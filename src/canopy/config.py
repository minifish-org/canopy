from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _path_env(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


def _load_poi_theme_map() -> Dict[str, List[str]]:
    raw = os.getenv("CANOPY_POI_THEME_MAP")
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("CANOPY_POI_THEME_MAP must be a JSON object")
    result: Dict[str, List[str]] = {}
    for key, value in parsed.items():
        if isinstance(value, str):
            result[str(key)] = [value]
        elif isinstance(value, list):
            result[str(key)] = [str(item) for item in value]
        else:
            raise ValueError("CANOPY_POI_THEME_MAP values must be strings or lists")
    return result


@dataclass(frozen=True)
class Settings:
    graphhopper_url: str
    graphhopper_profile: str
    graphhopper_timeout_s: float
    output_dir: Path
    onemap_base_url: str
    onemap_email: Optional[str]
    onemap_password: Optional[str]
    onemap_token: Optional[str]
    onemap_token_expires_at: Optional[int]
    onemap_token_cache: Path
    loop_tolerance_pct: float
    loop_max_seed_candidates: int
    loop_max_attempts_per_seed: int
    poi_corridor_m: float
    poi_theme_map: Dict[str, List[str]]

    @classmethod
    def from_env(cls) -> "Settings":
        token_expires = os.getenv("CANOPY_ONEMAP_TOKEN_EXPIRES_AT")
        return cls(
            graphhopper_url=os.getenv(
                "CANOPY_GRAPHHOPPER_URL", "http://localhost:8989"
            ).rstrip("/"),
            graphhopper_profile=os.getenv("CANOPY_GRAPHHOPPER_PROFILE", "bike"),
            graphhopper_timeout_s=_float_env("CANOPY_GRAPHHOPPER_TIMEOUT_S", 15.0),
            output_dir=_path_env("CANOPY_OUTPUT_DIR", "~/.canopy/gpx"),
            onemap_base_url=os.getenv(
                "CANOPY_ONEMAP_BASE_URL", "https://www.onemap.gov.sg"
            ).rstrip("/"),
            onemap_email=os.getenv("CANOPY_ONEMAP_EMAIL"),
            onemap_password=os.getenv("CANOPY_ONEMAP_PASSWORD"),
            onemap_token=os.getenv("CANOPY_ONEMAP_TOKEN"),
            onemap_token_expires_at=int(token_expires) if token_expires else None,
            onemap_token_cache=_path_env(
                "CANOPY_ONEMAP_TOKEN_CACHE", "~/.canopy/onemap-token.json"
            ),
            loop_tolerance_pct=_float_env("CANOPY_LOOP_TOLERANCE_PCT", 5.0),
            loop_max_seed_candidates=_int_env("CANOPY_LOOP_MAX_SEEDS", 24),
            loop_max_attempts_per_seed=_int_env("CANOPY_LOOP_MAX_ATTEMPTS", 3),
            poi_corridor_m=_float_env("CANOPY_POI_CORRIDOR_M", 120.0),
            poi_theme_map=_load_poi_theme_map(),
        )
