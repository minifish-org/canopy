from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import parse, request
from urllib.error import HTTPError, URLError

from .config import Settings
from .geo import buffered_bbox, distance_to_polyline_m, geometry_coordinates


class OneMapError(RuntimeError):
    pass


DEFAULT_THEME_ALIASES: Dict[str, List[str]] = {
    "water": ["drinking water", "water cooler", "water point"],
    "toilet": ["toilet", "public toilet", "restroom"],
    "bicycle_parking": ["bicycle parking", "bike parking", "bicycle park"],
    "shelter": ["shelter", "pavilion"],
    "park": ["parks"],
    "hawker": ["hawker centres", "hawker"],
    "mrt": ["mrt", "train station"],
}


class OneMapClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._theme_cache: Optional[List[Dict[str, Any]]] = None

    def _request_json(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        auth: bool = True,
    ) -> Dict[str, Any]:
        query = f"?{parse.urlencode(params)}" if params else ""
        url = f"{self.settings.onemap_base_url}{path}{query}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            headers["Authorization"] = self.access_token()
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise OneMapError(f"OneMap HTTP {exc.code}: {raw}") from exc
        except URLError as exc:
            raise OneMapError(f"OneMap is not reachable: {exc.reason}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OneMapError(f"OneMap returned non-JSON data: {raw[:200]}") from exc
        if isinstance(parsed, dict) and parsed.get("error"):
            raise OneMapError(f"OneMap error: {parsed['error']}")
        return parsed

    def _cached_token(self) -> Optional[str]:
        token = self.settings.onemap_token
        expires_at = self.settings.onemap_token_expires_at
        if token and (expires_at is None or expires_at > int(time.time()) + 300):
            return token
        cache_path = self.settings.onemap_token_cache
        if not cache_path.exists():
            return None
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        token = cached.get("access_token")
        expires_at = int(cached.get("expiry_timestamp") or 0)
        if token and expires_at > int(time.time()) + 300:
            return str(token)
        return None

    def _save_token(self, token_payload: Dict[str, Any]) -> None:
        cache_path = self.settings.onemap_token_cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(token_payload), encoding="utf-8")
        try:
            os.chmod(cache_path, 0o600)
        except OSError:
            pass

    def _authenticate(self) -> str:
        if not self.settings.onemap_email or not self.settings.onemap_password:
            raise OneMapError(
                "OneMap credentials are not configured. Set CANOPY_ONEMAP_TOKEN, or set CANOPY_ONEMAP_EMAIL and CANOPY_ONEMAP_PASSWORD."
            )
        payload = self._request_json(
            "POST",
            "/api/auth/post/getToken",
            body={
                "email": self.settings.onemap_email,
                "password": self.settings.onemap_password,
            },
            auth=False,
        )
        token = payload.get("access_token")
        if not token:
            raise OneMapError(f"OneMap did not return an access_token: {payload}")
        self._save_token(payload)
        return str(token)

    def access_token(self) -> str:
        return self._cached_token() or self._authenticate()

    def geocode(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        data = self._request_json(
            "GET",
            "/api/common/elastic/search",
            params={
                "searchVal": query,
                "returnGeom": "Y",
                "getAddrDetails": "Y",
                "pageNum": 1,
            },
        )
        results = data.get("results") or []
        output: List[Dict[str, Any]] = []
        for item in results[:limit]:
            lat = item.get("LATITUDE")
            lon = item.get("LONGITUDE") or item.get("LONGTITUDE")
            if lat is None or lon is None:
                continue
            output.append(
                {
                    "name": item.get("SEARCHVAL") or item.get("ADDRESS") or query,
                    "lat": float(lat),
                    "lon": float(lon),
                    "address": item.get("ADDRESS"),
                    "postal": item.get("POSTAL"),
                    "source": "onemap",
                }
            )
        return output

    def all_themes(self) -> List[Dict[str, Any]]:
        if self._theme_cache is not None:
            return self._theme_cache
        data = self._request_json(
            "GET",
            "/api/public/themesvc/getAllThemesInfo",
            params={"moreInfo": "Y"},
        )
        themes = data.get("Theme_Names") or data.get("theme_names") or []
        self._theme_cache = [theme for theme in themes if isinstance(theme, dict)]
        return self._theme_cache

    def resolve_theme_query_names(self, poi_types: Iterable[str]) -> Dict[str, List[str]]:
        themes = self.all_themes()
        by_query = {
            str(theme.get("QUERYNAME", "")).lower(): str(theme.get("QUERYNAME", ""))
            for theme in themes
            if theme.get("QUERYNAME")
        }
        by_name = {
            str(theme.get("THEMENAME", "")).lower(): str(theme.get("QUERYNAME", ""))
            for theme in themes
            if theme.get("THEMENAME") and theme.get("QUERYNAME")
        }
        resolved: Dict[str, List[str]] = {}
        for poi_type in poi_types:
            aliases = []
            aliases.extend(self.settings.poi_theme_map.get(poi_type, []))
            aliases.extend(DEFAULT_THEME_ALIASES.get(poi_type, []))
            aliases.append(poi_type.replace("_", " "))
            matches: List[str] = []
            for alias in aliases:
                key = alias.lower()
                if key in by_query:
                    matches.append(by_query[key])
                    continue
                if key in by_name:
                    matches.append(by_name[key])
                    continue
                words = [word for word in key.split() if word]
                for theme in themes:
                    query = str(theme.get("QUERYNAME", "")).lower()
                    name = str(theme.get("THEMENAME", "")).lower()
                    haystack = f"{query} {name}"
                    if words and all(word in haystack for word in words):
                        matches.append(str(theme.get("QUERYNAME")))
            deduped = []
            for match in matches:
                if match and match not in deduped:
                    deduped.append(match)
            resolved[poi_type] = deduped
        return resolved

    def retrieve_theme(
        self, query_name: str, bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"queryName": query_name}
        if bbox is not None:
            min_lat, min_lon, max_lat, max_lon = bbox
            params["extents"] = f"{min_lat:.7f},{min_lon:.7f},{max_lat:.7f},{max_lon:.7f}"
        data = self._request_json(
            "GET", "/api/public/themesvc/retrieveTheme", params=params
        )
        results = (
            data.get("SrchResults")
            or data.get("SearchResults")
            or data.get("results")
            or data.get("Result")
            or []
        )
        return [item for item in results if isinstance(item, dict)]

    def pois_along(
        self,
        geometry: Any,
        poi_types: Sequence[str],
        corridor_m: float,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        coords = geometry_coordinates(geometry)
        bbox = buffered_bbox(coords, corridor_m)
        theme_map = self.resolve_theme_query_names(poi_types)
        pois: List[Dict[str, Any]] = []
        for poi_type, query_names in theme_map.items():
            for query_name in query_names:
                for item in self.retrieve_theme(query_name, bbox=bbox):
                    parsed = _parse_poi(item)
                    if parsed is None:
                        continue
                    distance_m = distance_to_polyline_m(
                        (parsed["lat"], parsed["lon"]), coords
                    )
                    if distance_m > corridor_m:
                        continue
                    parsed.update(
                        {
                            "type": poi_type,
                            "theme": query_name,
                            "distance_to_route_m": round(distance_m, 1),
                            "source": "onemap",
                        }
                    )
                    pois.append(parsed)
        pois.sort(key=lambda item: (item["distance_to_route_m"], item.get("name") or ""))
        return pois[:max_results]


def _first_value(item: Dict[str, Any], keys: Sequence[str]) -> Optional[Any]:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", "NIL"):
            return value
    return None


def _parse_poi(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lat = _first_value(item, ["Lat", "LATITUDE", "latitude", "lat"])
    lon = _first_value(
        item,
        ["Lng", "LONGITUDE", "LONGTITUDE", "longitude", "longtitude", "lng", "lon"],
    )
    if lat is None or lon is None:
        return None
    name = _first_value(item, ["NAME", "Name", "THEMENAME", "DESCRIPTION"])
    address = _first_value(
        item,
        [
            "ADDRESS",
            "Address",
            "ADDRESSSTREETNAME",
            "ADDRESSPOSTALCODE",
            "POSTAL",
        ],
    )
    return {
        "name": str(name) if name is not None else "OneMap POI",
        "lat": float(lat),
        "lon": float(lon),
        "address": str(address) if address is not None else None,
        "description": _first_value(item, ["DESCRIPTION", "Description"]),
        "raw": item,
    }
