from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

from .config import Settings


@dataclass
class StudyData:
    facilities: gpd.GeoDataFrame
    demands: gpd.GeoDataFrame
    drone_eligible_demands: gpd.GeoDataFrame
    restricted_demands: gpd.GeoDataFrame
    candidates: gpd.GeoDataFrame
    no_fly_zones: gpd.GeoDataFrame
    boundary: gpd.GeoDataFrame
    accessibility: pd.DataFrame


def _flag_points_in_zones(
    points: gpd.GeoDataFrame, zones: gpd.GeoDataFrame
) -> pd.Series:
    if points.empty or zones.empty:
        return pd.Series(False, index=points.index, dtype=bool)
    joined = gpd.sjoin(
        points[["geometry"]], zones[["geometry"]], how="left", predicate="intersects"
    )
    blocked_indices = set(joined.index[joined["index_right"].notna()])
    return pd.Series(points.index.isin(blocked_indices), index=points.index)


def load_study_data(settings: Settings) -> StudyData:
    facilities_df = pd.read_csv(settings.facilities_path)
    if "facility_id" not in facilities_df:
        facilities_df["facility_id"] = facilities_df.index
    facilities_df["site_id"] = facilities_df["facility_id"].map(
        lambda value: f"facility_{int(value)}"
    )
    facilities = gpd.GeoDataFrame(
        facilities_df,
        geometry=gpd.points_from_xy(
            facilities_df["longitude"], facilities_df["latitude"]
        ),
        crs="EPSG:4326",
    ).to_crs(settings.metric_crs)
    zones = gpd.read_file(settings.no_fly_path).to_crs(settings.metric_crs)
    zones = zones[zones.geometry.notna() & ~zones.geometry.is_empty].copy()
    boundary = gpd.read_file(settings.boundary_path).to_crs(settings.metric_crs)

    facilities["inside_no_fly_zone"] = _flag_points_in_zones(facilities, zones)
    demands = facilities[facilities["is_demand_point"].astype(bool)].copy()
    restricted_demands = demands[demands["inside_no_fly_zone"]].copy()
    eligible_demands = demands[~demands["inside_no_fly_zone"]].copy()
    candidates = facilities[
        facilities["is_candidate_station"].astype(bool)
        & ~facilities["inside_no_fly_zone"]
    ].copy()

    accessibility = demands[
        [
            "site_id",
            "name",
            "facility_category",
            "latitude",
            "longitude",
            "inside_no_fly_zone",
        ]
    ].copy()
    accessibility["drone_access_class"] = accessibility[
        "inside_no_fly_zone"
    ].map(
        {
            False: "eligible_for_obstacle_safe_drone_routing",
            True: "requires_special_authorization_or_ground_handoff",
        }
    )

    return StudyData(
        facilities=facilities,
        demands=demands,
        drone_eligible_demands=eligible_demands,
        restricted_demands=restricted_demands,
        candidates=candidates,
        no_fly_zones=zones,
        boundary=boundary,
        accessibility=accessibility,
    )

