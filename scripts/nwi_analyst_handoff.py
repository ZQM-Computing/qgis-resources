#!/usr/bin/env python3
"""Build a non-authorizing analyst handoff from an internally checked NWI archive.

No network requests, geometry screening, customer report, permit decision or
commercial source approval. A hash is an integrity fingerprint, not a signature.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nwi_snapshot_replay import replay
from nwi_source_inspector import (
    LAYER_URL, MAX_OUTPUT_BYTES, SourceInspectionError, _no_duplicates,
)

REVIEW_GATES = (
    "independently-authenticate-source-acquisition",
    "verify-per-project-mapping-and-imagery-vintage",
    "confirm-aoi-specific-mapped-coverage-and-known-gaps",
    "review-reuse-rights-and-redistribution-conditions",
    "independently-verify-study-boundary-and-coordinate-reference",
    "qualified-analyst-review-of-mapped-constraints",
)


def candidate_handoff(snapshot: dict) -> dict:
    """Produce metadata-only review candidate; fail on inconsistent snapshots."""
    result = replay(snapshot)
    if result["status"] != "INTERNAL_INTEGRITY_REPLAYED_NOT_APPROVED":
        raise SourceInspectionError("snapshot integrity not established")
    source = snapshot["source"]
    # Keep the complete requested bounding box for independent scope comparison.
    bbox = source["request_bbox_epsg4326"]
    digest = result["normalized_geojson_sha256"]
    # This is not the original provider response: only normalized data are hashed.
    if source.get("service") != LAYER_URL:
        raise SourceInspectionError("unexpected source endpoint")
    return {
        "schema_version": 1,
        "kind": "source-candidate-review-handoff",
        "status": "BLOCKED_PENDING_INDEPENDENT_SOURCE_REVIEW",
        "source_id": "usfws-nwi-wetlands",
        "source_layer_url": LAYER_URL,
        "requested_bbox_epsg4326": bbox,
        "normalized_feature_collection_sha256": digest,
        "normalized_feature_count": result["feature_count"],
        "normalized_vertex_count": result["vertex_count"],
        "integrity_replayed": True,
        "source_authenticity_verified": False,
        "project_mapping_date_verified": False,
        "aoi_coverage_verified": False,
        "reuse_rights_verified": False,
        "study_boundary_verified": False,
        "regulatory_determination": False,
        "commercial_delivery_authorized": False,
        "human_review_required": True,
        "review_gates": list(REVIEW_GATES),
        "notes": "Internal snapshot consistency only. Not a screening-manifest source, not wetlands absence, not legal delineation, not permission to use data commercially."
    }


def _load(path: Path) -> dict:
    with path.open("rb") as stream:
        data = stream.read(MAX_OUTPUT_BYTES + 1)
    if len(data) > MAX_OUTPUT_BYTES:
        raise SourceInspectionError("snapshot exceeds bounded size")
    return json.loads(
        data.decode("utf-8"),
        object_pairs_hook=_no_duplicates,
        parse_constant=lambda _: (_ for _ in ()).throw(
            SourceInspectionError("nonfinite JSON constant")
        ),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        handoff = candidate_handoff(_load(args.snapshot))
        print(json.dumps(handoff, sort_keys=True, indent=2, allow_nan=False))
        return 0  # Handoff constructed, never commercial approval.
    except (OSError, UnicodeError, TypeError, ValueError, KeyError):
        print("nwi-analyst-handoff-blocked: invalid or inconsistent snapshot", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
