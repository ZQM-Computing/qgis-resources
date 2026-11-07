#!/usr/bin/env python3
"""Read-only GDAL/OGR topology gate for untrusted, unapproved NWI snapshots.

This is not a screening analysis, coverage verification, regulatory opinion,
certified delineation, licensed reuse approval, or source authentication.
It never requests network access or modifies the original inspection JSON.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from nwi_source_inspector import (
    LAYER_URL, MAX_FEATURES, MAX_OUTPUT_BYTES, MAX_VERTICES,
    SourceInspectionError, _bbox, _decode_json, _validate_coords,
)

# The source hash is a tamper-detection checksum, NOT a cryptographic signature.
STATUS = "quarantined-topology-reviewed-not-approved"


def validate_snapshot(snapshot: Any) -> dict[str, Any]:
    """Validate normalized feature checksum and OGR geometry topology in memory."""
    if not isinstance(snapshot, dict):
        raise SourceInspectionError("Snapshot must be an object")
    if (snapshot.get("schema_version") != 1
            or snapshot.get("status") != "inspection-only-not-screened"
            or snapshot.get("coverage_state") != "unverified"
            or snapshot.get("reuse_rights") != "unverified"
            or snapshot.get("human_review") != "pending"
            or snapshot.get("regulatory_determination") is not False):
        raise SourceInspectionError("Snapshot is not an unapproved source inspection")
    source = snapshot.get("source")
    if not isinstance(source, dict) or source.get("service") != LAYER_URL or source.get("layer_id") != 0:
        raise SourceInspectionError("Unrecognized source identity")
    if source.get("requested_output_crs") != "EPSG:4326":
        raise SourceInspectionError("Unsupported declared output coordinate system")
    _bbox(source.get("request_bbox_epsg4326"))
    collection = snapshot.get("feature_collection")
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
        raise SourceInspectionError("Invalid normalized feature collection")
    features = collection.get("features")
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise SourceInspectionError("Invalid normalized feature count")
    if type(source.get("features_reconciled")) is not int or source["features_reconciled"] != len(features):
        raise SourceInspectionError("Snapshot feature count mismatch")
    raw = json.dumps(collection, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest = sha256(raw).hexdigest()
    if source.get("normalized_geojson_sha256") != digest:
        raise SourceInspectionError("Normalized feature checksum mismatch")

    from osgeo import ogr

    last_objectid: int | None = None
    vertices = 0
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise SourceInspectionError("Malformed normalized feature")
        props = feature.get("properties")
        if not isinstance(props, dict):
            raise SourceInspectionError("Malformed normalized attributes")
        oid = props.get("OBJECTID")
        if (type(oid) is not int or feature.get("id") != oid
                or (last_objectid is not None and oid <= last_objectid)):
            raise SourceInspectionError("Missing, inconsistent or unordered source identifier")
        last_objectid = oid
        for field in ("ATTRIBUTE", "WETLAND_TYPE"):
            if not isinstance(props.get(field), str) or not props[field].strip():
                raise SourceInspectionError("Missing source class attributes")
        geometry_data = feature.get("geometry")
        vertices += _validate_coords(geometry_data)
        if vertices > MAX_VERTICES:
            raise SourceInspectionError("Total source vertex limit exceeded")
        geometry = ogr.CreateGeometryFromJson(
            json.dumps(geometry_data, separators=(",", ":"), allow_nan=False)
        )
        if geometry is None or bool(geometry.IsEmpty()):
            raise SourceInspectionError("Unreadable or empty OGR geometry")
        kind = ogr.GT_Flatten(geometry.GetGeometryType())
        if kind not in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
            raise SourceInspectionError("Non-polygon OGR geometry")
        if not bool(geometry.IsValid()):
            raise SourceInspectionError("Invalid polygon topology; source quarantined")
        left, right, bottom, top = geometry.GetEnvelope()
        if not all(math.isfinite(x) for x in (left, right, bottom, top)):
            raise SourceInspectionError("Invalid OGR geographic coordinates")

    return {
        "status": STATUS,
        "source": LAYER_URL,
        "normalized_geojson_sha256": digest,
        "features_topologically_validated": len(features),
        "vertices_examined": vertices,
        "coverage_state": "unverified",
        "reuse_rights": "unverified",
        "human_review": "pending",
        "regulatory_determination": False,
        "limitations": (
            "This validates internal checksum and polygon topology only. The source "
            "is unauthenticated, mapping date/coverage and reuse rights are unverified; "
            "no parcel/environmental determination or customer delivery is permitted."
        ),
    }


def validate_path(path: Path) -> dict[str, Any]:
    """Read a bounded snapshot from disk without modifying it or the directory."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_OUTPUT_BYTES:
        raise SourceInspectionError("Snapshot path missing, symlinked or oversized")
    snapshot = _decode_json(path.read_bytes())
    return validate_snapshot(snapshot)


def main(argv: list[str] | None = None) -> int:
    """Print an inspection status only; never write data or contact an endpoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate_path(args.snapshot)
    except (OSError, ValueError, RuntimeError, ImportError, RecursionError, OverflowError):
        print("NWI topology check failed closed; source remains unapproved")
        return 1
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
