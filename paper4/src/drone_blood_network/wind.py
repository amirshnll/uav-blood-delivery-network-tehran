from __future__ import annotations

from math import atan2, cos, degrees, radians, sin

from .config import Settings


WIND_SPEED_SCENARIOS = (
    (2.0, "باد ملایم"),
    (5.0, "باد متوسط"),
    (8.0, "باد نسبتاً شدید"),
    (10.0, "مرز بالای سناریوی سخت"),
)

WIND_DIRECTION_SCENARIOS = (
    ("north_to_south", "شمال به جنوب"),
    ("south_to_north", "جنوب به شمال"),
    ("east_to_west", "شرق به غرب"),
    ("west_to_east", "غرب به شرق"),
)

WIND_DIRECTION_BEARINGS = {
    "calm": None,
    "north_to_south": 180.0,
    "south_to_north": 0.0,
    "east_to_west": 270.0,
    "west_to_east": 90.0,
}


def initial_bearing_degrees(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    dlon_rad = radians(lon2 - lon1)
    y = sin(dlon_rad) * cos(lat2_rad)
    x = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(
        dlon_rad
    )
    return (degrees(atan2(y, x)) + 360.0) % 360.0


def _wind_intensity(settings: Settings) -> float:
    if settings.wind_speed_mps <= 0 or settings.wind_reference_speed_mps <= 0:
        return 0.0
    return min(settings.wind_speed_mps / settings.wind_reference_speed_mps, 1.5)


def wind_alignment(route_bearing_deg: float, direction: str) -> float:
    wind_bearing = WIND_DIRECTION_BEARINGS.get(direction)
    if wind_bearing is None:
        return 0.0
    delta_deg = ((route_bearing_deg - wind_bearing + 180.0) % 360.0) - 180.0
    return cos(radians(delta_deg))


def effective_distance_multiplier(
    route_bearing_deg: float, settings: Settings
) -> tuple[float, float]:
    intensity = _wind_intensity(settings)
    if intensity == 0.0:
        return 1.0, 0.0

    alignment = wind_alignment(route_bearing_deg, settings.wind_direction)
    headwind_factor = (1.0 - alignment) / 2.0
    tailwind_factor = max(alignment, 0.0)
    multiplier = 1.0
    multiplier += settings.wind_speed_impact_on_radius * intensity * headwind_factor
    multiplier -= settings.wind_tailwind_bonus_on_radius * intensity * tailwind_factor
    return max(0.75, multiplier), alignment


def effective_cruise_speed_mps(
    base_speed_mps: float, route_bearing_deg: float, settings: Settings
) -> tuple[float, float]:
    intensity = _wind_intensity(settings)
    if intensity == 0.0:
        return base_speed_mps, 0.0

    alignment = wind_alignment(route_bearing_deg, settings.wind_direction)
    headwind_factor = (1.0 - alignment) / 2.0
    tailwind_factor = max(alignment, 0.0)
    speed_multiplier = 1.0
    speed_multiplier -= settings.wind_speed_impact_on_cruise * intensity * headwind_factor
    speed_multiplier += settings.wind_tailwind_bonus_on_speed * intensity * tailwind_factor
    adjusted_speed = max(settings.minimum_cruise_speed_mps, base_speed_mps * speed_multiplier)
    return adjusted_speed, alignment
