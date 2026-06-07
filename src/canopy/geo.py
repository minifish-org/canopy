from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


EARTH_RADIUS_M = 6_371_008.8
LatLon = Tuple[float, float]
LonLat = Tuple[float, float]


def haversine_m(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def line_distance_m(points_latlon: Sequence[LatLon]) -> float:
    return sum(
        haversine_m(points_latlon[index], points_latlon[index + 1])
        for index in range(max(0, len(points_latlon) - 1))
    )


def lonlat_to_latlon(point: Sequence[float]) -> LatLon:
    return (float(point[1]), float(point[0]))


def latlon_to_lonlat(point: Sequence[float]) -> LonLat:
    return (float(point[1]), float(point[0]))


def _looks_like_singapore_lat_lon(a: float, b: float) -> bool:
    return 0.8 <= a <= 1.6 and 103.0 <= b <= 105.0


def normalize_lonlat_coord(coord: Sequence[float]) -> LonLat:
    if len(coord) < 2:
        raise ValueError("Coordinate must contain at least two numbers")
    a = float(coord[0])
    b = float(coord[1])
    if _looks_like_singapore_lat_lon(a, b):
        return (b, a)
    return (a, b)


def geometry_coordinates(geometry: Any) -> List[LonLat]:
    if isinstance(geometry, dict) and geometry.get("type") == "Feature":
        geometry = geometry.get("geometry", {})
    if isinstance(geometry, dict) and geometry.get("type") == "LineString":
        return [normalize_lonlat_coord(coord) for coord in geometry["coordinates"]]
    if isinstance(geometry, dict) and "coordinates" in geometry:
        return [normalize_lonlat_coord(coord) for coord in geometry["coordinates"]]
    if isinstance(geometry, list):
        return [normalize_lonlat_coord(coord) for coord in geometry]
    raise ValueError("Geometry must be a GeoJSON LineString, Feature, or coordinate list")


def geojson_feature(
    coords_lonlat: Sequence[Sequence[float]], properties: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "properties": properties or {},
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [round(float(lon), 7), round(float(lat), 7)]
                for lon, lat in coords_lonlat
            ],
        },
    }


def feature_properties(geometry: Any) -> Dict[str, Any]:
    if isinstance(geometry, dict) and geometry.get("type") == "Feature":
        props = geometry.get("properties") or {}
        if isinstance(props, dict):
            return props
    if isinstance(geometry, dict):
        props = geometry.get("properties") or {}
        if isinstance(props, dict):
            return props
    return {}


def coerce_point(
    value: Any, geocoder: Optional[Callable[[str], List[Dict[str, Any]]]] = None
) -> LatLon:
    if isinstance(value, dict):
        lat_value = (
            value.get("lat")
            or value.get("latitude")
            or value.get("LATITUDE")
            or value.get("Lat")
        )
        lon_value = (
            value.get("lon")
            or value.get("lng")
            or value.get("longitude")
            or value.get("LONGITUDE")
            or value.get("LONGTITUDE")
            or value.get("Lng")
        )
        if lat_value is not None and lon_value is not None:
            return (float(lat_value), float(lon_value))

    if isinstance(value, (list, tuple)) and len(value) >= 2:
        a = float(value[0])
        b = float(value[1])
        if _looks_like_singapore_lat_lon(a, b):
            return (a, b)
        if _looks_like_singapore_lat_lon(b, a):
            return (b, a)
        return (a, b)

    if isinstance(value, str):
        stripped = value.strip()
        parts = [part for part in re.split(r"[\s,]+", stripped) if part]
        if len(parts) >= 2:
            try:
                a = float(parts[0])
                b = float(parts[1])
                if _looks_like_singapore_lat_lon(a, b):
                    return (a, b)
                if _looks_like_singapore_lat_lon(b, a):
                    return (b, a)
            except ValueError:
                pass
        if geocoder is not None:
            matches = geocoder(stripped)
            if not matches:
                raise ValueError(f"OneMap found no geocode result for {stripped!r}")
            return coerce_point(matches[0])

    raise ValueError(
        "Location must be a lat/lon pair, a dict with lat/lon, or a geocodable string"
    )


def direction_vector(direction: Optional[str]) -> Optional[Tuple[float, float]]:
    if not direction:
        return None
    key = direction.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    vectors = {
        "n": (0.0, 1.0),
        "north": (0.0, 1.0),
        "s": (0.0, -1.0),
        "south": (0.0, -1.0),
        "e": (1.0, 0.0),
        "east": (1.0, 0.0),
        "w": (-1.0, 0.0),
        "west": (-1.0, 0.0),
        "ne": (1.0, 1.0),
        "northeast": (1.0, 1.0),
        "nw": (-1.0, 1.0),
        "northwest": (-1.0, 1.0),
        "se": (1.0, -1.0),
        "southeast": (1.0, -1.0),
        "sw": (-1.0, -1.0),
        "southwest": (-1.0, -1.0),
    }
    vector = vectors.get(key)
    if vector is None:
        raise ValueError(
            "direction must be one of north, south, east, west, northeast, northwest, southeast, southwest"
        )
    length = math.hypot(vector[0], vector[1])
    return (vector[0] / length, vector[1] / length)


def centroid_direction_score(
    start_latlon: LatLon, coords_lonlat: Sequence[Sequence[float]], direction: Optional[str]
) -> Optional[float]:
    desired = direction_vector(direction)
    if desired is None or not coords_lonlat:
        return None
    mean_lon = sum(float(coord[0]) for coord in coords_lonlat) / len(coords_lonlat)
    mean_lat = sum(float(coord[1]) for coord in coords_lonlat) / len(coords_lonlat)
    lat0, lon0 = start_latlon
    north_m = haversine_m((lat0, lon0), (mean_lat, lon0))
    if mean_lat < lat0:
        north_m *= -1
    east_m = haversine_m((lat0, lon0), (lat0, mean_lon))
    if mean_lon < lon0:
        east_m *= -1
    length = math.hypot(east_m, north_m)
    if length == 0:
        return 0.0
    actual = (east_m / length, north_m / length)
    return actual[0] * desired[0] + actual[1] * desired[1]


def buffered_bbox(
    coords_lonlat: Sequence[Sequence[float]], buffer_m: float
) -> Tuple[float, float, float, float]:
    if not coords_lonlat:
        raise ValueError("Cannot build a bbox for empty geometry")
    lons = [float(coord[0]) for coord in coords_lonlat]
    lats = [float(coord[1]) for coord in coords_lonlat]
    mid_lat = sum(lats) / len(lats)
    lat_buffer = buffer_m / 111_320.0
    lon_buffer = buffer_m / (111_320.0 * max(0.2, math.cos(math.radians(mid_lat))))
    return (
        min(lats) - lat_buffer,
        min(lons) - lon_buffer,
        max(lats) + lat_buffer,
        max(lons) + lon_buffer,
    )


def _project_latlon(point: LatLon, origin: LatLon) -> Tuple[float, float]:
    lat, lon = point
    origin_lat, origin_lon = origin
    x = math.radians(lon - origin_lon) * EARTH_RADIUS_M * math.cos(math.radians(origin_lat))
    y = math.radians(lat - origin_lat) * EARTH_RADIUS_M
    return (x, y)


def point_to_segment_distance_m(point: LatLon, start: LatLon, end: LatLon) -> float:
    px, py = _project_latlon(point, start)
    ax, ay = (0.0, 0.0)
    bx, by = _project_latlon(end, start)
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return haversine_m(point, start)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    closest = (ax + t * dx, ay + t * dy)
    return math.hypot(px - closest[0], py - closest[1])


def distance_to_polyline_m(point: LatLon, coords_lonlat: Sequence[Sequence[float]]) -> float:
    points_latlon = [lonlat_to_latlon(coord) for coord in coords_lonlat]
    if not points_latlon:
        raise ValueError("Cannot measure distance to an empty polyline")
    if len(points_latlon) == 1:
        return haversine_m(point, points_latlon[0])
    return min(
        point_to_segment_distance_m(point, points_latlon[index], points_latlon[index + 1])
        for index in range(len(points_latlon) - 1)
    )


def latlon_points(coords_lonlat: Iterable[Sequence[float]]) -> List[LatLon]:
    return [lonlat_to_latlon(coord) for coord in coords_lonlat]
