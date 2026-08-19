from __future__ import annotations

import argparse
import json

from .pipeline import (
    run_all,
    run_extraction,
    run_optimization,
    run_simulation,
    run_validation,
    run_wind_analysis,
)


COMMANDS = {"extract", "optimize", "simulate", "validate", "wind-analysis", "run-all"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Tehran drone blood network pipeline")
    parser.add_argument(
        "command", choices=sorted(COMMANDS), help="Pipeline stage to execute"
    )
    args = parser.parse_args()

    if args.command == "extract":
        facilities = run_extraction()
        print(json.dumps({"facility_count": len(facilities)}, indent=2))
    elif args.command == "optimize":
        result = run_optimization()
        print(
            json.dumps(
                {
                    "station_count": result.station_count,
                    "candidate_pool": result.candidate_pool,
                },
                indent=2,
            )
        )
    elif args.command == "simulate":
        result, daily_df, missions_df = run_simulation()
        print(
            json.dumps(
                {
                    "station_count": result.station_count,
                    "daily_records": len(daily_df),
                    "mission_records": len(missions_df),
                },
                indent=2,
            )
        )
    elif args.command == "validate":
        constraints_df, robustness_df, sensitivity_df, wind_summary_df, _ = run_validation()
        print(
            json.dumps(
                {
                    "constraint_checks": constraints_df.to_dict(orient="records"),
                    "monte_carlo_runs": len(robustness_df),
                    "sensitivity_rows": len(sensitivity_df),
                    "wind_scenarios": len(wind_summary_df),
                },
                indent=2,
            )
        )
    elif args.command == "wind-analysis":
        wind_summary_df, wind_station_df = run_wind_analysis()
        print(
            json.dumps(
                {
                    "wind_scenarios": len(wind_summary_df),
                    "station_detail_rows": len(wind_station_df),
                    "station_count_min": int(wind_summary_df["station_count"].min()),
                    "station_count_max": int(wind_summary_df["station_count"].max()),
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(run_all(), indent=2))


if __name__ == "__main__":
    main()
