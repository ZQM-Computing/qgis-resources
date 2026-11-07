#!/usr/bin/env python3
"""Bounded, synthetic-only 2D utility corridor proximity screening using GDAL/OGR.

Distances are projected horizontal geometry distances, NOT 3D conductor clearance,
vegetation growth predictions, wildfire probabilities or work-order authorization.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path
import re
import sys

CRS = "EPSG:32617"
MAX_INPUT = 1024 * 1024
MAX_ASSETS = 100
MAX_VEGETATION = 1000
MAX_POINTS = 10000
OPAQUE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,79}$")


def unique_pairs(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON property")
        result[name] = value
    return result


def nonfinite(value):
    raise ValueError("nonfinite JSON number")


def load(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT:
        raise ValueError("fixture too large")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs, parse_constant=nonfinite)


def _valid_date(s: object) -> bool:
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        date.fromisoformat(s)
    except ValueError:
        return False
    return True


def _coords(value, *, ring=False):
    if not isinstance(value, list) or len(value) > MAX_POINTS or len(value) < (4 if ring else 2):
        raise ValueError("invalid coordinate count")
    for pair in value:
        if (not isinstance(pair, list) or len(pair) != 2
                or any(isinstance(n, bool) or not isinstance(n, (int, float))
                       or not math.isfinite(n) for n in pair)):
            raise ValueError("invalid coordinate pair")
        # Bounded UTM-like projected coordinates. Prevent accidental lon/lat as metres.
        if not (100000 <= pair[0] <= 900000 and 0 <= pair[1] <= 10000000):
            raise ValueError("projected coordinates outside pilot bounds")
    if ring and value[0] != value[-1]:
        raise ValueError("polygon ring not closed")


def _geometry(source: dict, kind: str, ogr):
    if not isinstance(source, dict) or set(source) != {"type", "coordinates"} or source["type"] != kind:
        raise ValueError("invalid or unsupported geometry type")
    coords = source["coordinates"]
    if kind == "LineString":
        _coords(coords)
    else:
        if not isinstance(coords, list) or not 1 <= len(coords) <= 50:
            raise ValueError("polygon rings missing or excessive")
        for ring in coords:
            _coords(ring, ring=True)
    geom = ogr.CreateGeometryFromJson(json.dumps(source, allow_nan=False))
    if geom is None or geom.IsEmpty() or not bool(geom.IsValid()):
        raise ValueError("invalid geometry topology")
    if (kind == "LineString" and ogr.GT_Flatten(geom.GetGeometryType()) != ogr.wkbLineString) or (
            kind == "Polygon" and ogr.GT_Flatten(geom.GetGeometryType()) != ogr.wkbPolygon):
        raise ValueError("unexpected geometry type")
    return geom


def _record_id(entry, seen):
    ident = entry.get("id")
    if not isinstance(ident, str) or not OPAQUE_ID.fullmatch(ident) or ident in seen:
        raise ValueError("invalid or duplicate opaque asset identifier")
    seen.add(ident)
    return ident


def analyze(record: dict) -> dict:
    """Pure in-memory measurement, with no external data or regulatory clearance claim."""
    from osgeo import ogr

    if not isinstance(record, dict) or type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        raise ValueError("unsupported schema version")
    if record.get("scope") != "synthetic-only" or record.get("crs") != CRS:
        raise ValueError("only synthetic projected CRS EPSG:32617 supported")
    if record.get("human_review") != "pending" or record.get("deployment_authorized") is True:
        raise ValueError("screening cannot self-authorize")
    observed = record.get("observed_date")
    if not _valid_date(observed):
        raise ValueError("missing valid observation date")
    threshold = record.get("screening_distance_m")
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold) or not 0 < threshold <= 100):
        raise ValueError("invalid screening distance")
    assets, plants = record.get("assets"), record.get("vegetation")
    if not isinstance(assets, list) or not 1 <= len(assets) <= MAX_ASSETS:
        raise ValueError("missing or excessive assets")
    if not isinstance(plants, list) or not 1 <= len(plants) <= MAX_VEGETATION:
        raise ValueError("missing or excessive vegetation geometries")
    seen_assets, seen_plants = set(), set()
    lines, polygons = [], []
    for entry in assets:
        if not isinstance(entry, dict):
            raise ValueError("invalid asset")
        ident = _record_id(entry, seen_assets)
        lines.append((ident, _geometry(entry.get("geometry"), "LineString", ogr)))
    for entry in plants:
        if not isinstance(entry, dict):
            raise ValueError("invalid vegetation")
        ident = _record_id(entry, seen_plants)
        polygons.append((ident, _geometry(entry.get("geometry"), "Polygon", ogr)))
    results = []
    for asset_id, line in lines:
        candidates = []
        for vegetation_id, polygon in polygons:
            distance = line.Distance(polygon)
            if distance is None or not math.isfinite(distance) or distance < 0:
                raise ValueError("invalid projected horizontal distance")
            if distance <= threshold:
                candidates.append({"vegetation_id": vegetation_id, "horizontal_distance_m": round(distance, 3)})
        candidates.sort(key=lambda v: (v["horizontal_distance_m"], v["vegetation_id"]))
        results.append({
            "asset_id": asset_id,
            "finding": "SCREEN_FOR_INSPECTION" if candidates else "NO_NEARBY_MAPPED_GEOMETRY_NOT_CLEARANCE",
            "candidates": candidates,
        })
    results.sort(key=lambda x: x["asset_id"])
    return {
        "schema_version": 1,
        "method": "OGR 2D projected geometry distance",
        "measurement_crs": CRS,
        "observed_date_claimed": observed,
        "screening_distance_m": threshold,
        "status": "REVIEW" if any(x["candidates"] for x in results) else "INSUFFICIENT_EVIDENCE",
        "asset_results": results,
        "coverage_verified": False,
        "asset_geometry_verified": False,
        "canopy_height_verified": False,
        "conductor_clearance_3d_measured": False,
        "wildfire_probability_estimated": False,
        "cost_savings_estimated": False,
        "work_order_authorized": False,
        "human_review_required": True,
        "source_scope": "synthetic-only",
        "limitations": "Horizontal projected screening only; cannot determine vertical conductor clearance, vegetation growth, regulatory compliance or actual utility maintenance need.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        result = analyze(load(args.input))
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, ImportError, RuntimeError):
        print("utility-corridor-screening-failed: invalid synthetic input or runtime", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
