from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    project_name: str = os.getenv("PROJECT_NAME", "drone_blood_network")
    osm_place_name: str = os.getenv("OSM_PLACE_NAME", "Tehran, Tehran Province, Iran")
    max_operation_radius_km: float = float(os.getenv("MAX_OPERATION_RADIUS_KM", "6.0"))
    effective_mission_range_km: float = float(
        os.getenv("EFFECTIVE_MISSION_RANGE_KM", "12.0")
    )
    cruise_speed_mps: float = float(os.getenv("CRUISE_SPEED_MPS", "15.0"))
    max_payload_kg: float = float(os.getenv("MAX_PAYLOAD_KG", "30.0"))
    base_payload_kg: float = float(os.getenv("BASE_PAYLOAD_KG", "18.0"))
    handling_time_min: float = float(os.getenv("HANDLING_TIME_MIN", "6.0"))
    simulation_days: int = int(os.getenv("SIMULATION_DAYS", "30"))
    monte_carlo_runs: int = int(os.getenv("MONTE_CARLO_RUNS", "200"))
    random_seed: int = int(os.getenv("RANDOM_SEED", "42"))
    temperature_scenario: str = os.getenv("TEMPERATURE_SCENARIO", "S1").upper()
    wind_speed_mps: float = float(os.getenv("WIND_SPEED_MPS", "0.0"))
    wind_direction: str = os.getenv("WIND_DIRECTION", "calm")
    wind_reference_speed_mps: float = float(
        os.getenv("WIND_REFERENCE_SPEED_MPS", "10.0")
    )
    wind_speed_impact_on_radius: float = float(
        os.getenv("WIND_SPEED_IMPACT_ON_RADIUS", "0.35")
    )
    wind_tailwind_bonus_on_radius: float = float(
        os.getenv("WIND_TAILWIND_BONUS_ON_RADIUS", "0.10")
    )
    wind_speed_impact_on_cruise: float = float(
        os.getenv("WIND_SPEED_IMPACT_ON_CRUISE", "0.30")
    )
    wind_tailwind_bonus_on_speed: float = float(
        os.getenv("WIND_TAILWIND_BONUS_ON_SPEED", "0.12")
    )
    minimum_cruise_speed_mps: float = float(
        os.getenv("MINIMUM_CRUISE_SPEED_MPS", "8.0")
    )
    no_fly_site_buffer_m: float = float(os.getenv("NO_FLY_SITE_BUFFER_M", "150.0"))
    airport_buffer_m: float = float(os.getenv("AIRPORT_BUFFER_M", "3000.0"))
    data_dir: Path = ROOT_DIR / os.getenv("DATA_DIR", "data")
    results_dir: Path = ROOT_DIR / os.getenv("RESULTS_DIR", "results")

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


DEFAULT_SETTINGS = Settings()
