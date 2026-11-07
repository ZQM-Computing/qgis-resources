#!/usr/bin/env python3
"""Strict bounded GeoJSON polygon preflight for optional local STAC AOI masks.

A topology-valid polygon is not a surveyed boundary or verified property right.
No reprojection or remote access is performed by this module.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

MAX_GEOJSON_BYTES = 128 * 1024
MAX_GEOMETRY_VERTICES = 2000
MAX_POLYGON_PARTS = 20


class AoiError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise AoiError("duplicate GeoJSON key")
        result[k] = v
    return result


def _reject_constant(value):
    raise AoiError("nonfinite GeoJSON value")


def load_aoi(path: Path, bbox):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_GEOJSON_BYTES + 1)
    if len(data) > MAX_GEOJSON_BYTES:
        raise AoiError("AOI polygon exceeds byte limit")
    try:
        geometry = json.loads(data.decode("utf-8"), object_pairs_hook=_unique,
                              parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AoiError("AOI is not valid GeoJSON") from exc
    return validate_aoi(geometry, bbox)


def validate_aoi(geometry, bbox):
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        raise AoiError("expected only a GeoJSON geometry object")
    kind, coordinates = geometry["type"], geometry["coordinates"]
    if kind not in ("Polygon", "MultiPolygon"):
        raise AoiError("only Polygon or MultiPolygon is allowed")
    polygons = [coordinates] if kind == "Polygon" else coordinates
    if not isinstance(polygons, list) or not 1 <= len(polygons) <= MAX_POLYGON_PARTS:
        raise AoiError("invalid polygon part count")
    if len(bbox) != 4:
        raise AoiError("missing geographic query bbox")
    west, south, east, north = bbox
    count = 0
    for polygon in polygons:
        if not isinstance(polygon, list) or not 1 <= len(polygon) <= MAX_POLYGON_PARTS:
            raise AoiError("invalid polygon ring count")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise AoiError("polygon ring requires four or more points")
            count += len(ring)
            if count > MAX_GEOMETRY_VERTICES:
                raise AoiError("AOI exceeds polygon vertex budget")
            if ring[0] != ring[-1]:
                raise AoiError("unclosed polygon ring")
            for point in ring:
                if (not isinstance(point, list) or len(point) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
                    raise AoiError("invalid finite two-dimensional coordinates")
                x, y = point
                if not (-180 <= x <= 180 and -90 <= y <= 90):
                    raise AoiError("invalid EPSG:4326 longitude/latitude")
                if not (west <= x <= east and south <= y <= north):
                    raise AoiError("AOI vertices lie outside requested query bbox")
            if len({tuple(point) for point in ring[:-1]}) < 3:
                raise AoiError("degenerate polygon ring")
            if any(abs(a[0] - b[0]) > 180 for a, b in zip(ring, ring[1:])):
                raise AoiError("antimeridian polygons unsupported")
    # Shapely/GEOS catches crossed rings, exterior/hole errors and overlapping
    # MultiPolygon members; never auto-repair an untrusted source boundary.
    try:
        from shapely.geometry import shape
    except ImportError as exc:
        raise AoiError("Shapely is required for AOI topology validation") from exc
    try:
        polygon = shape(geometry)
    except (ValueError, TypeError) as exc:
        raise AoiError("invalid AOI polygon topology") from exc
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise AoiError("invalid or empty polygon geometry")
    return geometry
