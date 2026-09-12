from dataclasses import replace

import geopandas as gpd
import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from drone_blood_network.config import Settings, WindScenario
from drone_blood_network.energy import (
    energy_per_km_at_payload,
    ground_speed_along_track_mps,
    sortie_energy_per_km,
)
from drone_blood_network.routing import (
    RoutingGrid,
    dijkstra_energy,
    reconstruct_path,
)


def test_payload_energy_calibration_matches_official_range_anchors():
    settings = Settings()
    assert energy_per_km_at_payload(0.0, settings) == 1.0 / 28.0
    assert energy_per_km_at_payload(30.0, settings) == 1.0 / 16.0


def test_calm_round_trip_energy_includes_loaded_and_light_legs():
    settings = Settings()
    calm = WindScenario("CALM", 0.0, None, "calm")
    result = sortie_energy_per_km(0.0, calm, settings)
    expected = energy_per_km_at_payload(18.0, settings) + energy_per_km_at_payload(
        3.0, settings
    )
    assert abs(result.energy_per_km - expected) < 1e-12


def test_wind_is_evaluated_separately_for_loaded_outbound_and_return():
    settings = Settings()
    southward = WindScenario("N2S", 8.0, 180.0, "N to S")
    south_delivery = sortie_energy_per_km(180.0, southward, settings)
    north_delivery = sortie_energy_per_km(0.0, southward, settings)
    assert south_delivery.energy_per_km < north_delivery.energy_per_km
    assert south_delivery.outbound_ground_speed_mps > south_delivery.return_ground_speed_mps


def test_crosswind_reduces_along_track_ground_speed():
    settings = Settings()
    eastward_wind = WindScenario("W2E", 8.0, 90.0, "W to E")
    speed = ground_speed_along_track_mps(0.0, eastward_wind, settings)
    assert speed is not None
    assert speed < settings.cruise_airspeed_mps


def test_grid_dijkstra_detours_around_blocked_cells():
    free = np.ones((9, 9), dtype=bool)
    free[1:8, 4] = False
    grid = RoutingGrid(
        free=free,
        transform=from_origin(0.0, 900.0, 100.0, 100.0),
        resolution_m=100.0,
        crs="EPSG:32639",
    )
    settings = replace(
        Settings(),
        grid_resolution_m=100.0,
        battery_reserve_fraction=0.0,
        takeoff_landing_energy_fraction=0.0,
    )
    calm = WindScenario("CALM", 0.0, None, "calm")
    start = (4, 1)
    target = (4, 7)
    search = dijkstra_energy(
        grid, start, {target}, calm, settings, keep_predecessors=True
    )
    assert target in search.energy
    assert search.distance_m[target] > 600.0
    assert search.predecessor is not None
    path = reconstruct_path(grid, start, target, search.predecessor)
    obstacle = Polygon([(400, 100), (500, 100), (500, 800), (400, 800)])
    assert path is not None
    assert not path.crosses(obstacle)

