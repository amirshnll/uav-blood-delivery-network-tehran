from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd
import pulp

from .config import Settings
from .wind import effective_distance_multiplier, initial_bearing_degrees


EARTH_RADIUS_KM = 6371.0


@dataclass
class OptimizationResult:
    selected_stations: pd.DataFrame
    demand_points: pd.DataFrame
    assignments: pd.DataFrame
    station_count: int
    uncovered_demand_count: int
    objective_value: float
    candidate_pool: str


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def build_distance_matrix(
    candidates: pd.DataFrame, demand: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for candidate in candidates.itertuples(index=False):
        for point in demand.itertuples(index=False):
            distance_km = haversine_km(
                candidate.latitude,
                candidate.longitude,
                point.latitude,
                point.longitude,
            )
            route_bearing_deg = initial_bearing_degrees(
                candidate.latitude,
                candidate.longitude,
                point.latitude,
                point.longitude,
            )
            rows.append(
                {
                    "station_id": candidate.site_id,
                    "demand_id": point.site_id,
                    "distance_km": distance_km,
                    "route_bearing_deg": route_bearing_deg,
                }
            )
    return pd.DataFrame(rows)


def _prepare_sites(
    facilities: pd.DataFrame, use_all_as_candidates: bool
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    sites = facilities.copy().reset_index(drop=True)
    sites["site_id"] = [f"site_{idx}" for idx in range(len(sites))]
    demand = sites[sites["is_demand_point"]].copy().reset_index(drop=True)
    if use_all_as_candidates:
        candidates = sites.copy().reset_index(drop=True)
        pool_label = "all_facilities"
    else:
        candidates = sites[sites["is_candidate_station"]].copy().reset_index(drop=True)
        pool_label = "preferred_only"
    return candidates, demand, pool_label


def solve_set_cover(
    facilities: pd.DataFrame,
    settings: Settings,
    use_all_as_candidates: bool = False,
) -> OptimizationResult:
    candidates, demand, pool_label = _prepare_sites(facilities, use_all_as_candidates)
    if candidates.empty or demand.empty:
        raise RuntimeError("Candidate stations or demand points are empty.")

    distances = build_distance_matrix(candidates, demand)
    wind_adjustments = distances["route_bearing_deg"].apply(
        lambda bearing: effective_distance_multiplier(float(bearing), settings)
    )
    distances["distance_multiplier"] = wind_adjustments.apply(lambda value: value[0])
    distances["wind_alignment"] = wind_adjustments.apply(lambda value: value[1])
    distances["effective_distance_km"] = (
        distances["distance_km"] * distances["distance_multiplier"]
    )
    coverage = distances[
        distances["effective_distance_km"] <= settings.max_operation_radius_km
    ].copy()
    covered_ids = set(coverage["demand_id"].unique())
    uncovered = [
        demand_id for demand_id in demand["site_id"] if demand_id not in covered_ids
    ]
    if uncovered:
        raise RuntimeError(
            f"{len(uncovered)} demand points are not coverable with wind-adjusted radius "
            f"{settings.max_operation_radius_km} km using candidate pool '{pool_label}'."
        )

    model = pulp.LpProblem("tehran_drone_station_location", pulp.LpMinimize)
    station_vars = {
        station_id: pulp.LpVariable(f"x_{station_id}", cat="Binary")
        for station_id in candidates["site_id"]
    }
    model += pulp.lpSum(station_vars.values())

    for demand_id in demand["site_id"]:
        feasible_stations = coverage.loc[
            coverage["demand_id"] == demand_id, "station_id"
        ].tolist()
        model += (
            pulp.lpSum(station_vars[station_id] for station_id in feasible_stations)
            >= 1,
            f"cover_{demand_id}",
        )

    solver = pulp.PULP_CBC_CMD(msg=False)
    status = model.solve(solver)
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"Optimization failed with status {pulp.LpStatus[status]}.")

    selected_ids = [
        station_id
        for station_id, var in station_vars.items()
        if var.value() and var.value() >= 0.5
    ]
    selected = (
        candidates[candidates["site_id"].isin(selected_ids)]
        .copy()
        .reset_index(drop=True)
    )

    selected_coverage = coverage[coverage["station_id"].isin(selected_ids)].copy()
    assignment_rows = []
    for demand_point in demand.itertuples(index=False):
        feasible = selected_coverage[
            selected_coverage["demand_id"] == demand_point.site_id
        ].sort_values(["effective_distance_km", "distance_km"])
        nearest = feasible.iloc[0]
        assignment_rows.append(
            {
                "site_id": demand_point.site_id,
                "assigned_station_id": nearest["station_id"],
                "distance_km": nearest["distance_km"],
                "effective_distance_km": nearest["effective_distance_km"],
                "route_bearing_deg": nearest["route_bearing_deg"],
                "wind_alignment": nearest["wind_alignment"],
                "distance_multiplier": nearest["distance_multiplier"],
            }
        )

    assignment_df = demand.merge(
        pd.DataFrame(assignment_rows), on="site_id", how="left"
    )
    assignment_df["wind_speed_mps"] = settings.wind_speed_mps
    assignment_df["wind_direction"] = settings.wind_direction
    return OptimizationResult(
        selected_stations=selected,
        demand_points=demand,
        assignments=assignment_df,
        station_count=len(selected),
        uncovered_demand_count=0,
        objective_value=float(pulp.value(model.objective)),
        candidate_pool=pool_label,
    )


def solve_with_fallback(
    facilities: pd.DataFrame, settings: Settings
) -> OptimizationResult:
    try:
        return solve_set_cover(facilities, settings, use_all_as_candidates=False)
    except RuntimeError:
        return solve_set_cover(facilities, settings, use_all_as_candidates=True)


def save_optimization_outputs(result: OptimizationResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result.selected_stations.to_csv(output_dir / "selected_stations.csv", index=False)
    result.assignments.to_csv(output_dir / "demand_assignments.csv", index=False)
    wind_speed_mps = (
        float(result.assignments["wind_speed_mps"].iloc[0])
        if not result.assignments.empty and "wind_speed_mps" in result.assignments
        else 0.0
    )
    wind_direction = (
        str(result.assignments["wind_direction"].iloc[0])
        if not result.assignments.empty and "wind_direction" in result.assignments
        else "calm"
    )
    pd.DataFrame(
        [
            {
                "station_count": result.station_count,
                "uncovered_demand_count": result.uncovered_demand_count,
                "objective_value": result.objective_value,
                "candidate_pool": result.candidate_pool,
                "wind_speed_mps": wind_speed_mps,
                "wind_direction": wind_direction,
            }
        ]
    ).to_csv(output_dir / "optimization_summary.csv", index=False)
