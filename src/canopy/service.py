from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .audit import audit_route_geometry
from .config import Settings
from .geo import (
    LatLon,
    centroid_direction_score,
    coerce_point,
    geometry_coordinates,
)
from .gpx import export_gpx as export_gpx_file
from .graphhopper import GraphHopperClient, GraphHopperError, PathResult
from .onemap import OneMapClient


@dataclass
class LoopCandidate:
    seed: int
    attempt: int
    requested_distance_m: float
    result: PathResult
    target_error_pct: float
    direction_score: Optional[float]


class CanopyService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings.from_env()
        self.graphhopper = GraphHopperClient(
            self.settings.graphhopper_url,
            profile=self.settings.graphhopper_profile,
            timeout_s=self.settings.graphhopper_timeout_s,
        )
        self._onemap: Optional[OneMapClient] = None

    @property
    def onemap(self) -> OneMapClient:
        if self._onemap is None:
            self._onemap = OneMapClient(self.settings)
        return self._onemap

    def geocode(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.onemap.geocode(query, limit=limit)

    def _resolve_location(self, value: Any) -> LatLon:
        return coerce_point(value, geocoder=lambda query: self.geocode(query, limit=1))

    def route(self, origin: Any, destination: Any, prefer: str = "pcn") -> Dict[str, Any]:
        self._validate_prefer(prefer)
        origin_point = self._resolve_location(origin)
        destination_point = self._resolve_location(destination)
        result = self.graphhopper.route(origin_point, destination_point)
        return self._route_response(
            result,
            extra_geometry_properties={
                "profile": self.settings.graphhopper_profile,
                "prefer": "pcn",
            },
        )

    def plan_loop(
        self,
        start: Any,
        distance_km: float,
        direction: Optional[str] = None,
        prefer: str = "pcn",
    ) -> Dict[str, Any]:
        self._validate_prefer(prefer)
        if distance_km <= 0:
            raise ValueError("distance_km must be positive")
        start_point = self._resolve_location(start)
        target_m = distance_km * 1000.0
        candidates = self._loop_candidates(start_point, target_m, direction)
        if not candidates:
            raise GraphHopperError("No round_trip candidates were returned by GraphHopper")
        chosen = self._choose_loop_candidate(candidates)
        actual_km = chosen.result.distance_km
        response = self._route_response(
            chosen.result,
            extra_geometry_properties={
                "profile": self.settings.graphhopper_profile,
                "prefer": "pcn",
                "loop_seed": chosen.seed,
                "loop_attempt": chosen.attempt,
                "target_distance_m": round(target_m, 3),
                "requested_distance_m": round(chosen.requested_distance_m, 3),
                "direction": direction,
                "direction_score": chosen.direction_score,
            },
        )
        response.update(
            {
                "target_distance_km": round(distance_km, 3),
                "distance_error_pct": round(chosen.target_error_pct, 2),
                "loop_seed": chosen.seed,
                "loop_attempt": chosen.attempt,
                "direction_score": (
                    round(chosen.direction_score, 4)
                    if chosen.direction_score is not None
                    else None
                ),
                "candidate_count": len(candidates),
            }
        )
        return response

    def _loop_candidates(
        self, start: LatLon, target_m: float, direction: Optional[str]
    ) -> List[LoopCandidate]:
        candidates: List[LoopCandidate] = []
        max_seeds = max(1, self.settings.loop_max_seed_candidates)
        max_attempts = max(1, self.settings.loop_max_attempts_per_seed)
        for seed in range(1, max_seeds + 1):
            requested_m = target_m
            previous_actual_m: Optional[float] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = self.graphhopper.round_trip(start, requested_m, seed)
                except GraphHopperError:
                    break
                actual_m = result.distance_m
                if actual_m <= 0:
                    break
                target_error_pct = abs(actual_m - target_m) / target_m * 100.0
                direction_score = centroid_direction_score(
                    start, result.coords_lonlat, direction
                )
                candidates.append(
                    LoopCandidate(
                        seed=seed,
                        attempt=attempt,
                        requested_distance_m=requested_m,
                        result=result,
                        target_error_pct=target_error_pct,
                        direction_score=direction_score,
                    )
                )
                if target_error_pct <= self.settings.loop_tolerance_pct:
                    break
                if previous_actual_m is not None and abs(previous_actual_m - actual_m) < 25:
                    break
                previous_actual_m = actual_m
                ratio = target_m / actual_m
                ratio = max(0.65, min(1.8, ratio))
                next_requested_m = requested_m * ratio
                if abs(next_requested_m - requested_m) < 100:
                    break
                requested_m = next_requested_m
        return candidates

    def _choose_loop_candidate(self, candidates: List[LoopCandidate]) -> LoopCandidate:
        tolerance = self.settings.loop_tolerance_pct

        def rank(candidate: LoopCandidate) -> tuple:
            score = candidate.direction_score
            car_free_pct = candidate.result.audit().get("car_free_pct")
            car_free_pct = float(car_free_pct) if car_free_pct is not None else 0.0
            if score is None:
                if candidate.target_error_pct <= tolerance:
                    return (0, -car_free_pct, candidate.target_error_pct, candidate.attempt)
                return (1, candidate.target_error_pct, -car_free_pct, candidate.attempt)
            direction_ok = score >= 0.55
            if candidate.target_error_pct <= tolerance and direction_ok:
                return (
                    0,
                    -car_free_pct,
                    -score,
                    candidate.target_error_pct,
                    candidate.attempt,
                )
            if candidate.target_error_pct <= tolerance:
                return (
                    1,
                    -score,
                    -car_free_pct,
                    candidate.target_error_pct,
                    candidate.attempt,
                )
            direction_penalty = (1.0 - score) * 20.0
            return (
                2,
                candidate.target_error_pct + direction_penalty,
                -car_free_pct,
                candidate.attempt,
            )

        return sorted(candidates, key=rank)[0]

    def audit_route(self, geometry: Any) -> Dict[str, Any]:
        return audit_route_geometry(geometry)

    def export_gpx(self, geometry: Any, name: str) -> Dict[str, str]:
        return export_gpx_file(geometry, name)

    def pois_along(
        self,
        geometry: Any,
        types: Optional[List[str]] = None,
        corridor_m: Optional[float] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        poi_types = types or ["water", "toilet", "bicycle_parking", "shelter"]
        return self.onemap.pois_along(
            geometry,
            poi_types=poi_types,
            corridor_m=(
                self.settings.poi_corridor_m if corridor_m is None else float(corridor_m)
            ),
            max_results=max_results,
        )

    def _route_response(
        self,
        result: PathResult,
        extra_geometry_properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        audit = result.audit()
        geometry = result.feature(extra_geometry_properties)
        return {
            "distance_km": round(result.distance_km, 3),
            "car_free_pct": audit.get("car_free_pct"),
            "on_road_pct": audit.get("on_road_pct"),
            "by_road_class": audit.get("by_road_class", {}),
            "geometry": geometry,
            "point_count": len(geometry_coordinates(geometry)),
            "routing_engine": "graphhopper",
            "note": (
                "Low-car routing favors PCN/cycleway/path geometry. It does not avoid pedestrians; Singapore PCNs are shared paths."
            ),
        }

    @staticmethod
    def _validate_prefer(prefer: str) -> None:
        if prefer != "pcn":
            raise ValueError("Only prefer='pcn' is supported in this milestone")
