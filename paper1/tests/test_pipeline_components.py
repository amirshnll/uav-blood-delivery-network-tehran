import pandas as pd

from drone_blood_network.config import Settings
from drone_blood_network.optimization import haversine_km, solve_set_cover
from drone_blood_network.simulation import run_mission_simulation
from drone_blood_network.validation import validate_constraints


def synthetic_facilities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": "Hospital A",
                "facility_category": "hospital",
                "is_demand_point": True,
                "is_candidate_station": True,
                "latitude": 35.7000,
                "longitude": 51.3900,
            },
            {
                "name": "Clinic B",
                "facility_category": "clinic",
                "is_demand_point": True,
                "is_candidate_station": False,
                "latitude": 35.7200,
                "longitude": 51.4100,
            },
            {
                "name": "Hospital C",
                "facility_category": "hospital",
                "is_demand_point": True,
                "is_candidate_station": True,
                "latitude": 35.6800,
                "longitude": 51.3500,
            },
        ]
    )


def test_haversine_is_zero_for_same_point():
    assert haversine_km(35.7, 51.4, 35.7, 51.4) == 0


def test_set_cover_finds_feasible_solution():
    settings = Settings(max_operation_radius_km=6.0)
    result = solve_set_cover(
        synthetic_facilities(), settings, use_all_as_candidates=False
    )
    assert result.station_count >= 1
    assert result.assignments["assigned_station_id"].notna().all()


def test_simulation_and_validation_constraints():
    settings = Settings(
        max_operation_radius_km=6.0, simulation_days=3, monte_carlo_runs=5
    )
    result = solve_set_cover(
        synthetic_facilities(), settings, use_all_as_candidates=False
    )
    daily_df, missions_df = run_mission_simulation(result.assignments, settings)
    constraints_df = validate_constraints(result.assignments, settings)
    assert len(daily_df) == len(result.assignments) * settings.simulation_days
    assert "within_range_limit" in missions_df.columns or missions_df.empty
    assert constraints_df.loc[0, "all_demands_assigned"]
