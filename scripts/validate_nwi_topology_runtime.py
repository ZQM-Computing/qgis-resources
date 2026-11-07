"""Offline actual GDAL/OGR topology check for quarantined NWI inspection data.

No agency requests, client parcels, or customer-facing conclusions are made.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from urllib.parse import parse_qs, urlsplit

from nwi_source_inspector import (
    LAYER_URL, SourceInspectionError, collect, _validate_coords,
)
from nwi_topology_gate import STATUS, main, validate_path, validate_snapshot

BOX = (-81.01, 29.01, -81.0, 29.02)


def _feature(geometry: dict) -> dict:
    """Wrap synthetic geometry in an NWI feature with the required properties."""
    return {
        "type": "Feature",
        "properties": {
            "OBJECTID": 1,
            "ATTRIBUTE": "PFO1A",
            "WETLAND_TYPE": "Freshwater Forested/Shrub Wetland",
        },
        "geometry": geometry,
    }


def _polygon(ring: list[list[float]]) -> dict:
    """Wrap a synthetic ring in a GeoJSON polygon."""
    return {"type": "Polygon", "coordinates": [ring]}


def _mock_fetch(url: str) -> dict:
    """Serve synthetic layer metadata, counts and features without network access."""
    if urlsplit(url).path == urlsplit(LAYER_URL).path:
        return {
            "id": 0,
            "name": "Wetlands",
            "geometryType": "esriGeometryPolygon",
            "capabilities": "Map,Query,Data",
            "supportedQueryFormats": "JSON, geoJSON, PBF",
            "maxRecordCount": 500,
            "fields": [
                {"name": "OBJECTID", "type": "esriFieldTypeOID"},
                {"name": "ATTRIBUTE", "type": "esriFieldTypeString"},
                {"name": "WETLAND_TYPE", "type": "esriFieldTypeString"},
            ],
            "advancedQueryCapabilities": {
                "supportsPagination": True, "supportsOrderBy": True,
            },
        }
    query = parse_qs(urlsplit(url).query)
    if query.get("returnCountOnly") == ["true"]:
        return {"count": 1}
    return {
        "type": "FeatureCollection",
        "features": [_feature(_polygon([
            [-81.009, 29.011],
            [-81.005, 29.011],
            [-81.005, 29.015],
            [-81.009, 29.011],
        ]))],
    }


def _fail(snapshot: dict) -> None:
    """Require the OGR gate to reject an invalid snapshot."""
    try:
        validate_snapshot(snapshot)
    except SourceInspectionError:
        return
    raise AssertionError("Invalid source input unexpectedly passed GDAL quarantine gate")


def run() -> None:
    """Verify valid input, corrupted hashes and self-intersecting real OGR geometry."""
    snapshot = collect(BOX, _mock_fetch, obtained_at="2026-11-07T20:00:00Z")
    original = deepcopy(snapshot)
    passed = validate_snapshot(snapshot)
    assert passed["status"] == STATUS
    assert passed["features_topologically_validated"] == 1
    assert passed["coverage_state"] == "unverified"
    assert passed["reuse_rights"] == "unverified"
    assert passed["human_review"] == "pending"
    assert passed["regulatory_determination"] is False
    assert original == snapshot, "Topology validation mutated input"

    with tempfile.TemporaryDirectory(prefix="zqm-nwi-gdal-") as dirname:
        root = Path(dirname)
        source = root / "snapshot.json"
        data = json.dumps(snapshot, sort_keys=True).encode("utf-8")
        source.write_bytes(data)
        assert validate_path(source) == passed
        assert main([str(source)]) == 0
        assert source.read_bytes() == data
        assert sorted(p.name for p in root.iterdir()) == ["snapshot.json"]

    modified = deepcopy(snapshot)
    modified["feature_collection"]["features"][0]["geometry"]["coordinates"][0][1][0] += 0.0002
    _fail(modified)  # source checksum does not match normalized features

    modified = deepcopy(snapshot)
    modified["source"]["request_bbox_epsg4326"] = None
    _fail(modified)

    modified = deepcopy(snapshot)
    modified["source"]["features_reconciled"] = 2
    _fail(modified)

    # A self-crossing quadrilateral can have nonzero shoelace area.
    # Stdlib parsing accepts this ring's structure; GEOS-backed IsValid must not.
    bow_tie = [
        [-81.009, 29.011],
        [-81.005, 29.015],
        [-81.009, 29.014],
        [-81.007, 29.011],
        [-81.009, 29.011],
    ]
    geometry = _polygon(bow_tie)
    assert _validate_coords(geometry) == 5
    invalid = deepcopy(snapshot)
    invalid["feature_collection"]["features"][0]["geometry"] = geometry
    normalized = invalid["feature_collection"]
    invalid["source"]["normalized_geojson_sha256"] = sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    _fail(invalid)  # not enough to recompute an unkeyed checksum

    print(json.dumps({
        "case": "NWI quarantined snapshot OGR topology and checksum",
        "status": "passed",
        "features": passed["features_topologically_validated"],
        "source_data": "mocked-synthetic-only",
        "real_data_approved": False,
    }, sort_keys=True))


if __name__ == "__main__":
    run()
