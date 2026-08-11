from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Settings
from .optimization import solve_set_cover


def validate_constraints(assignments: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    checks = {
        "all_demands_assigned": bool(assignments["assigned_station_id"].notna().all()),
        "all_within_radius": bool(
            (assignments["distance_km"] <= settings.max_operation_radius_km).all()
        ),
        "all_within_round_trip_range": bool(
            (
                assignments["distance_km"] * 2 <= settings.effective_mission_range_km
            ).all()
        ),
        "payload_within_limit": settings.base_payload_kg <= settings.max_payload_kg,
    }
    return pd.DataFrame([checks])


def monte_carlo_robustness(
    assignments: pd.DataFrame, settings: Settings
) -> pd.DataFrame:
    rng = np.random.default_rng(settings.random_seed)
    rows = []
    for run_id in range(1, settings.monte_carlo_runs + 1):
        wind_penalty = rng.uniform(0.85, 1.0)
        speed_penalty = rng.uniform(0.8, 1.0)
        stressed_radius = settings.max_operation_radius_km * wind_penalty
        stressed_range = settings.effective_mission_range_km * wind_penalty
        stressed_speed = settings.cruise_speed_mps * speed_penalty
        feasible_ratio = float((assignments["distance_km"] <= stressed_radius).mean())
        avg_service_min = float(
            (
                (assignments["distance_km"] * 2) / (stressed_speed * 60.0 / 1000.0)
                + settings.handling_time_min
            ).mean()
        )
        rows.append(
            {
                "run_id": run_id,
                "stressed_radius_km": stressed_radius,
                "stressed_range_km": stressed_range,
                "stressed_speed_mps": stressed_speed,
                "feasible_ratio": feasible_ratio,
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
        scenario_settings = Settings(
            project_name=settings.project_name,
            osm_place_name=settings.osm_place_name,
            max_operation_radius_km=radius,
            effective_mission_range_km=max(
                radius * 2, settings.effective_mission_range_km
            ),
            cruise_speed_mps=settings.cruise_speed_mps,
            max_payload_kg=settings.max_payload_kg,
            base_payload_kg=settings.base_payload_kg,
            handling_time_min=settings.handling_time_min,
            simulation_days=settings.simulation_days,
            monte_carlo_runs=settings.monte_carlo_runs,
            random_seed=settings.random_seed,
            data_dir=settings.data_dir,
            results_dir=settings.results_dir,
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


def save_validation_outputs(
    constraints_df: pd.DataFrame,
    robustness_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    output_dir,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    constraints_df.to_csv(output_dir / "validation_constraints.csv", index=False)
    robustness_df.to_csv(output_dir / "validation_monte_carlo.csv", index=False)
    sensitivity_df.to_csv(output_dir / "validation_sensitivity.csv", index=False)
