from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib import parse, request
from urllib.error import HTTPError, URLError

from .audit import audit_from_path_details
from .geo import LatLon, geojson_feature


class GraphHopperError(RuntimeError):
    pass


@dataclass
class PathResult:
    distance_m: float
    time_ms: int
    coords_lonlat: List[List[float]]
    path_details: Dict[str, Any]
    raw: Dict[str, Any]

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000.0

    def audit(self) -> Dict[str, Any]:
        return audit_from_path_details(
            self.coords_lonlat, self.path_details, self.distance_m
        )

    def feature(self, extra_properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "source": "graphhopper",
            "distance_m": round(self.distance_m, 3),
            "time_ms": self.time_ms,
            "path_details": self.path_details,
        }
        if extra_properties:
            props.update(extra_properties)
        return geojson_feature(self.coords_lonlat, props)


class GraphHopperClient:
    def __init__(self, base_url: str, profile: str = "bike", timeout_s: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.timeout_s = timeout_s

    def _get_json(self, path: str, params: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        query = parse.urlencode(params, doseq=True)
        url = f"{self.base_url}{path}?{query}"
        req = request.Request(url, headers={"Accept": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GraphHopperError(f"GraphHopper HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise GraphHopperError(
                f"GraphHopper is not reachable at {self.base_url}: {exc.reason}"
            ) from exc
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise GraphHopperError(f"GraphHopper returned non-JSON data: {body[:200]}") from exc
        if isinstance(data, dict) and data.get("message") and not data.get("paths"):
            raise GraphHopperError(f"GraphHopper error: {data['message']}")
        return data

    def info(self) -> Dict[str, Any]:
        return self._get_json("/info", [])

    def route(self, origin: LatLon, destination: LatLon) -> PathResult:
        return self._route([origin, destination])

    def round_trip(self, start: LatLon, distance_m: float, seed: int) -> PathResult:
        return self._route(
            [start],
            algorithm="round_trip",
            round_trip_distance_m=distance_m,
            round_trip_seed=seed,
        )

    def _route(
        self,
        points: Sequence[LatLon],
        algorithm: Optional[str] = None,
        round_trip_distance_m: Optional[float] = None,
        round_trip_seed: Optional[int] = None,
    ) -> PathResult:
        params: List[Tuple[str, Any]] = []
        for lat, lon in points:
            params.append(("point", f"{lat:.7f},{lon:.7f}"))
        params.extend(
            [
                ("profile", self.profile),
                ("points_encoded", "false"),
                ("instructions", "false"),
                ("calc_points", "true"),
                ("ch.disable", "true"),
                ("details", "road_class"),
                ("details", "bike_network"),
            ]
        )
        if algorithm:
            params.append(("algorithm", algorithm))
        if round_trip_distance_m is not None:
            params.append(("round_trip.distance", int(round(round_trip_distance_m))))
        if round_trip_seed is not None:
            params.append(("round_trip.seed", int(round_trip_seed)))

        data = self._get_json("/route", params)
        paths = data.get("paths") or []
        if not paths:
            raise GraphHopperError(f"GraphHopper returned no path: {data}")
        path = paths[0]
        points_obj = path.get("points") or {}
        coords = points_obj.get("coordinates") or []
        if not coords:
            raise GraphHopperError("GraphHopper returned a path without point geometry")
        coords_lonlat = [[float(coord[0]), float(coord[1])] for coord in coords]
        return PathResult(
            distance_m=float(path.get("distance", 0.0)),
            time_ms=int(path.get("time", 0)),
            coords_lonlat=coords_lonlat,
            path_details=path.get("details") or {},
            raw=path,
        )
