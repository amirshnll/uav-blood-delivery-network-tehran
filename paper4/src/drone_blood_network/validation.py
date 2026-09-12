from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .config import Settings
from .optimization import solve_set_cover, solve_with_fallback
from .temperature import (
    TEMPERATURE_SCENARIOS,
    adjusted_mission_range_km,
    adjusted_operation_radius_km,
    battery_performance_factor,
    resolve_temperature_scenario,
)
from .wind import (
    WIND_DIRECTION_SCENARIOS,
    WIND_SPEED_SCENARIOS,
    effective_cruise_speed_mps,
)


def validate_constraints(assignments: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    effective_distances = assignments.get("effective_distance_km", assignments["distance_km"])
    temperature_scenario = resolve_temperature_scenario(settings)
    effective_round_trip_range_km = adjusted_mission_range_km(
        settings.effective_mission_range_km, settings
    )
    checks = {
        "all_demands_assigned": bool(assignments["assigned_station_id"].notna().all()),
        "all_within_radius": bool(
            (effective_distances <= settings.max_operation_radius_km).all()
        ),
        "all_within_base_radius": bool(
            (assignments["distance_km"] <= settings.max_operation_radius_km).all()
        ),
        "all_within_round_trip_range": bool(
            (assignments["distance_km"] * 2 <= effective_round_trip_range_km).all()
        ),
        "payload_within_limit": settings.base_payload_kg <= settings.max_payload_kg,
        "temperature_scenario": temperature_scenario.code,
        "temperature_status_label": temperature_scenario.status_label,
        "battery_performance_factor": battery_performance_factor(settings),
        "effective_round_trip_range_km": effective_round_trip_range_km,
        "wind_speed_mps": settings.wind_speed_mps,
        "wind_direction": settings.wind_direction,
    }
    return pd.DataFrame([checks])


def monte_carlo_robustness(
    assignments: pd.DataFrame, settings: Settings
) -> pd.DataFrame:
    rng = np.random.default_rng(settings.random_seed)
    rows = []
    base_effective_distances = assignments.get(
        "effective_distance_km", assignments["distance_km"]
    )
    route_bearings = assignments.get(
        "route_bearing_deg", pd.Series(np.zeros(len(assignments)))
    )
    base_radius_km = adjusted_operation_radius_km(
        settings.max_operation_radius_km, settings
    )
    base_range_km = adjusted_mission_range_km(settings.effective_mission_range_km, settings)

    for run_id in range(1, settings.monte_carlo_runs + 1):
        wind_penalty = rng.uniform(0.85, 1.0)
        speed_penalty = rng.uniform(0.8, 1.0)
        stressed_radius = base_radius_km * wind_penalty
        stressed_range = base_range_km * wind_penalty
        stressed_settings = replace(
            settings,
            wind_speed_mps=settings.wind_speed_mps
            + rng.uniform(0.0, settings.wind_reference_speed_mps * 0.25),
        )
        stressed_effective_distances = base_effective_distances * rng.uniform(
            1.0, 1.0 + (1.0 - wind_penalty), size=len(assignments)
        )
        stressed_speeds = [
            effective_cruise_speed_mps(
                settings.cruise_speed_mps * speed_penalty,
                float(route_bearing),
                stressed_settings,
            )[0]
            for route_bearing in route_bearings
        ]
        avg_service_min = float(
            (
                (assignments["distance_km"] * 2)
                / (np.maximum(stressed_speeds, settings.minimum_cruise_speed_mps) * 60.0 / 1000.0)
                + settings.handling_time_min
            ).mean()
        )
        rows.append(
            {
                "run_id": run_id,
                "stressed_radius_km": stressed_radius,
                "stressed_range_km": stressed_range,
                "stressed_speed_mps": float(np.mean(stressed_speeds)) if stressed_speeds else 0.0,
                "feasible_ratio": float(
                    (stressed_effective_distances <= stressed_radius).mean()
                ),
                "all_round_trip_feasible": bool(
                    (assignments["distance_km"] * 2 <= stressed_range).all()
                ),
                "avg_service_time_min": avg_service_min,
            }
        )
    return pd.DataFrame(rows)


def sensitivity_analysis(facilities: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    rows = []
    for radius in (5.0, settings.max_operation_radius_km, 7.0):
        scenario_settings = replace(
            settings,
            max_operation_radius_km=radius,
            effective_mission_range_km=max(radius * 2, settings.effective_mission_range_km),
        )
        try:
            result = solve_set_cover(
                facilities, scenario_settings, use_all_as_candidates=True
            )
            rows.append(
                {
                    "radius_km": radius,
                    "station_count": result.station_count,
                    "status": "optimal",
                }
            )
        except RuntimeError as exc:
            rows.append(
                {"radius_km": radius, "station_count": np.nan, "status": str(exc)}
            )
    return pd.DataFrame(rows)


def wind_scenario_analysis(
    facilities: pd.DataFrame, settings: Settings
) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_settings = replace(settings, wind_speed_mps=0.0, wind_direction="calm")
    baseline_result = solve_with_fallback(facilities, baseline_settings)
    baseline_station_ids = set(baseline_result.selected_stations["site_id"])
    summary_rows = []
    detail_rows = []

    for wind_speed_mps, wind_speed_label in WIND_SPEED_SCENARIOS:
        for wind_direction, wind_direction_label in WIND_DIRECTION_SCENARIOS:
            scenario_settings = replace(
                settings,
                wind_speed_mps=wind_speed_mps,
                wind_direction=wind_direction,
            )
            result = solve_with_fallback(facilities, scenario_settings)
            scenario_station_ids = set(result.selected_stations["site_id"])
            added_station_ids = sorted(scenario_station_ids - baseline_station_ids)
            removed_station_ids = sorted(baseline_station_ids - scenario_station_ids)

            summary_rows.append(
                {
                    "wind_speed_mps": wind_speed_mps,
                    "wind_speed_label": wind_speed_label,
                    "wind_direction": wind_direction,
                    "wind_direction_label": wind_direction_label,
                    "station_count": result.station_count,
                    "baseline_station_count": baseline_result.station_count,
                    "delta_station_count": result.station_count
                    - baseline_result.station_count,
                    "shared_station_count": len(
                        baseline_station_ids & scenario_station_ids
                    ),
                    "added_station_count": len(added_station_ids),
                    "removed_station_count": len(removed_station_ids),
                    "changed_station_count": len(added_station_ids)
                    + len(removed_station_ids),
                    "avg_distance_km": float(result.assignments["distance_km"].mean()),
                    "avg_effective_distance_km": float(
                        result.assignments["effective_distance_km"].mean()
                    ),
                    "max_effective_distance_km": float(
                        result.assignments["effective_distance_km"].max()
                    ),
                    "candidate_pool": result.candidate_pool,
                    "added_station_ids": "|".join(added_station_ids),
                    "removed_station_ids": "|".join(removed_station_ids),
                }
            )

            detail_map = {
                row.site_id: row
                for row in result.selected_stations.itertuples(index=False)
            }
            for station_id in sorted(scenario_station_ids | baseline_station_ids):
                station = detail_map.get(station_id)
                detail_rows.append(
                    {
                        "wind_speed_mps": wind_speed_mps,
                        "wind_speed_label": wind_speed_label,
                        "wind_direction": wind_direction,
                        "wind_direction_label": wind_direction_label,
                        "station_id": station_id,
                        "selected_in_scenario": station_id in scenario_station_ids,
                        "selected_in_baseline": station_id in baseline_station_ids,
                        "station_change": (
                            "added"
                            if station_id in scenario_station_ids
                            and station_id not in baseline_station_ids
                            else "removed"
                            if station_id in baseline_station_ids
                            and station_id not in scenario_station_ids
                            else "retained"
                        ),
                        "station_name": getattr(station, "name", ""),
                        "latitude": getattr(station, "latitude", np.nan),
                        "longitude": getattr(station, "longitude", np.nan),
                    }
                )

    return pd.DataFrame(summary_rows), pd.DataFrame(detail_rows)


def temperature_scenario_analysis(
    facilities: pd.DataFrame, settings: Settings
) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_settings = replace(settings, temperature_scenario="S1")
    baseline_result = solve_with_fallback(facilities, baseline_settings)
    baseline_station_ids = set(baseline_result.selected_stations["site_id"])
    summary_rows = []
    detail_rows = []

    for scenario in TEMPERATURE_SCENARIOS:
        scenario_settings = replace(settings, temperature_scenario=scenario.code)
        result = solve_with_fallback(facilities, scenario_settings)
        scenario_station_ids = set(result.selected_stations["site_id"])
        added_station_ids = sorted(scenario_station_ids - baseline_station_ids)
        removed_station_ids = sorted(baseline_station_ids - scenario_station_ids)

        summary_rows.append(
            {
                "temperature_scenario": scenario.code,
                "temperature_status_label": scenario.status_label,
                "temperature_range_label": scenario.ambient_range_label,
                "battery_performance_factor": scenario.battery_performance_factor,
                "effective_operation_radius_km": adjusted_operation_radius_km(
                    settings.max_operation_radius_km, scenario_settings
                ),
                "effective_mission_range_km": adjusted_mission_range_km(
                    settings.effective_mission_range_km, scenario_settings
                ),
                "station_count": result.station_count,
                "baseline_station_count": baseline_result.station_count,
                "delta_station_count": result.station_count
                - baseline_result.station_count,
                "shared_station_count": len(baseline_station_ids & scenario_station_ids),
                "added_station_count": len(added_station_ids),
                "removed_station_count": len(removed_station_ids),
                "changed_station_count": len(added_station_ids)
                + len(removed_station_ids),
                "avg_distance_km": float(result.assignments["distance_km"].mean()),
                "avg_effective_distance_km": float(
                    result.assignments["effective_distance_km"].mean()
                ),
                "max_effective_distance_km": float(
                    result.assignments["effective_distance_km"].max()
                ),
                "candidate_pool": result.candidate_pool,
                "added_station_ids": "|".join(added_station_ids),
                "removed_station_ids": "|".join(removed_station_ids),
            }
        )

        detail_map = {
            row.site_id: row for row in result.selected_stations.itertuples(index=False)
        }
        for station_id in sorted(scenario_station_ids | baseline_station_ids):
            station = detail_map.get(station_id)
            detail_rows.append(
                {
                    "temperature_scenario": scenario.code,
                    "temperature_status_label": scenario.status_label,
                    "temperature_range_label": scenario.ambient_range_label,
                    "battery_performance_factor": scenario.battery_performance_factor,
                    "station_id": station_id,
                    "selected_in_scenario": station_id in scenario_station_ids,
                    "selected_in_baseline": station_id in baseline_station_ids,
                    "station_change": (
                        "added"
                        if station_id in scenario_station_ids
                        and station_id not in baseline_station_ids
                        else "removed"
                        if station_id in baseline_station_ids
                        and station_id not in scenario_station_ids
                        else "retained"
                    ),
                    "station_name": getattr(station, "name", ""),
                    "latitude": getattr(station, "latitude", np.nan),
                    "longitude": getattr(station, "longitude", np.nan),
                }
            )

    return pd.DataFrame(summary_rows), pd.DataFrame(detail_rows)


def save_validation_outputs(
    constraints_df: pd.DataFrame,
    robustness_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    wind_summary_df: pd.DataFrame,
    wind_station_df: pd.DataFrame,
    temperature_summary_df: pd.DataFrame,
    temperature_station_df: pd.DataFrame,
    output_dir,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    constraints_df.to_csv(output_dir / "validation_constraints.csv", index=False)
    robustness_df.to_csv(output_dir / "validation_monte_carlo.csv", index=False)
    sensitivity_df.to_csv(output_dir / "validation_sensitivity.csv", index=False)
    wind_summary_df.to_csv(output_dir / "validation_wind_scenarios.csv", index=False)
    wind_station_df.to_csv(
        output_dir / "validation_wind_station_details.csv", index=False
    )
    temperature_summary_df.to_csv(
        output_dir / "validation_temperature_scenarios.csv", index=False
    )
    temperature_station_df.to_csv(
        output_dir / "validation_temperature_station_details.csv", index=False
    )
