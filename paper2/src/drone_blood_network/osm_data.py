from __future__ import annotations

import json

import geopandas as gpd
import osmnx as ox
import pandas as pd

from .config import Settings


DEMAND_CATEGORIES = {"hospital", "clinic", "doctors", "doctor", "laboratory"}
PREFERRED_STATION_CATEGORIES = {
    "hospital",
    "ambulance_station",
    "blood_donation",
    "blood_bank",
}
NO_FLY_ZONE_SPECS = (
    (
        "military_security",
        "military and security sites",
        {"landuse": "military", "military": True},
        "feature_only",
    ),
    (
        "government_political",
        "government and political sites",
        {
            "office": "government",
            "building": "government",
            "amenity": ["embassy", "courthouse", "townhall"],
        },
        "feature_only",
    ),
    (
        "critical_infrastructure",
        "critical infrastructure",
        {
            "power": ["plant", "substation", "generator", "transformer"],
            "man_made": [
                "water_works",
                "wastewater_plant",
                "reservoir_covered",
                "storage_tank",
                "water_tower",
            ],
        },
        "feature_only",
    ),
    (
        "airport_buffer",
        "airport surroundings",
        {"aeroway": ["aerodrome", "runway"]},
        "buffer_all",
    ),
    (
        "protected_environment",
        "protected environmental areas",
        {"boundary": "protected_area", "leisure": "nature_reserve", "protect_class": True},
        "feature_only",
    ),
)
OVERPASS_URL_CANDIDATES = (
    "https://overpass-api.de/api",
    "https://overpass.private.coffee/api",
    "https://overpass.kumi.systems/api",
)


def _classify_facility(row: pd.Series) -> str:
    for key in ("amenity", "healthcare"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "unknown"


def _geometry_to_point(geometry):
    geom_type = getattr(geometry, "geom_type", "")
    if geom_type == "Point":
        return geometry
    if geom_type in {"Polygon", "MultiPolygon", "LineString", "MultiLineString"}:
        return geometry.centroid
    return geometry.representative_point()


def _normalize_name(values: pd.Series, fallback: str) -> pd.Series:
    return values.fillna(fallback).astype(str).str.strip().replace("", fallback)


def _empty_no_fly_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        columns=["name", "no_fly_category", "no_fly_description", "geometry"],
        geometry="geometry",
        crs="EPSG:4326",
    )


def _features_from_polygon_with_fallback(polygon, tags):
    original_url = ox.settings.overpass_url
    last_error = None
    candidate_urls = [original_url, *OVERPASS_URL_CANDIDATES]

    for overpass_url in dict.fromkeys(candidate_urls):
        ox.settings.overpass_url = overpass_url
        try:
            response = ox.features_from_polygon(polygon, tags=tags)
            ox.settings.overpass_url = original_url
            return response
        except Exception as exc:  # pragma: no cover - network-dependent fallback
            last_error = exc

    ox.settings.overpass_url = original_url
    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to query Overpass for OSM features.")


def _build_no_fly_zones(city_gdf: gpd.GeoDataFrame, settings: Settings) -> gpd.GeoDataFrame:
    city_polygon = city_gdf.geometry.iloc[0]
    metric_crs = city_gdf.estimate_utm_crs()
    zone_frames: list[gpd.GeoDataFrame] = []

    for category, description, tags, geometry_mode in NO_FLY_ZONE_SPECS:
        features = _features_from_polygon_with_fallback(
            city_polygon, tags=tags
        ).reset_index()
        if features.empty:
            continue

        features_gdf = gpd.GeoDataFrame(features, geometry="geometry", crs="EPSG:4326")
        features_gdf = features_gdf[features_gdf.geometry.notna()].copy()
        if features_gdf.empty:
            continue

        features_gdf["name"] = _normalize_name(
            features_gdf.get("name", pd.Series(index=features_gdf.index, dtype="object")),
            fallback=category,
        )
        metric_gdf = features_gdf.to_crs(metric_crs)
        if geometry_mode == "buffer_all":
            metric_gdf["geometry"] = metric_gdf.geometry.buffer(settings.airport_buffer_m)
        else:
            area_mask = metric_gdf.geom_type.isin(["Polygon", "MultiPolygon"])
            metric_gdf.loc[~area_mask, "geometry"] = metric_gdf.loc[
                ~area_mask, "geometry"
            ].buffer(settings.no_fly_site_buffer_m)

        metric_gdf = metric_gdf[metric_gdf.geometry.notna()].copy()
        metric_gdf = metric_gdf[~metric_gdf.geometry.is_empty].copy()
        if metric_gdf.empty:
            continue

        zone_frames.append(
            metric_gdf[
                [col for col in ["name", "geometry"] if col in metric_gdf.columns]
            ]
            .assign(
                no_fly_category=category,
                no_fly_description=description,
            )
            .to_crs("EPSG:4326")
        )

    if not zone_frames:
        return _empty_no_fly_gdf()
    return (
        pd.concat(zone_frames, ignore_index=True)
        .pipe(lambda frame: gpd.GeoDataFrame(frame, geometry="geometry", crs="EPSG:4326"))
    )


def _filter_facilities_by_no_fly_zones(
    dataset: pd.DataFrame, no_fly_zones: gpd.GeoDataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    facilities_gdf = gpd.GeoDataFrame(
        dataset.reset_index(drop=True).copy(),
        geometry=gpd.points_from_xy(dataset["longitude"], dataset["latitude"]),
        crs="EPSG:4326",
    )
    facilities_gdf["facility_id"] = facilities_gdf.index.astype(int)

    if no_fly_zones.empty:
        facilities_gdf["no_fly_categories"] = ""
        facilities_gdf["in_no_fly_zone"] = False
    else:
        joined = gpd.sjoin(
            facilities_gdf[["facility_id", "geometry"]],
            no_fly_zones[["no_fly_category", "geometry"]],
            how="left",
            predicate="intersects",
        )
        category_map = (
            joined.dropna(subset=["no_fly_category"])
            .groupby("facility_id")["no_fly_category"]
            .agg(lambda values: "|".join(sorted(set(map(str, values)))))
        )
        facilities_gdf["no_fly_categories"] = (
            facilities_gdf["facility_id"].map(category_map).fillna("")
        )
        facilities_gdf["in_no_fly_zone"] = facilities_gdf["no_fly_categories"].ne("")

    facilities_with_flags = facilities_gdf.drop(columns=["geometry"]).copy()
    filtered = facilities_with_flags[~facilities_with_flags["in_no_fly_zone"]].copy()
    return filtered.reset_index(drop=True), facilities_with_flags.reset_index(drop=True)


def _write_extraction_metadata(
    facilities_with_flags: pd.DataFrame,
    filtered_facilities: pd.DataFrame,
    no_fly_zones: gpd.GeoDataFrame,
    settings: Settings,
) -> None:
    excluded = facilities_with_flags[facilities_with_flags["in_no_fly_zone"]].copy()
    excluded_by_category: dict[str, int] = {}
    for category_string in excluded["no_fly_categories"]:
        for category in filter(None, str(category_string).split("|")):
            excluded_by_category[category] = excluded_by_category.get(category, 0) + 1

    metadata = {
        "raw_facility_count": int(len(facilities_with_flags)),
        "filtered_facility_count": int(len(filtered_facilities)),
        "excluded_facility_count": int(excluded["facility_id"].nunique()),
        "raw_demand_count": int(facilities_with_flags["is_demand_point"].sum()),
        "filtered_demand_count": int(filtered_facilities["is_demand_point"].sum()),
        "excluded_demand_count": int(excluded["is_demand_point"].sum()),
        "raw_candidate_count": int(facilities_with_flags["is_candidate_station"].sum()),
        "filtered_candidate_count": int(filtered_facilities["is_candidate_station"].sum()),
        "excluded_candidate_count": int(excluded["is_candidate_station"].sum()),
        "no_fly_zone_count": int(len(no_fly_zones)),
        "no_fly_zone_count_by_category": {
            str(key): int(value)
            for key, value in no_fly_zones["no_fly_category"].value_counts().items()
        },
        "excluded_facility_count_by_category": excluded_by_category,
        "airport_buffer_m": settings.airport_buffer_m,
        "site_buffer_m": settings.no_fly_site_buffer_m,
    }
    (settings.processed_dir / "tehran_no_fly_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def extract_tehran_healthcare_facilities(settings: Settings) -> pd.DataFrame:
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.raw_dir.mkdir(parents=True, exist_ok=True)

    city_gdf = ox.geocode_to_gdf(settings.osm_place_name)
    city_polygon = city_gdf.geometry.iloc[0]

    tags = {
        "amenity": ["hospital", "clinic", "doctors", "ambulance_station"],
        "healthcare": [
            "hospital",
            "clinic",
            "doctor",
            "laboratory",
            "blood_donation",
            "blood_bank",
        ],
    }
    facilities = _features_from_polygon_with_fallback(
        city_polygon, tags=tags
    ).reset_index()
    if facilities.empty:
        raise RuntimeError("No healthcare facilities were returned from OpenStreetMap.")

    facilities["facility_category"] = facilities.apply(_classify_facility, axis=1)
    facilities["name"] = _normalize_name(
        facilities.get("name", pd.Series(index=facilities.index, dtype="object")),
        fallback="unnamed",
    )
    facilities["point_geometry"] = facilities.geometry.apply(_geometry_to_point)
    facilities["longitude"] = facilities["point_geometry"].x
    facilities["latitude"] = facilities["point_geometry"].y
    facilities["is_demand_point"] = facilities["facility_category"].isin(
        DEMAND_CATEGORIES
    )
    facilities["is_candidate_station"] = facilities["facility_category"].isin(
        PREFERRED_STATION_CATEGORIES
    )

    keep_cols = [
        "osmid",
        "element_type",
        "name",
        "amenity",
        "healthcare",
        "facility_category",
        "is_demand_point",
        "is_candidate_station",
        "latitude",
        "longitude",
    ]
    dataset = facilities[[col for col in keep_cols if col in facilities.columns]].copy()
    dataset = dataset.dropna(subset=["latitude", "longitude"]).drop_duplicates(
        subset=["name", "facility_category", "latitude", "longitude"]
    )

    if not dataset["is_demand_point"].any():
        dataset["is_demand_point"] = True
    if not dataset["is_candidate_station"].any():
        dataset["is_candidate_station"] = dataset["facility_category"].isin(
            {"hospital", "clinic"}
        )

    no_fly_zones = _build_no_fly_zones(city_gdf, settings)
    filtered_dataset, facilities_with_flags = _filter_facilities_by_no_fly_zones(
        dataset, no_fly_zones
    )

    (settings.processed_dir / "tehran_boundary.geojson").write_text(
        city_gdf.to_json(), encoding="utf-8"
    )
    no_fly_zones.to_file(
        settings.processed_dir / "tehran_no_fly_zones.geojson",
        driver="GeoJSON",
    )
    facilities_with_flags.to_csv(
        settings.processed_dir / "tehran_healthcare_facilities_all.csv", index=False
    )
    filtered_dataset.to_csv(
        settings.processed_dir / "tehran_healthcare_facilities.csv", index=False
    )
    _write_extraction_metadata(
        facilities_with_flags=facilities_with_flags,
        filtered_facilities=filtered_dataset,
        no_fly_zones=no_fly_zones,
        settings=settings,
    )
    return filtered_dataset


def load_facilities(settings: Settings) -> pd.DataFrame:
    csv_path = settings.processed_dir / "tehran_healthcare_facilities.csv"
    if not csv_path.exists():
        return extract_tehran_healthcare_facilities(settings)
    return pd.read_csv(csv_path)
