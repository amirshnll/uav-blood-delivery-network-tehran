from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class WindScenario:
    code: str
    speed_mps: float
    flow_bearing_deg: float | None
    label_fa: str


WIND_SCENARIOS = (
    WindScenario("CALM", 0.0, None, "بدون باد"),
    WindScenario("N2S_5", 5.0, 180.0, "شمال به جنوب، ۵ متر بر ثانیه"),
    WindScenario("S2N_5", 5.0, 0.0, "جنوب به شمال، ۵ متر بر ثانیه"),
    WindScenario("E2W_5", 5.0, 270.0, "شرق به غرب، ۵ متر بر ثانیه"),
    WindScenario("W2E_5", 5.0, 90.0, "غرب به شرق، ۵ متر بر ثانیه"),
    WindScenario("N2S_10", 10.0, 180.0, "شمال به جنوب، ۱۰ متر بر ثانیه"),
    WindScenario("S2N_10", 10.0, 0.0, "جنوب به شمال، ۱۰ متر بر ثانیه"),
    WindScenario("E2W_10", 10.0, 270.0, "شرق به غرب، ۱۰ متر بر ثانیه"),
    WindScenario("W2E_10", 10.0, 90.0, "غرب به شرق، ۱۰ متر بر ثانیه"),
)


@dataclass(frozen=True)
class Settings:
    source_project_dir: Path = ROOT_DIR.parent / "paper2"
    metric_crs: str = "EPSG:32639"
    grid_resolution_m: float = 100.0
    no_fly_clearance_m: float = 100.0
    max_endpoint_snap_m: float = 400.0
    cruise_airspeed_mps: float = 15.0
    minimum_ground_speed_mps: float = 3.0
    maximum_wind_speed_mps: float = 12.0
    outbound_payload_kg: float = 18.0
    return_payload_kg: float = 3.0
    calibration_payload_kg: float = 30.0
    empty_range_km: float = 28.0
    full_payload_range_km: float = 16.0
    battery_reserve_fraction: float = 0.20
    takeoff_landing_energy_fraction: float = 0.04
    solver_time_limit_s: int = 300
    random_seed: int = 42
    results_dir: Path = ROOT_DIR / "results"
    paper_dir: Path = ROOT_DIR / "paper"

    @property
    def source_data_dir(self) -> Path:
        return self.source_project_dir / "data" / "processed"

    @property
    def facilities_path(self) -> Path:
        return self.source_data_dir / "tehran_healthcare_facilities_all.csv"

    @property
    def no_fly_path(self) -> Path:
        return self.source_data_dir / "tehran_no_fly_zones.geojson"

    @property
    def boundary_path(self) -> Path:
        return self.source_data_dir / "tehran_boundary.geojson"

    @property
    def available_cruise_energy_fraction(self) -> float:
        return (
            1.0
            - self.battery_reserve_fraction
            - self.takeoff_landing_energy_fraction
        )


DEFAULT_SETTINGS = Settings()

