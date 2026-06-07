from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Sequence

from .geo import feature_properties, geometry_coordinates, haversine_m, lonlat_to_latlon


ON_ROAD_CLASSES = {
    "MOTORWAY",
    "MOTORWAY_LINK",
    "TRUNK",
    "TRUNK_LINK",
    "PRIMARY",
    "PRIMARY_LINK",
    "SECONDARY",
    "SECONDARY_LINK",
    "TERTIARY",
    "TERTIARY_LINK",
    "RESIDENTIAL",
    "UNCLASSIFIED",
    "SERVICE",
    "LIVING_STREET",
    "ROAD",
}


def _round_pct(value: float) -> float:
    return round(value, 2)


def _interval_distance_m(
    coords_lonlat: Sequence[Sequence[float]], start_index: int, end_index: int
) -> float:
    if not coords_lonlat:
        return 0.0
    start = max(0, min(start_index, len(coords_lonlat) - 1))
    end = max(start, min(end_index, len(coords_lonlat) - 1))
    distance = 0.0
    for index in range(start, end):
        distance += haversine_m(
            lonlat_to_latlon(coords_lonlat[index]),
            lonlat_to_latlon(coords_lonlat[index + 1]),
        )
    return distance


def audit_from_path_details(
    coords_lonlat: Sequence[Sequence[float]],
    path_details: Mapping[str, Any],
    total_distance_m: float | None = None,
) -> Dict[str, Any]:
    road_class_details = path_details.get("road_class")
    if not road_class_details:
        return {
            "car_free_pct": None,
            "on_road_pct": None,
            "by_road_class": {},
            "note": "No GraphHopper road_class path details are available for this geometry.",
        }

    by_class_m: Dict[str, float] = defaultdict(float)
    for item in road_class_details:
        if not isinstance(item, list) or len(item) < 3:
            continue
        start_index = int(item[0])
        end_index = int(item[1])
        road_class = str(item[2]).upper()
        by_class_m[road_class] += _interval_distance_m(
            coords_lonlat, start_index, end_index
        )

    detail_distance_m = sum(by_class_m.values())
    denominator = float(total_distance_m or detail_distance_m or 0.0)
    if denominator <= 0:
        return {
            "car_free_pct": None,
            "on_road_pct": None,
            "by_road_class": {},
            "note": "Route distance is zero; audit percentages are undefined.",
        }

    on_road_m = sum(
        distance for road_class, distance in by_class_m.items() if road_class in ON_ROAD_CLASSES
    )
    by_road_class = {
        road_class: {
            "distance_km": round(distance / 1000.0, 3),
            "pct": _round_pct(100.0 * distance / denominator),
            "on_road": road_class in ON_ROAD_CLASSES,
        }
        for road_class, distance in sorted(
            by_class_m.items(), key=lambda item: item[1], reverse=True
        )
    }
    on_road_pct = 100.0 * on_road_m / denominator
    return {
        "car_free_pct": _round_pct(max(0.0, 100.0 - on_road_pct)),
        "on_road_pct": _round_pct(on_road_pct),
        "by_road_class": by_road_class,
        "on_road_distance_km": round(on_road_m / 1000.0, 3),
        "audited_distance_km": round(detail_distance_m / 1000.0, 3),
    }


def audit_route_geometry(geometry: Any) -> Dict[str, Any]:
    coords = geometry_coordinates(geometry)
    props = feature_properties(geometry)
    path_details = props.get("path_details") or props.get("details")
    if not isinstance(path_details, Mapping):
        return {
            "car_free_pct": None,
            "on_road_pct": None,
            "by_road_class": {},
            "note": "Canopy can audit geometry returned by route/plan_loop because it includes GraphHopper path_details. This geometry has coordinates only.",
        }
    distance_m = props.get("distance_m")
    return audit_from_path_details(
        coords,
        path_details,
        float(distance_m) if distance_m is not None else None,
    )
