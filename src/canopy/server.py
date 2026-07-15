from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .service import CanopyService


try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - exercised before runtime install
    raise SystemExit(
        "The MCP runtime is not installed. Run `python -m pip install -e .` first."
    ) from exc


mcp = FastMCP(
    "canopy",
    host=os.getenv("CANOPY_MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("CANOPY_MCP_PORT", "8000")),
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)
service = CanopyService()


@mcp.tool()
def geocode(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Resolve a Singapore address/place/postal code using OneMap Search."""
    return service.geocode(query, limit=limit)


@mcp.tool()
def plan_loop(
    start: Any,
    distance_km: float,
    direction: Optional[str] = None,
    prefer: str = "pcn",
) -> Dict[str, Any]:
    """Plan a low-car round trip from a start point using GraphHopper round_trip.

    start may be "lat,lon", a {lat, lon} object, or a place string that OneMap can geocode.
    direction is optional and selects among many seeds by route centroid, e.g. east or northeast.
    The requested distance is approximate; the response always reports the actual distance.
    """
    return service.plan_loop(start, distance_km, direction=direction, prefer=prefer)


@mcp.tool()
def route(origin: Any, destination: Any, prefer: str = "pcn") -> Dict[str, Any]:
    """Plan a low-car A-to-B route.

    origin and destination may be "lat,lon", {lat, lon} objects, or OneMap-geocodable strings.
    """
    return service.route(origin, destination, prefer=prefer)


@mcp.tool()
def pois_along(
    geometry: Any,
    types: Optional[List[str]] = None,
    corridor_m: Optional[float] = None,
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """Find OneMap theme POIs near a route geometry.

    Exact OneMap query names are accepted in types. Friendly aliases such as water, toilet,
    bicycle_parking, and shelter are best-effort and can be configured with CANOPY_POI_THEME_MAP.
    """
    return service.pois_along(
        geometry, types=types, corridor_m=corridor_m, max_results=max_results
    )


@mcp.tool()
def audit_route(geometry: Any) -> Dict[str, Any]:
    """Return car-free/on-road percentages from Canopy route geometry path details."""
    return service.audit_route(geometry)


@mcp.tool()
def export_gpx(geometry: Any, name: str) -> Dict[str, str]:
    """Return portable GPX content, filename, and media type for a route geometry."""
    return service.export_gpx(geometry, name)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
