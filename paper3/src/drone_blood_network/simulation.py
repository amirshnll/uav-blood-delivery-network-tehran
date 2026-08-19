from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Settings
from .wind import effective_cruise_speed_mps


CATEGORY_WEIGHTS = {
    "hospital": 1.0,
    "clinic": 0.55,
    "doctor": 0.35,
    "doctors": 0.35,
    "laboratory": 0.45,
    "unknown": 0.25,
}


def _category_weight(category: str) -> float:
    return CATEGORY_WEIGHTS.get(str(category).lower(), 0.3)


def run_mission_simulation(
    assignments: pd.DataFrame, settings: Settings
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(settings.random_seed)
    simulated_days = []
    mission_rows = []
    cruise_speed_km_min = settings.cruise_speed_mps * 60.0 / 1000.0

    for _, row in assignments.iterrows():
        demand_rate = _category_weight(row.get("facility_category", "unknown"))
        for day in range(1, settings.simulation_days + 1):
            missions = int(rng.poisson(demand_rate))
            round_trip_distance_km = float(row["distance_km"]) * 2.0
            adjusted_speed_mps, wind_alignment = effective_cruise_speed_mps(
                settings.cruise_speed_mps,
                float(row.get("route_bearing_deg", 0.0)),
                settings,
            )
            cruise_speed_km_min = adjusted_speed_mps * 60.0 / 1000.0
            flight_time_min = (
                round_trip_distance_km / cruise_speed_km_min
                if cruise_speed_km_min
                else 0.0
            )
            total_time_min = flight_time_min + settings.handling_time_min
            utilization = round_trip_distance_km / settings.effective_mission_range_km

            simulated_days.append(
                {
                    "day": day,
                    "demand_site_id": row["site_id"],
                    "facility_name": row.get("name", "unnamed"),
                    "facility_category": row.get("facility_category", "unknown"),
                    "assigned_station_id": row["assigned_station_id"],
                    "missions": missions,
                    "one_way_distance_km": row["distance_km"],
                    "round_trip_distance_km": round_trip_distance_km,
                    "estimated_total_time_min": total_time_min,
                    "battery_utilization": utilization,
                    "payload_kg": settings.base_payload_kg,
                    "effective_cruise_speed_mps": adjusted_speed_mps,
                    "wind_alignment": wind_alignment,
                    "wind_speed_mps": settings.wind_speed_mps,
                    "wind_direction": settings.wind_direction,
                }
            )

            for mission_no in range(missions):
                mission_rows.append(
                    {
                        "day": day,
                        "mission_no": mission_no + 1,
                        "demand_site_id": row["site_id"],
                        "assigned_station_id": row["assigned_station_id"],
                        "round_trip_distance_km": round_trip_distance_km,
                        "estimated_total_time_min": total_time_min,
                        "battery_utilization": utilization,
                        "payload_kg": settings.base_payload_kg,
                        "effective_cruise_speed_mps": adjusted_speed_mps,
                        "wind_alignment": wind_alignment,
                        "wind_speed_mps": settings.wind_speed_mps,
                        "wind_direction": settings.wind_direction,
                        "within_payload_limit": settings.base_payload_kg
                        <= settings.max_payload_kg,
                        "within_range_limit": round_trip_distance_km
                        <= settings.effective_mission_range_km,
                    }
                )

    daily_df = pd.DataFrame(simulated_days)
    missions_df = pd.DataFrame(mission_rows)
    return daily_df, missions_df


def save_simulation_outputs(
    daily_df: pd.DataFrame, missions_df: pd.DataFrame, output_dir
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_df.to_csv(output_dir / "simulation_daily_summary.csv", index=False)
    missions_df.to_csv(output_dir / "simulation_missions.csv", index=False)
