from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pulp

from .config import Settings


@dataclass
class SetCoverResult:
    selected_station_ids: list[str]
    assignments: pd.DataFrame
    station_count: int
    covered_demand_count: int
    uncovered_demand_count: int
    solver_status: str


def solve_set_cover(
    coverage: pd.DataFrame,
    demand_ids: list[str],
    candidate_ids: list[str],
    settings: Settings,
    preferred_station_ids: set[str] | None = None,
) -> SetCoverResult:
    feasible = coverage[
        np.isfinite(coverage["route_energy_fraction"])
        & (coverage["route_energy_fraction"] <= settings.available_cruise_energy_fraction)
    ].copy()
    by_demand = feasible.groupby("demand_id")["station_id"].agg(list).to_dict()
    impossible = [demand_id for demand_id in demand_ids if demand_id not in by_demand]

    model = pulp.LpProblem("safe_wind_energy_station_siting", pulp.LpMinimize)
    station_vars = {
        station_id: pulp.LpVariable(f"x_{station_id}", cat="Binary")
        for station_id in candidate_ids
    }
    uncovered_vars = {
        demand_id: pulp.LpVariable(f"u_{demand_id}", cat="Binary")
        for demand_id in demand_ids
    }
    penalty = len(candidate_ids) + 1
    stability_term = pulp.lpSum(
        station_vars[station_id]
        for station_id in candidate_ids
        if preferred_station_ids is not None and station_id not in preferred_station_ids
    )
    model += (
        pulp.lpSum(station_vars.values())
        + penalty * pulp.lpSum(uncovered_vars.values())
        + 1e-3 * stability_term
    )
    for demand_id in demand_ids:
        stations = by_demand.get(demand_id, [])
        model += (
            pulp.lpSum(station_vars[station_id] for station_id in stations)
            + uncovered_vars[demand_id]
            >= 1,
            f"cover_{demand_id}",
        )
        if demand_id in impossible:
            model += uncovered_vars[demand_id] == 1

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=settings.solver_time_limit_s)
    status_code = model.solve(solver)
    status = pulp.LpStatus[status_code]
    if status not in {"Optimal", "Not Solved"}:
        raise RuntimeError(f"Set-cover optimization failed with status {status}.")
    selected_ids = sorted(
        station_id
        for station_id, variable in station_vars.items()
        if variable.value() is not None and variable.value() >= 0.5
    )

    selected_coverage = feasible[feasible["station_id"].isin(selected_ids)].copy()
    if selected_coverage.empty:
        assignments = pd.DataFrame(
            columns=[
                "demand_id",
                "station_id",
                "route_energy_fraction",
                "route_distance_km",
                "straight_distance_km",
                "detour_ratio",
            ]
        )
    else:
        assignments = (
            selected_coverage.sort_values(
                ["demand_id", "route_energy_fraction", "route_distance_km"]
            )
            .drop_duplicates("demand_id")
            .reset_index(drop=True)
        )
    covered_ids = set(assignments["demand_id"])
    uncovered_ids = sorted(set(demand_ids) - covered_ids)
    if uncovered_ids:
        missing_rows = pd.DataFrame(
            {
                "demand_id": uncovered_ids,
                "station_id": pd.NA,
                "route_energy_fraction": np.nan,
                "route_distance_km": np.nan,
                "straight_distance_km": np.nan,
                "detour_ratio": np.nan,
            }
        )
        assignments = pd.concat([assignments, missing_rows], ignore_index=True)

    return SetCoverResult(
        selected_station_ids=selected_ids,
        assignments=assignments,
        station_count=len(selected_ids),
        covered_demand_count=len(covered_ids),
        uncovered_demand_count=len(uncovered_ids),
        solver_status=status,
    )
