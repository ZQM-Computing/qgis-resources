#!/usr/bin/env python3
"""Offline NWI snapshot replay gate: checks internal integrity, never source truth.

An internally consistent agency-query archive is NOT evidence of coverage,
rights, authenticity, jurisdictional wetlands or client-delivery authorization.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from nwi_source_inspector import (
    LAYER_URL, MAX_FEATURES, MAX_OUTPUT_BYTES, MAX_VERTICES,
    SourceInspectionError, _bbox, _no_duplicates, _validate_coords,
)

HEX = re.compile(r"^[a-f0-9]{64}$")
SOURCE_KEYS = {"OBJECTID", "ATTRIBUTE", "WETLAND_TYPE"}


def replay(snapshot: dict) -> dict:
    """Recalculate immutable normalized feature checksum and reject inconsistencies."""
    if not isinstance(snapshot, dict) or type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1:
        raise SourceInspectionError("unsupported snapshot schema")
    if (snapshot.get("status") != "inspection-only-not-screened"
            or snapshot.get("coverage_state") != "unverified"
            or snapshot.get("reuse_rights") != "unverified"
            or snapshot.get("human_review") != "pending"
            or snapshot.get("regulatory_determination") is not False):
        raise SourceInspectionError("unsupported source approval assertions")
    src, collection = snapshot.get("source"), snapshot.get("feature_collection")
    if not isinstance(src, dict) or not isinstance(collection, dict):
        raise SourceInspectionError("missing source and normalized feature records")
    if (src.get("service") != LAYER_URL or type(src.get("layer_id")) is not int
            or src["layer_id"] != 0 or src.get("requested_output_crs") != "EPSG:4326"):
        raise SourceInspectionError("source identity or coordinate reference mismatch")
    bounds = src.get("request_bbox_epsg4326")
    if not isinstance(bounds, (list, tuple)):
        raise SourceInspectionError("missing query bounds")
    bbox = _bbox(bounds)
    if collection.get("type") != "FeatureCollection" or set(collection) != {"type", "features"}:
        raise SourceInspectionError("unexpected normalized GeoJSON envelope")
    rows = collection["features"]
    count = src.get("features_reconciled")
    if type(count) is not int or not 0 <= count <= MAX_FEATURES or not isinstance(rows, list) or len(rows) != count:
        raise SourceInspectionError("feature count mismatch")
    vertices = 0
    last = None
    for feature in rows:
        if not isinstance(feature, dict) or set(feature) != {"type", "id", "properties", "geometry"} or feature["type"] != "Feature":
            raise SourceInspectionError("non-normalized NWI feature")
        props = feature["properties"]
        if not isinstance(props, dict) or set(props) != SOURCE_KEYS:
            raise SourceInspectionError("unrecognized NWI attributes")
        oid = props.get("OBJECTID")
        if type(oid) is not int or oid != feature["id"] or (last is not None and oid <= last):
            raise SourceInspectionError("replayed NWI identifiers not ordered/unique")
        last = oid
        for key in ("ATTRIBUTE", "WETLAND_TYPE"):
            if not isinstance(props[key], str) or not props[key].strip():
                raise SourceInspectionError("missing wetland description")
        vertices += _validate_coords(feature["geometry"], requested_bbox=bbox)
        if vertices > MAX_VERTICES:
            raise SourceInspectionError("replayed NWI vertex budget exceeded")
    if type(src.get("feature_vertices_checked")) is not int or src["feature_vertices_checked"] != vertices:
        raise SourceInspectionError("feature vertex reconciliation mismatch")
    if "point-in-time-snapshot-unverified" not in str(src.get("feature_pagination_integrity", "")):
        raise SourceInspectionError("missing source temporal consistency caveat")
    canonical = json.dumps(collection, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    expected = src.get("normalized_geojson_sha256")
    if not isinstance(expected, str) or not HEX.fullmatch(expected) or sha256(canonical).hexdigest() != expected:
        raise SourceInspectionError("normalized source digest mismatch")
    return {
        "schema_version": 1,
        "status": "INTERNAL_INTEGRITY_REPLAYED_NOT_APPROVED",
        "source_layer": "USFWS-NWI-0",
        "normalized_geojson_sha256": expected,
        "feature_count": count,
        "vertex_count": vertices,
        "snapshot_authenticity_verified": False,
        "agency_temporal_consistency_verified": False,
        "geographic_completeness_verified": False,
        "reuse_rights_verified": False,
        "regulatory_jurisdiction_determined": False,
        "commercial_delivery_authorized": False,
        "human_review_required": True,
    }


def main(argv=None) -> int:
    """Report offline snapshot integrity and return failure for invalid evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.snapshot.open("rb") as stream:
            raw = stream.read(MAX_OUTPUT_BYTES + 1)
        if len(raw) > MAX_OUTPUT_BYTES:
            raise SourceInspectionError("source snapshot too large")
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
            parse_constant=lambda _x: (_ for _ in ()).throw(SourceInspectionError("nonfinite input")),
        )
        print(json.dumps(replay(value), sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        print("nwi-snapshot-replay-rejected: incomplete or invalid evidence", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
