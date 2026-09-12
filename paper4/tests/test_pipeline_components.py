import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from drone_blood_network.config import Settings
from drone_blood_network.osm_data import _filter_facilities_by_no_fly_zones
from drone_blood_network.optimization import haversine_km, solve_set_cover
from drone_blood_network.simulation import run_mission_simulation
from drone_blood_network.validation import (
    temperature_scenario_analysis,
    validate_constraints,
    wind_scenario_analysis,
)


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


def wind_sensitive_facilities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": "Central Hub",
                "facility_category": "hospital",
                "is_demand_point": False,
                "is_candidate_station": True,
                "latitude": 35.7000,
                "longitude": 51.4000,
            },
            {
                "name": "North Hub",
                "facility_category": "hospital",
                "is_demand_point": False,
                "is_candidate_station": True,
                "latitude": 35.7450,
                "longitude": 51.4000,
            },
            {
                "name": "North Clinic",
                "facility_category": "clinic",
                "is_demand_point": True,
                "is_candidate_station": False,
                "latitude": 35.7450,
                "longitude": 51.4000,
            },
            {
                "name": "South Clinic",
                "facility_category": "clinic",
                "is_demand_point": True,
                "is_candidate_station": False,
                "latitude": 35.6550,
                "longitude": 51.4000,
            },
        ]
    )


def temperature_sensitive_facilities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": "Central Hub",
                "facility_category": "hospital",
                "is_demand_point": False,
                "is_candidate_station": True,
                "latitude": 35.7000,
                "longitude": 51.4000,
            },
            {
                "name": "North Hub",
                "facility_category": "hospital",
                "is_demand_point": False,
                "is_candidate_station": True,
                "latitude": 35.7520,
                "longitude": 51.4000,
            },
            {
                "name": "South Hub",
                "facility_category": "hospital",
                "is_demand_point": False,
                "is_candidate_station": True,
                "latitude": 35.6480,
                "longitude": 51.4000,
            },
            {
                "name": "North Clinic",
                "facility_category": "clinic",
                "is_demand_point": True,
                "is_candidate_station": False,
                "latitude": 35.7520,
                "longitude": 51.4000,
            },
            {
                "name": "South Clinic",
                "facility_category": "clinic",
                "is_demand_point": True,
                "is_candidate_station": False,
                "latitude": 35.6480,
                "longitude": 51.4000,
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
    assert "effective_cruise_speed_mps" in daily_df.columns
    assert constraints_df.loc[0, "all_demands_assigned"]


def test_no_fly_filter_excludes_facilities_inside_restricted_zones():
    facilities = pd.DataFrame(
        [
            {
                "name": "Inside Zone",
                "facility_category": "hospital",
                "is_demand_point": True,
                "is_candidate_station": True,
                "latitude": 35.7000,
                "longitude": 51.4000,
            },
            {
                "name": "Outside Zone",
                "facility_category": "clinic",
                "is_demand_point": True,
                "is_candidate_station": False,
                "latitude": 35.7400,
                "longitude": 51.4600,
            },
        ]
    )
    no_fly_zones = gpd.GeoDataFrame(
        [
            {
                "name": "Restricted Area",
                "no_fly_category": "military_security",
                "geometry": Polygon(
                    [
                        (51.3950, 35.6950),
                        (51.4050, 35.6950),
                        (51.4050, 35.7050),
                        (51.3950, 35.7050),
                    ]
                ),
            }
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )

    filtered, facilities_with_flags = _filter_facilities_by_no_fly_zones(
        facilities, no_fly_zones
    )

    assert filtered["name"].tolist() == ["Outside Zone"]
    assert facilities_with_flags["in_no_fly_zone"].tolist() == [True, False]
    assert (
        facilities_with_flags.loc[0, "no_fly_categories"] == "military_security"
    )


def test_wind_scenario_can_increase_station_count_for_headwind_routes():
    baseline_settings = Settings(max_operation_radius_km=6.0)
    baseline_result = solve_set_cover(
        wind_sensitive_facilities(), baseline_settings, use_all_as_candidates=False
    )
    stressed_settings = Settings(
        max_operation_radius_km=6.0,
        wind_speed_mps=10.0,
        wind_direction="north_to_south",
    )
    stressed_result = solve_set_cover(
        wind_sensitive_facilities(), stressed_settings, use_all_as_candidates=False
    )

    assert baseline_result.station_count == 1
    assert stressed_result.station_count == 2
    assert baseline_result.selected_stations["name"].tolist() == ["Central Hub"]
    assert set(stressed_result.selected_stations["name"]) == {"Central Hub", "North Hub"}


def test_wind_scenario_analysis_generates_all_speed_direction_combinations():
    summary_df, details_df = wind_scenario_analysis(
        wind_sensitive_facilities(),
        Settings(max_operation_radius_km=6.0),
    )

    assert len(summary_df) == 16
    assert {
        "wind_speed_mps",
        "wind_direction",
        "delta_station_count",
        "changed_station_count",
    }.issubset(summary_df.columns)
    assert not details_df.empty


def test_temperature_scenario_reduces_effective_range_and_requires_more_stations():
    baseline_settings = Settings(max_operation_radius_km=6.0, temperature_scenario="S1")
    baseline_result = solve_set_cover(
        temperature_sensitive_facilities(),
        baseline_settings,
        use_all_as_candidates=False,
    )
    stressed_settings = Settings(max_operation_radius_km=6.0, temperature_scenario="S2")
    stressed_result = solve_set_cover(
        temperature_sensitive_facilities(),
        stressed_settings,
        use_all_as_candidates=False,
    )

    assert baseline_result.station_count == 1
    assert stressed_result.station_count == 2
    assert baseline_result.selected_stations["name"].tolist() == ["Central Hub"]
    assert set(stressed_result.selected_stations["name"]) == {"North Hub", "South Hub"}


def test_temperature_scenario_analysis_generates_all_temperature_cases():
    summary_df, details_df = temperature_scenario_analysis(
        temperature_sensitive_facilities(),
        Settings(max_operation_radius_km=6.0),
    )

    assert len(summary_df) == 5
    assert {
        "temperature_scenario",
        "battery_performance_factor",
        "effective_operation_radius_km",
        "delta_station_count",
    }.issubset(summary_df.columns)
    assert not details_df.empty
