from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree as ET

from .geo import geometry_coordinates


GPX_NS = "http://www.topografix.com/GPX/1/1"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "canopy-track"


def _fmt(value: float) -> str:
    return f"{value:.7f}".rstrip("0").rstrip(".")


def write_gpx_track(
    coords_lonlat: Sequence[Sequence[float]], name: str, output_dir: Path
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"{_slug(name)}-{timestamp}.gpx"

    ET.register_namespace("", GPX_NS)
    ET.register_namespace("xsi", XSI_NS)
    gpx = ET.Element(
        f"{{{GPX_NS}}}gpx",
        {
            "version": "1.1",
            "creator": "Canopy",
            f"{{{XSI_NS}}}schemaLocation": (
                "http://www.topografix.com/GPX/1/1 "
                "http://www.topografix.com/GPX/1/1/gpx.xsd"
            ),
        },
    )
    metadata = ET.SubElement(gpx, f"{{{GPX_NS}}}metadata")
    ET.SubElement(metadata, f"{{{GPX_NS}}}name").text = name
    trk = ET.SubElement(gpx, f"{{{GPX_NS}}}trk")
    ET.SubElement(trk, f"{{{GPX_NS}}}name").text = name
    trkseg = ET.SubElement(trk, f"{{{GPX_NS}}}trkseg")
    for lon, lat in coords_lonlat:
        ET.SubElement(
            trkseg,
            f"{{{GPX_NS}}}trkpt",
            {"lat": _fmt(float(lat)), "lon": _fmt(float(lon))},
        )
    tree = ET.ElementTree(gpx)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def export_gpx(geometry: Any, name: str, output_dir: Path) -> Path:
    coords = geometry_coordinates(geometry)
    if len(coords) < 2:
        raise ValueError("GPX track export needs at least two points")
    return write_gpx_track(coords, name, output_dir)
