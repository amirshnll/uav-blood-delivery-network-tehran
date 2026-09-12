from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin, sqrt

from .config import Settings, WindScenario


@dataclass(frozen=True)
class DirectionalEnergy:
    energy_per_km: float
    outbound_ground_speed_mps: float
    return_ground_speed_mps: float
    feasible: bool


def energy_per_km_at_payload(payload_kg: float, settings: Settings) -> float:
    """Calibrate normalized battery use per km by linear interpolation.

    Official dual-battery ranges provide the two calibration anchors: empty
    range and range at the rated calibration payload. Extrapolation above the
    rated payload is intentionally rejected by clipping at the rated payload.
    """

    payload_fraction = min(max(payload_kg, 0.0), settings.calibration_payload_kg)
    payload_fraction /= settings.calibration_payload_kg
    empty_rate = 1.0 / settings.empty_range_km
    full_rate = 1.0 / settings.full_payload_range_km
    return empty_rate + payload_fraction * (full_rate - empty_rate)


def ground_speed_along_track_mps(
    track_bearing_deg: float,
    scenario: WindScenario,
    settings: Settings,
) -> float | None:
    """Ground speed while maintaining track at a fixed cruise airspeed.

    Bearings are clockwise from north. ``flow_bearing_deg`` describes where
    the wind is going (e.g. 180 degrees means a north-to-south flow).
    """

    if scenario.speed_mps > settings.maximum_wind_speed_mps:
        return None
    if scenario.speed_mps <= 0 or scenario.flow_bearing_deg is None:
        return settings.cruise_airspeed_mps

    delta = radians(scenario.flow_bearing_deg - track_bearing_deg)
    wind_along = scenario.speed_mps * cos(delta)
    wind_cross = scenario.speed_mps * sin(delta)
    if abs(wind_cross) >= settings.cruise_airspeed_mps:
        return None
    along_air_component = sqrt(
        max(settings.cruise_airspeed_mps**2 - wind_cross**2, 0.0)
    )
    ground_speed = along_air_component + wind_along
    if ground_speed < settings.minimum_ground_speed_mps:
        return None
    return ground_speed


def sortie_energy_per_km(
    outbound_bearing_deg: float,
    scenario: WindScenario,
    settings: Settings,
) -> DirectionalEnergy:
    """Normalized round-trip battery use for one km of outbound path.

    The outbound leg carries blood and packaging. The return leg follows the
    same segment in reverse and carries only the reusable container. At fixed
    airspeed, energy per ground-km scales inversely with ground speed.
    """

    out_speed = ground_speed_along_track_mps(
        outbound_bearing_deg, scenario, settings
    )
    return_speed = ground_speed_along_track_mps(
        (outbound_bearing_deg + 180.0) % 360.0, scenario, settings
    )
    if out_speed is None or return_speed is None:
        return DirectionalEnergy(float("inf"), 0.0, 0.0, False)

    outbound_rate = energy_per_km_at_payload(settings.outbound_payload_kg, settings)
    return_rate = energy_per_km_at_payload(settings.return_payload_kg, settings)
    reference_speed = settings.cruise_airspeed_mps
    energy_per_km = (
        outbound_rate * reference_speed / out_speed
        + return_rate * reference_speed / return_speed
    )
    return DirectionalEnergy(energy_per_km, out_speed, return_speed, True)

