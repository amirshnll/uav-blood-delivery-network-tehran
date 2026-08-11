from __future__ import annotations

import json

from .config import DEFAULT_SETTINGS, Settings
from .optimization import save_optimization_outputs, solve_with_fallback
from .osm_data import extract_tehran_healthcare_facilities, load_facilities
from .simulation import run_mission_simulation, save_simulation_outputs
from .validation import (
    monte_carlo_robustness,
    save_validation_outputs,
    sensitivity_analysis,
    validate_constraints,
)


def run_extraction(settings: Settings = DEFAULT_SETTINGS):
    return extract_tehran_healthcare_facilities(settings)


def run_optimization(settings: Settings = DEFAULT_SETTINGS):
    facilities = load_facilities(settings)
    result = solve_with_fallback(facilities, settings)
    save_optimization_outputs(result, settings.results_dir)
    return result


def run_simulation(settings: Settings = DEFAULT_SETTINGS):
    optimization_result = run_optimization(settings)
    daily_df, missions_df = run_mission_simulation(
        optimization_result.assignments, settings
    )
    save_simulation_outputs(daily_df, missions_df, settings.results_dir)
    return optimization_result, daily_df, missions_df


def run_validation(settings: Settings = DEFAULT_SETTINGS):
    facilities = load_facilities(settings)
    optimization_result = run_optimization(settings)
    constraints_df = validate_constraints(optimization_result.assignments, settings)
    robustness_df = monte_carlo_robustness(optimization_result.assignments, settings)
    sensitivity_df = sensitivity_analysis(facilities, settings)
    save_validation_outputs(
        constraints_df, robustness_df, sensitivity_df, settings.results_dir
    )
    return constraints_df, robustness_df, sensitivity_df


def run_all(settings: Settings = DEFAULT_SETTINGS) -> dict:
    facilities = run_extraction(settings)
    optimization_result = solve_with_fallback(facilities, settings)
    save_optimization_outputs(optimization_result, settings.results_dir)

    daily_df, missions_df = run_mission_simulation(
        optimization_result.assignments, settings
    )
    save_simulation_outputs(daily_df, missions_df, settings.results_dir)

    constraints_df = validate_constraints(optimization_result.assignments, settings)
    robustness_df = monte_carlo_robustness(optimization_result.assignments, settings)
    sensitivity_df = sensitivity_analysis(facilities, settings)
    save_validation_outputs(
        constraints_df, robustness_df, sensitivity_df, settings.results_dir
    )

    summary = {
        "facility_count": int(len(facilities)),
        "demand_count": int(len(optimization_result.demand_points)),
        "station_count": int(optimization_result.station_count),
        "candidate_pool": optimization_result.candidate_pool,
        "avg_missions_per_day": (
            float(daily_df["missions"].mean()) if not daily_df.empty else 0.0
        ),
        "monte_carlo_feasible_ratio_mean": (
            float(robustness_df["feasible_ratio"].mean())
            if not robustness_df.empty
            else 0.0
        ),
    }
    (settings.results_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
