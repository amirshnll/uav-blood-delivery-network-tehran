from __future__ import annotations

from dataclasses import dataclass
import heapq
from math import atan2, ceil, degrees, hypot

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import LineString

from .config import Settings, WindScenario
from .energy import sortie_energy_per_km


MOVES = (
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
    (-1, -1),
    (-1, 1),
    (1, -1),
    (1, 1),
)


@dataclass
class RoutingGrid:
    free: np.ndarray
    transform: object
    resolution_m: float
    crs: str

    @property
    def shape(self) -> tuple[int, int]:
        return self.free.shape

    def cell_center(self, cell: tuple[int, int]) -> tuple[float, float]:
        row, col = cell
        x = self.transform.c + (col + 0.5) * self.transform.a
        y = self.transform.f + (row + 0.5) * self.transform.e
        return float(x), float(y)

    def raw_cell_for_xy(self, x: float, y: float) -> tuple[int, int]:
        col = int((x - self.transform.c) // self.resolution_m)
        row = int((self.transform.f - y) // self.resolution_m)
        return row, col

    def nearest_free_cell(
        self,
        x: float,
        y: float,
        max_distance_m: float,
        forbidden_geometry=None,
    ) -> tuple[tuple[int, int] | None, float]:
        row, col = self.raw_cell_for_xy(x, y)
        rows, cols = self.shape
        max_steps = int(ceil(max_distance_m / self.resolution_m))
        best: tuple[int, int] | None = None
        best_distance = float("inf")
        for dr in range(-max_steps, max_steps + 1):
            for dc in range(-max_steps, max_steps + 1):
                rr, cc = row + dr, col + dc
                if not (0 <= rr < rows and 0 <= cc < cols and self.free[rr, cc]):
                    continue
                cx, cy = self.cell_center((rr, cc))
                distance = hypot(cx - x, cy - y)
                if distance > max_distance_m:
                    continue
                if forbidden_geometry is not None and LineString(
                    [(x, y), (cx, cy)]
                ).intersects(forbidden_geometry):
                    continue
                if distance < best_distance:
                    best = (rr, cc)
                    best_distance = distance
        return best, best_distance


@dataclass
class SearchResult:
    energy: dict[tuple[int, int], float]
    distance_m: dict[tuple[int, int], float]
    predecessor: dict[tuple[int, int], tuple[int, int]] | None


def build_routing_grid(
    boundary: gpd.GeoDataFrame,
    no_fly_zones: gpd.GeoDataFrame,
    settings: Settings,
) -> RoutingGrid:
    boundary_geometry = boundary.geometry.union_all()
    minx, miny, maxx, maxy = boundary_geometry.bounds
    resolution = settings.grid_resolution_m
    width = int(ceil((maxx - minx) / resolution))
    height = int(ceil((maxy - miny) / resolution))
    transform = from_origin(minx, maxy, resolution, resolution)

    city_mask = rasterize(
        [(boundary_geometry, 1)],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=False,
        dtype="uint8",
    ).astype(bool)
    buffered = no_fly_zones.geometry.buffer(settings.no_fly_clearance_m)
    blocked_mask = rasterize(
        [(geometry, 1) for geometry in buffered if not geometry.is_empty],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=False,
        dtype="uint8",
    ).astype(bool)
    return RoutingGrid(
        free=city_mask & ~blocked_mask,
        transform=transform,
        resolution_m=resolution,
        crs=settings.metric_crs,
    )


def bearing_for_move(dr: int, dc: int) -> float:
    east = float(dc)
    north = float(-dr)
    return (degrees(atan2(east, north)) + 360.0) % 360.0


def directional_move_costs(
    scenario: WindScenario, settings: Settings
) -> dict[tuple[int, int], tuple[float, float]]:
    costs: dict[tuple[int, int], tuple[float, float]] = {}
    for dr, dc in MOVES:
        length_m = settings.grid_resolution_m * hypot(dr, dc)
        energy = sortie_energy_per_km(bearing_for_move(dr, dc), scenario, settings)
        costs[(dr, dc)] = (energy.energy_per_km * length_m / 1000.0, length_m)
    return costs


def dijkstra_energy(
    grid: RoutingGrid,
    start: tuple[int, int],
    targets: set[tuple[int, int]],
    scenario: WindScenario,
    settings: Settings,
    *,
    keep_predecessors: bool = False,
) -> SearchResult:
    max_energy = settings.available_cruise_energy_fraction
    move_costs = directional_move_costs(scenario, settings)
    best = {start: 0.0}
    path_distance = {start: 0.0}
    predecessor: dict[tuple[int, int], tuple[int, int]] | None = (
        {} if keep_predecessors else None
    )
    heap: list[tuple[float, int, int]] = [(0.0, start[0], start[1])]
    remaining = set(targets)
    rows, cols = grid.shape

    while heap and remaining:
        current_energy, row, col = heapq.heappop(heap)
        node = (row, col)
        if current_energy != best.get(node):
            continue
        if current_energy > max_energy:
            break
        remaining.discard(node)

        for dr, dc in MOVES:
            nr, nc = row + dr, col + dc
            if not (0 <= nr < rows and 0 <= nc < cols and grid.free[nr, nc]):
                continue
            if dr and dc:
                if not (grid.free[row + dr, col] and grid.free[row, col + dc]):
                    continue
            edge_energy, edge_distance = move_costs[(dr, dc)]
            candidate_energy = current_energy + edge_energy
            if candidate_energy > max_energy:
                continue
            next_node = (nr, nc)
            if candidate_energy + 1e-12 < best.get(next_node, float("inf")):
                best[next_node] = candidate_energy
                path_distance[next_node] = path_distance[node] + edge_distance
                if predecessor is not None:
                    predecessor[next_node] = node
                heapq.heappush(heap, (candidate_energy, nr, nc))

    return SearchResult(
        energy={target: best[target] for target in targets if target in best},
        distance_m={
            target: path_distance[target] for target in targets if target in path_distance
        },
        predecessor=predecessor,
    )


def reconstruct_path(
    grid: RoutingGrid,
    start: tuple[int, int],
    target: tuple[int, int],
    predecessor: dict[tuple[int, int], tuple[int, int]],
    start_xy: tuple[float, float] | None = None,
    target_xy: tuple[float, float] | None = None,
) -> LineString | None:
    if target != start and target not in predecessor:
        return None
    nodes = [target]
    while nodes[-1] != start:
        nodes.append(predecessor[nodes[-1]])
    nodes.reverse()
    coordinates = [grid.cell_center(node) for node in nodes]
    if start_xy is not None:
        coordinates.insert(0, start_xy)
    if target_xy is not None:
        coordinates.append(target_xy)
    deduplicated = [coordinates[0]]
    for coordinate in coordinates[1:]:
        if coordinate != deduplicated[-1]:
            deduplicated.append(coordinate)
    coordinates = deduplicated
    if len(coordinates) == 1:
        coordinates.append(coordinates[0])
    return LineString(coordinates)
