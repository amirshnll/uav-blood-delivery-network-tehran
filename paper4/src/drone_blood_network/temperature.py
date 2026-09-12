from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True)
class TemperatureScenario:
    code: str
    status_label: str
    ambient_range_label: str
    battery_performance_factor: float


TEMPERATURE_SCENARIOS = (
    TemperatureScenario("S1", "دمای مطلوب", "۱۵ تا ۲۵ درجه سانتی‌گراد", 1.00),
    TemperatureScenario("S2", "دمای نسبتاً گرم", "۲۵ تا ۳۵ درجه سانتی‌گراد", 0.95),
    TemperatureScenario("S3", "دمای بسیار گرم", "۳۵ تا ۴۵ درجه سانتی‌گراد", 0.85),
    TemperatureScenario("S4", "دمای سرد", "۰ تا ۱۰ درجه سانتی‌گراد", 0.90),
    TemperatureScenario("S5", "دمای بسیار سرد", "کمتر از ۰ درجه سانتی‌گراد", 0.80),
)

TEMPERATURE_SCENARIO_MAP = {
    scenario.code: scenario for scenario in TEMPERATURE_SCENARIOS
}


def resolve_temperature_scenario(settings: Settings) -> TemperatureScenario:
    return TEMPERATURE_SCENARIO_MAP.get(
        settings.temperature_scenario.upper(), TEMPERATURE_SCENARIO_MAP["S1"]
    )


def battery_performance_factor(settings: Settings) -> float:
    return resolve_temperature_scenario(settings).battery_performance_factor


def temperature_distance_multiplier(settings: Settings) -> float:
    factor = battery_performance_factor(settings)
    if factor <= 0:
        raise ValueError("Temperature battery performance factor must be positive.")
    return 1.0 / factor


def adjusted_operation_radius_km(base_radius_km: float, settings: Settings) -> float:
    return base_radius_km * battery_performance_factor(settings)


def adjusted_mission_range_km(base_range_km: float, settings: Settings) -> float:
    return base_range_km * battery_performance_factor(settings)
