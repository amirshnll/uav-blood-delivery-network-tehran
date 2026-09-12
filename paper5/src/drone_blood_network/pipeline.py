from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from math import atan2, degrees, hypot
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from .config import DEFAULT_SETTINGS, WIND_SCENARIOS, Settings, WindScenario
from .data import StudyData, load_study_data
from .energy import sortie_energy_per_km
from .optimization import SetCoverResult, solve_set_cover
from .routing import (
    RoutingGrid,
    build_routing_grid,
    dijkstra_energy,
    reconstruct_path,
)
from .visualization import (
    plot_calm_network,
    plot_detour_distribution,
    plot_scenario_summary,
)


def _point_xy(frame: gpd.GeoDataFrame) -> dict[str, tuple[float, float]]:
    return {
        row.site_id: (float(row.geometry.x), float(row.geometry.y))
        for row in frame.itertuples()
    }


def _map_endpoints(
    frame: gpd.GeoDataFrame,
    grid: RoutingGrid,
    settings: Settings,
    forbidden_geometry,
) -> tuple[dict[str, tuple[int, int]], pd.DataFrame]:
    mapping: dict[str, tuple[int, int]] = {}
    rows = []
    for row in frame.itertuples():
        cell, snap_distance = grid.nearest_free_cell(
            float(row.geometry.x),
            float(row.geometry.y),
            settings.max_endpoint_snap_m,
            forbidden_geometry,
        )
        rows.append(
            {
                "site_id": row.site_id,
                "grid_cell": "" if cell is None else f"{cell[0]}:{cell[1]}",
                "grid_snap_distance_m": snap_distance,
                "mapped_to_free_grid": cell is not None,
            }
        )
        if cell is not None:
            mapping[row.site_id] = cell
    return mapping, pd.DataFrame(rows)


def _bearing_between_xy(start: tuple[float, float], end: tuple[float, float]) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return (degrees(atan2(dx, dy)) + 360.0) % 360.0


def _connector_cost(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    scenario: WindScenario,
    settings: Settings,
) -> tuple[float, float]:
    distance_km = hypot(end_xy[0] - start_xy[0], end_xy[1] - start_xy[1]) / 1000.0
    if distance_km == 0:
        return 0.0, 0.0
    bearing = _bearing_between_xy(start_xy, end_xy)
    energy = sortie_energy_per_km(bearing, scenario, settings)
    return energy.energy_per_km * distance_km, distance_km


def build_direct_coverage(
    data: StudyData,
    scenario: WindScenario,
    settings: Settings,
) -> pd.DataFrame:
    rows = []
    for station in data.candidates.itertuples():
        station_xy = (float(station.geometry.x), float(station.geometry.y))
        for demand in data.drone_eligible_demands.itertuples():
            demand_xy = (float(demand.geometry.x), float(demand.geometry.y))
            distance_km = hypot(
                demand_xy[0] - station_xy[0], demand_xy[1] - station_xy[1]
            ) / 1000.0
            bearing = _bearing_between_xy(station_xy, demand_xy)
            directional = sortie_energy_per_km(bearing, scenario, settings)
            energy = directional.energy_per_km * distance_km
            if energy <= settings.available_cruise_energy_fraction:
                rows.append(
                    {
                        "station_id": station.site_id,
                        "demand_id": demand.site_id,
                        "route_energy_fraction": energy,
                        "route_distance_km": distance_km,
                        "straight_distance_km": distance_km,
                        "detour_ratio": 1.0,
                    }
                )
    return pd.DataFrame(rows)


def build_safe_coverage(
    data: StudyData,
    grid: RoutingGrid,
    candidate_cells: dict[str, tuple[int, int]],
    demand_cells: dict[str, tuple[int, int]],
    scenario: WindScenario,
    settings: Settings,
) -> pd.DataFrame:
    station_xy = _point_xy(data.candidates)
    demand_xy = _point_xy(data.drone_eligible_demands)
    cell_to_demands: dict[tuple[int, int], list[str]] = {}
    for demand_id, cell in demand_cells.items():
        cell_to_demands.setdefault(cell, []).append(demand_id)
    target_cells = set(cell_to_demands)
    rows = []
    for station_id, station_cell in candidate_cells.items():
        station_cell_xy = grid.cell_center(station_cell)
        station_connector_energy, station_connector_km = _connector_cost(
            station_xy[station_id], station_cell_xy, scenario, settings
        )
        search = dijkstra_energy(
            grid,
            station_cell,
            target_cells,
            scenario,
            settings,
            keep_predecessors=False,
        )
        for cell, route_energy in search.energy.items():
            for demand_id in cell_to_demands[cell]:
                demand_cell_xy = grid.cell_center(cell)
                demand_connector_energy, demand_connector_km = _connector_cost(
                    demand_cell_xy, demand_xy[demand_id], scenario, settings
                )
                total_route_energy = (
                    station_connector_energy + route_energy + demand_connector_energy
                )
                if total_route_energy > settings.available_cruise_energy_fraction:
                    continue
                straight_km = hypot(
                    demand_xy[demand_id][0] - station_xy[station_id][0],
                    demand_xy[demand_id][1] - station_xy[station_id][1],
                ) / 1000.0
                route_km = (
                    station_connector_km
                    + search.distance_m[cell] / 1000.0
                    + demand_connector_km
                )
                rows.append(
                    {
                        "station_id": station_id,
                        "demand_id": demand_id,
                        "route_energy_fraction": total_route_energy,
                        "route_distance_km": route_km,
                        "straight_distance_km": straight_km,
                        "detour_ratio": route_km / straight_km if straight_km else 1.0,
                    }
                )
    return pd.DataFrame(rows)


def _enrich_assignments(
    assignments: pd.DataFrame, data: StudyData, scenario: WindScenario, settings: Settings
) -> pd.DataFrame:
    demand_columns = data.drone_eligible_demands[
        ["site_id", "name", "facility_category", "latitude", "longitude"]
    ].rename(
        columns={
            "site_id": "demand_id",
            "name": "demand_name",
            "facility_category": "demand_category",
            "latitude": "demand_latitude",
            "longitude": "demand_longitude",
        }
    )
    station_columns = data.candidates[
        ["site_id", "name", "facility_category", "latitude", "longitude"]
    ].rename(
        columns={
            "site_id": "station_id",
            "name": "station_name",
            "facility_category": "station_category",
            "latitude": "station_latitude",
            "longitude": "station_longitude",
        }
    )
    result = assignments.merge(demand_columns, on="demand_id", how="left")
    result = result.merge(station_columns, on="station_id", how="left")
    result["scenario"] = scenario.code
    result["wind_speed_mps"] = scenario.speed_mps
    result["wind_flow_bearing_deg"] = scenario.flow_bearing_deg
    result["total_energy_fraction"] = (
        result["route_energy_fraction"] + settings.takeoff_landing_energy_fraction
    )
    result["battery_reserve_after_mission_fraction"] = (
        1.0 - result["total_energy_fraction"]
    )
    result["unserved_reason"] = np.where(
        result["station_id"].isna(),
        "no_energy_feasible_safe_route_from_authorized_candidate",
        "",
    )
    return result


def _append_grid_unmapped_demands(
    assignments: pd.DataFrame,
    data: StudyData,
    mapped_demand_ids: set[str],
    scenario: WindScenario,
) -> pd.DataFrame:
    missing = data.drone_eligible_demands[
        ~data.drone_eligible_demands["site_id"].isin(mapped_demand_ids)
    ]
    if missing.empty:
        return assignments
    rows = pd.DataFrame(
        {
            "demand_id": missing["site_id"].values,
            "station_id": pd.NA,
            "route_energy_fraction": np.nan,
            "route_distance_km": np.nan,
            "straight_distance_km": np.nan,
            "detour_ratio": np.nan,
            "demand_name": missing["name"].values,
            "demand_category": missing["facility_category"].values,
            "demand_latitude": missing["latitude"].values,
            "demand_longitude": missing["longitude"].values,
            "station_name": pd.NA,
            "station_category": pd.NA,
            "station_latitude": np.nan,
            "station_longitude": np.nan,
            "scenario": scenario.code,
            "wind_speed_mps": scenario.speed_mps,
            "wind_flow_bearing_deg": scenario.flow_bearing_deg,
            "total_energy_fraction": np.nan,
            "battery_reserve_after_mission_fraction": np.nan,
            "unserved_reason": "endpoint_not_connectable_to_safe_grid_within_snap_limit",
        }
    )
    return pd.concat([assignments, rows], ignore_index=True)


def _scenario_metrics(
    scenario: WindScenario,
    result: SetCoverResult,
    assignments: pd.DataFrame,
    calm_station_ids: set[str] | None,
    total_eligible_demand_count: int,
) -> dict:
    covered = assignments[assignments["station_id"].notna()].copy()
    selected = set(result.selected_station_ids)
    return {
        "scenario": scenario.code,
        "scenario_label_fa": scenario.label_fa,
        "wind_speed_mps": scenario.speed_mps,
        "wind_flow_bearing_deg": scenario.flow_bearing_deg,
        "station_count": result.station_count,
        "covered_demand_count": result.covered_demand_count,
        "uncovered_demand_count": result.uncovered_demand_count,
        "total_eligible_demand_count": total_eligible_demand_count,
        "total_unserved_eligible_demand_count": (
            total_eligible_demand_count - result.covered_demand_count
        ),
        "covered_share_of_all_eligible_demands": (
            result.covered_demand_count / total_eligible_demand_count
        ),
        "mean_route_distance_km": float(covered["route_distance_km"].mean()),
        "p95_route_distance_km": float(covered["route_distance_km"].quantile(0.95)),
        "max_route_distance_km": float(covered["route_distance_km"].max()),
        "mean_detour_ratio": float(covered["detour_ratio"].mean()),
        "p95_detour_ratio": float(covered["detour_ratio"].quantile(0.95)),
        "max_detour_ratio": float(covered["detour_ratio"].max()),
        "mean_total_energy_fraction": float(covered["total_energy_fraction"].mean()),
        "p95_total_energy_fraction": float(covered["total_energy_fraction"].quantile(0.95)),
        "max_total_energy_fraction": float(covered["total_energy_fraction"].max()),
        "changed_station_count_vs_calm": (
            0 if calm_station_ids is None else len(selected.symmetric_difference(calm_station_ids))
        ),
        "solver_status": result.solver_status,
    }


def build_route_geometries(
    data: StudyData,
    grid: RoutingGrid,
    result: SetCoverResult,
    assignments: pd.DataFrame,
    candidate_cells: dict[str, tuple[int, int]],
    demand_cells: dict[str, tuple[int, int]],
    scenario: WindScenario,
    settings: Settings,
) -> gpd.GeoDataFrame:
    station_xy = _point_xy(data.candidates)
    demand_xy = _point_xy(data.drone_eligible_demands)
    covered = assignments[assignments["station_id"].notna()].copy()
    rows = []
    for station_id in result.selected_station_ids:
        assigned = covered[covered["station_id"] == station_id]
        if assigned.empty:
            continue
        target_cells = {demand_cells[demand_id] for demand_id in assigned["demand_id"]}
        search = dijkstra_energy(
            grid,
            candidate_cells[station_id],
            target_cells,
            scenario,
            settings,
            keep_predecessors=True,
        )
        assert search.predecessor is not None
        for row in assigned.itertuples():
            target_cell = demand_cells[row.demand_id]
            geometry = reconstruct_path(
                grid,
                candidate_cells[station_id],
                target_cell,
                search.predecessor,
                start_xy=station_xy[station_id],
                target_xy=demand_xy[row.demand_id],
            )
            rows.append(
                {
                    "scenario": scenario.code,
                    "station_id": station_id,
                    "demand_id": row.demand_id,
                    "route_energy_fraction": row.route_energy_fraction,
                    "route_distance_km": row.route_distance_km,
                    "geometry": geometry,
                }
            )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=settings.metric_crs)


def validate_routes(
    routes: gpd.GeoDataFrame, zones: gpd.GeoDataFrame
) -> pd.DataFrame:
    if routes.empty:
        return pd.DataFrame(
            [{"route_count": 0, "intersecting_route_count": 0, "all_routes_safe": True}]
        )
    joined = gpd.sjoin(
        routes[["demand_id", "geometry"]],
        zones[["geometry"]],
        how="left",
        predicate="intersects",
    )
    intersecting = joined.loc[joined["index_right"].notna(), "demand_id"].nunique()
    return pd.DataFrame(
        [
            {
                "route_count": len(routes),
                "intersecting_route_count": int(intersecting),
                "all_routes_safe": bool(intersecting == 0),
            }
        ]
    )


def direct_route_intersection_audit(
    assignments: pd.DataFrame, data: StudyData, settings: Settings
) -> pd.DataFrame:
    station_xy = _point_xy(data.candidates)
    demand_xy = _point_xy(data.drone_eligible_demands)
    rows = []
    for row in assignments[assignments["station_id"].notna()].itertuples():
        rows.append(
            {
                "demand_id": row.demand_id,
                "geometry": LineString(
                    [station_xy[row.station_id], demand_xy[row.demand_id]]
                ),
            }
        )
    lines = gpd.GeoDataFrame(rows, geometry="geometry", crs=settings.metric_crs)
    joined = gpd.sjoin(
        lines,
        data.no_fly_zones[["geometry"]],
        how="left",
        predicate="intersects",
    )
    intersecting = joined.loc[joined["index_right"].notna(), "demand_id"].nunique()
    return pd.DataFrame(
        [
            {
                "direct_assignment_count": len(lines),
                "intersecting_direct_assignment_count": int(intersecting),
                "intersecting_direct_assignment_share": (
                    intersecting / len(lines) if len(lines) else 0.0
                ),
            }
        ]
    )


def run_analysis(settings: Settings = DEFAULT_SETTINGS) -> dict:
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    data = load_study_data(settings)
    data.accessibility.to_csv(
        settings.results_dir / "demand_accessibility.csv", index=False
    )
    grid = build_routing_grid(data.boundary, data.no_fly_zones, settings)
    forbidden_geometry = data.no_fly_zones.geometry.union_all()
    candidate_cells, candidate_mapping = _map_endpoints(
        data.candidates, grid, settings, forbidden_geometry
    )
    demand_cells, demand_mapping = _map_endpoints(
        data.drone_eligible_demands, grid, settings, forbidden_geometry
    )
    endpoint_mapping = pd.concat(
        [
            candidate_mapping.assign(endpoint_role="candidate_station"),
            demand_mapping.assign(endpoint_role="demand"),
        ],
        ignore_index=True,
    )
    endpoint_mapping.to_csv(settings.results_dir / "endpoint_grid_mapping.csv", index=False)
    valid_demand_ids = sorted(demand_cells)
    valid_candidate_ids = sorted(candidate_cells)

    calm = WIND_SCENARIOS[0]
    direct_coverage = build_direct_coverage(data, calm, settings)
    direct_coverage = direct_coverage[
        direct_coverage["station_id"].isin(valid_candidate_ids)
        & direct_coverage["demand_id"].isin(valid_demand_ids)
    ].copy()
    direct_result = solve_set_cover(
        direct_coverage, valid_demand_ids, valid_candidate_ids, settings
    )
    direct_assignments = _enrich_assignments(
        direct_result.assignments, data, calm, settings
    )
    direct_assignments.to_csv(
        settings.results_dir / "assignments_direct_calm.csv", index=False
    )
    direct_audit = direct_route_intersection_audit(direct_assignments, data, settings)
    direct_audit.to_csv(
        settings.results_dir / "validation_direct_route_intersections.csv", index=False
    )

    scenario_rows = []
    station_rows = []
    all_assignments = []
    route_validation_rows = []
    calm_result: SetCoverResult | None = None
    calm_assignments: pd.DataFrame | None = None
    calm_coverage: pd.DataFrame | None = None
    calm_routes: gpd.GeoDataFrame | None = None
    calm_station_ids: set[str] | None = None

    for scenario in WIND_SCENARIOS:
        coverage = build_safe_coverage(
            data,
            grid,
            candidate_cells,
            demand_cells,
            scenario,
            settings,
        )
        result = solve_set_cover(
            coverage,
            valid_demand_ids,
            valid_candidate_ids,
            settings,
            preferred_station_ids=(calm_station_ids if scenario.code != "CALM" else None),
        )
        assignments = _enrich_assignments(result.assignments, data, scenario, settings)
        assignments = _append_grid_unmapped_demands(
            assignments, data, set(demand_cells), scenario
        )
        scenario_routes = build_route_geometries(
            data,
            grid,
            result,
            assignments,
            candidate_cells,
            demand_cells,
            scenario,
            settings,
        )
        scenario_validation = validate_routes(scenario_routes, data.no_fly_zones)
        route_validation_rows.append(
            {
                "scenario": scenario.code,
                **scenario_validation.iloc[0].to_dict(),
            }
        )
        if scenario.code == "CALM":
            calm_result = result
            calm_assignments = assignments
            calm_coverage = coverage
            calm_routes = scenario_routes
            calm_station_ids = set(result.selected_station_ids)
        scenario_rows.append(
            _scenario_metrics(
                scenario,
                result,
                assignments,
                calm_station_ids if scenario.code != "CALM" else None,
                len(data.drone_eligible_demands),
            )
        )
        selected_details = data.candidates[
            data.candidates["site_id"].isin(result.selected_station_ids)
        ]
        for station in selected_details.itertuples():
            station_rows.append(
                {
                    "scenario": scenario.code,
                    "station_id": station.site_id,
                    "station_name": station.name,
                    "facility_category": station.facility_category,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                }
            )
        all_assignments.append(assignments)

    scenario_summary = pd.DataFrame(scenario_rows)
    scenario_summary.to_csv(settings.results_dir / "scenario_summary.csv", index=False)
    pd.DataFrame(station_rows).to_csv(
        settings.results_dir / "selected_stations_by_scenario.csv", index=False
    )
    assignments_by_scenario = pd.concat(all_assignments, ignore_index=True)
    assignments_by_scenario.to_csv(
        settings.results_dir / "assignments_by_scenario.csv", index=False
    )
    route_validation_by_scenario = pd.DataFrame(route_validation_rows)
    route_validation_by_scenario.to_csv(
        settings.results_dir / "validation_routes_by_scenario.csv", index=False
    )
    if not route_validation_by_scenario["all_routes_safe"].astype(bool).all():
        invalid = route_validation_by_scenario.loc[
            ~route_validation_by_scenario["all_routes_safe"].astype(bool), "scenario"
        ].tolist()
        raise RuntimeError(
            f"Final route validation failed for scenarios: {invalid}."
        )

    assert (
        calm_result is not None
        and calm_assignments is not None
        and calm_coverage is not None
        and calm_routes is not None
    )
    calm_routes.to_file(settings.results_dir / "routes_calm.geojson", driver="GeoJSON")
    route_validation = validate_routes(calm_routes, data.no_fly_zones)
    route_validation.to_csv(
        settings.results_dir / "validation_safe_routes.csv", index=False
    )
    if not bool(route_validation.loc[0, "all_routes_safe"]):
        raise RuntimeError(
            "Final route validation failed: at least one reported route intersects a no-fly zone."
        )

    selected_calm = data.candidates[
        data.candidates["site_id"].isin(calm_result.selected_station_ids)
    ]
    plot_scenario_summary(
        scenario_summary, settings.results_dir / "figure_scenario_summary.png"
    )
    plot_calm_network(
        data.boundary,
        data.no_fly_zones,
        data.drone_eligible_demands,
        selected_calm,
        calm_routes,
        settings.results_dir / "figure_calm_network.png",
    )
    plot_detour_distribution(
        calm_assignments, settings.results_dir / "figure_detour_distribution.png"
    )

    summary = {
        "raw_facility_count": int(len(data.facilities)),
        "total_demand_count": int(len(data.demands)),
        "drone_eligible_demand_count": int(len(data.drone_eligible_demands)),
        "restricted_demand_count": int(len(data.restricted_demands)),
        "valid_candidate_station_count": int(len(data.candidates)),
        "mapped_candidate_station_count": int(len(candidate_cells)),
        "mapped_eligible_demand_count": int(len(demand_cells)),
        "grid_rows": int(grid.shape[0]),
        "grid_columns": int(grid.shape[1]),
        "grid_resolution_m": settings.grid_resolution_m,
        "no_fly_clearance_m": settings.no_fly_clearance_m,
        "free_grid_cell_share": float(grid.free.mean()),
        "available_cruise_energy_fraction": settings.available_cruise_energy_fraction,
        "direct_calm_station_count": direct_result.station_count,
        "safe_calm_station_count": calm_result.station_count,
        "direct_routes_intersecting_no_fly_count": int(
            direct_audit.loc[0, "intersecting_direct_assignment_count"]
        ),
        "direct_routes_intersecting_no_fly_share": float(
            direct_audit.loc[0, "intersecting_direct_assignment_share"]
        ),
        "safe_routes_intersecting_no_fly_count": int(
            route_validation.loc[0, "intersecting_route_count"]
        ),
        "scenario_station_count_min": int(scenario_summary["station_count"].min()),
        "scenario_station_count_max": int(scenario_summary["station_count"].max()),
        "scenario_uncovered_demand_count_max": int(
            scenario_summary["uncovered_demand_count"].max()
        ),
        "scenario_total_unserved_eligible_demand_count_max": int(
            scenario_summary["total_unserved_eligible_demand_count"].max()
        ),
        "settings": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(settings).items()
        },
    }
    (settings.results_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def run_sensitivity(settings: Settings = DEFAULT_SETTINGS) -> pd.DataFrame:
    rows = []
    for resolution in (75.0, 100.0, 150.0):
        for reserve in (0.15, 0.20, 0.25):
            scenario_settings = replace(
                settings,
                grid_resolution_m=resolution,
                battery_reserve_fraction=reserve,
            )
            data = load_study_data(scenario_settings)
            grid = build_routing_grid(
                data.boundary, data.no_fly_zones, scenario_settings
            )
            forbidden_geometry = data.no_fly_zones.geometry.union_all()
            candidate_cells, _ = _map_endpoints(
                data.candidates, grid, scenario_settings, forbidden_geometry
            )
            demand_cells, _ = _map_endpoints(
                data.drone_eligible_demands,
                grid,
                scenario_settings,
                forbidden_geometry,
            )
            coverage = build_safe_coverage(
                data,
                grid,
                candidate_cells,
                demand_cells,
                WIND_SCENARIOS[0],
                scenario_settings,
            )
            result = solve_set_cover(
                coverage,
                sorted(demand_cells),
                sorted(candidate_cells),
                scenario_settings,
            )
            assignments = _enrich_assignments(
                result.assignments, data, WIND_SCENARIOS[0], scenario_settings
            )
            covered = assignments[assignments["station_id"].notna()]
            rows.append(
                {
                    "grid_resolution_m": resolution,
                    "battery_reserve_fraction": reserve,
                    "station_count": result.station_count,
                    "mapped_eligible_demand_count": len(demand_cells),
                    "covered_demand_count": result.covered_demand_count,
                    "uncovered_demand_count": result.uncovered_demand_count,
                    "total_unserved_eligible_demand_count": (
                        len(data.drone_eligible_demands) - result.covered_demand_count
                    ),
                    "covered_share_of_all_eligible_demands": (
                        result.covered_demand_count / len(data.drone_eligible_demands)
                    ),
                    "mean_route_distance_km": covered["route_distance_km"].mean(),
                    "mean_total_energy_fraction": covered["total_energy_fraction"].mean(),
                }
            )
    sensitivity = pd.DataFrame(rows)
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    sensitivity.to_csv(settings.results_dir / "validation_sensitivity.csv", index=False)
    return sensitivity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="run main analysis and sensitivity")
    parser.add_argument("--sensitivity", action="store_true", help="run sensitivity only")
    args = parser.parse_args()
    if args.sensitivity:
        print(run_sensitivity().to_string(index=False))
        return
    summary = run_analysis()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.all:
        print(run_sensitivity().to_string(index=False))


if __name__ == "__main__":
    main()
