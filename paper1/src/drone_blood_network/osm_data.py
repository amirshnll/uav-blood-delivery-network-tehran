from __future__ import annotations

import pandas as pd
import osmnx as ox

from .config import Settings


DEMAND_CATEGORIES = {"hospital", "clinic", "doctors", "doctor", "laboratory"}
PREFERRED_STATION_CATEGORIES = {
    "hospital",
    "ambulance_station",
    "blood_donation",
    "blood_bank",
}


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
    facilities = ox.features_from_polygon(city_polygon, tags=tags).reset_index()
    if facilities.empty:
        raise RuntimeError("No healthcare facilities were returned from OpenStreetMap.")

    facilities["facility_category"] = facilities.apply(_classify_facility, axis=1)
    default_name_series = pd.Series(index=facilities.index, dtype="object")
    facilities["name"] = facilities.get("name", default_name_series).fillna("unnamed")
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

    (settings.processed_dir / "tehran_boundary.geojson").write_text(
        city_gdf.to_json(), encoding="utf-8"
    )
    dataset.to_csv(
        settings.processed_dir / "tehran_healthcare_facilities.csv", index=False
    )
    return dataset


def load_facilities(settings: Settings) -> pd.DataFrame:
    csv_path = settings.processed_dir / "tehran_healthcare_facilities.csv"
    if not csv_path.exists():
        return extract_tehran_healthcare_facilities(settings)
    return pd.read_csv(csv_path)
