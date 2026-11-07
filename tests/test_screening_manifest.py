"""Synthetic, dependency-free tests for screening metadata contract, not spatial QA."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("screening_manifest", ROOT / "scripts" / "screening_manifest.py")
manifest_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manifest_module)
FIXTURE = ROOT / "fixtures" / "screening-manifest.json"


def sample():
    """Load a fresh synthetic manifest for each independent test case."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_synthetic_contract_is_valid_and_source_files_exist():
    """Verify synthetic contract is valid and source files exist."""
    manifest = sample()
    assert manifest_module.validate_manifest(manifest) == []
    assert manifest_module.main([str(FIXTURE)]) == 0
    assert (ROOT / manifest["study_area"]["reference"]).is_file()
    for source in manifest["sources"]:
        if source["origin"] == "synthetic" and source["source_ref"]:
            assert (ROOT / source["source_ref"]).is_file()


def test_synthetic_geometries_are_structural_fixtures_not_spatial_proof():
    """Verify synthetic geometries are structural fixtures not spatial proof."""
    for path in ("screening-aoi.geojson", "synthetic-wetlands.geojson"):
        feature_collection = json.loads((ROOT / "fixtures" / path).read_text(encoding="utf-8"))
        assert feature_collection["type"] == "FeatureCollection"
        assert feature_collection["features"]
        for feature in feature_collection["features"]:
            assert feature["geometry"]["type"] == "Polygon"
            ring = feature["geometry"]["coordinates"][0]
            assert len(ring) >= 4 and ring[0] == ring[-1]


def test_unverified_sources_never_become_no_constraints():
    """Verify unverified sources never become no constraints."""
    manifest = sample()
    assert manifest_module.assess_source_state(manifest["sources"][0]) == "coverage-claimed-analysis-not-performed"
    assert manifest_module.assess_source_state(manifest["sources"][1]) == "not-assessable"
    partial = {"coverage_state": "partial"}
    assert manifest_module.assess_source_state(partial) == "partial-coverage-no-absence-inference"


def test_duplicate_sources_and_unknown_coverage_fail_closed():
    """Verify duplicate sources and unknown coverage fail closed."""
    manifest = sample()
    manifest["sources"][1]["id"] = manifest["sources"][0]["id"]
    assert "sources[1].id: duplicate identifier" in manifest_module.validate_manifest(manifest)
    manifest["sources"][1]["coverage_state"] = "clear"
    assert "sources[1].coverage_state: invalid" in manifest_module.validate_manifest(manifest)


def test_missing_crs_rights_or_retrieval_time_rejects_usable_source():
    """Verify missing crs rights or retrieval time rejects usable source."""
    for field, value, expected in (
        ("crs", None, "crs: required"),
        ("reuse_rights", "unverified", "reuse_rights: usable"),
        ("license", "", "license: required"),
        ("retrieved_at_utc", None, "retrieved_at_utc: UTC"),
    ):
        manifest = sample()
        manifest["sources"][0][field] = value
        errors = manifest_module.validate_manifest(manifest)
        assert any(expected in item for item in errors), errors


def test_missing_source_cannot_claim_geometry_or_count_as_clear():
    """Verify missing source cannot claim geometry or count as clear."""
    manifest = sample()
    manifest["sources"][1]["source_ref"] = "fixtures/synthetic-wetlands.geojson"
    assert any("cannot assert source geometry" in err for err in manifest_module.validate_manifest(manifest))


def test_no_unreviewed_or_synthetic_delivery_approval():
    """Verify no unreviewed or synthetic delivery approval."""
    manifest = sample()
    manifest["human_review"] = "approved"
    assert "human_review: contract pilot cannot assert approval" in manifest_module.validate_manifest(manifest)
    manifest = sample()
    manifest["delivery_status"] = "published"
    assert "delivery_status: contract pilot must remain draft" in manifest_module.validate_manifest(manifest)


def test_external_source_reference_requires_https_and_no_embedded_credentials():
    """Verify external source reference requires https and no embedded credentials."""
    assert manifest_module._source_reference("external", "https://data.example.org/dataset.geojson")
    for url in (
        "http://data.example.org/dataset.geojson",
        "https://user:password@data.example.org/dataset.geojson",
        "file:///home/client/private.gpkg",
        "https://data.example.org/data#fragment",
    ):
        assert not manifest_module._source_reference("external", url)


def test_no_traversal_in_synthetic_references():
    """Verify no traversal in synthetic references."""
    for ref in ("../secrets", "fixtures/../secrets", "/tmp/source.geojson", "fixtures\\x.geojson", "https://x.test"):
        assert not manifest_module._source_reference("synthetic", ref)


def test_bad_types_nonfinite_duplicate_json_and_oversized_input_fail_closed(tmp_path):
    """Verify bad types nonfinite duplicate json and oversized input fail closed."""
    assert manifest_module.validate_manifest([]) == ["manifest: expected JSON object"]
    bad = sample()
    bad["project_id"] = ["list-is-not-an-identifier"]
    assert "project_id: expected safe opaque identifier" in manifest_module.validate_manifest(bad)
    duplicate = tmp_path / "dupe.json"
    duplicate.write_text('{"one":1,"one":2}', encoding="utf-8")
    assert manifest_module.main([str(duplicate)]) == 2
    nonfinite = tmp_path / "bad.json"
    nonfinite.write_text('{"x":NaN}', encoding="utf-8")
    assert manifest_module.main([str(nonfinite)]) == 2
    oversized = tmp_path / "large.json"
    oversized.write_bytes(b"x" * (manifest_module.MAX_MANIFEST_BYTES + 1))
    assert manifest_module.main([str(oversized)]) == 2


def test_validation_is_deterministic_and_does_not_mutate_input():
    """Verify validation is deterministic and does not mutate input."""
    manifest = sample()
    original = deepcopy(manifest)
    assert manifest_module.validate_manifest(manifest) == manifest_module.validate_manifest(manifest)
    assert manifest == original


def test_malformed_array_valued_metadata_is_reported_not_crashed():
    """Verify malformed array valued metadata is reported not crashed."""
    manifest = sample()
    manifest["study_area"]["boundary_basis"] = ["synthetic-not-surveyed"]
    manifest["service_tier"] = ["preliminary"]
    manifest["sources"][0]["origin"] = ["synthetic"]
    manifest["sources"][0]["coverage_state"] = ["verified"]
    manifest["sources"][0]["reuse_rights"] = ["approved"]
    errors = manifest_module.validate_manifest(manifest)
    assert any("boundary_basis: invalid" in error for error in errors)
    assert any("service_tier: invalid" in error for error in errors)
    assert any(".origin: invalid" in error for error in errors)
    assert any(".coverage_state: invalid" in error for error in errors)
    assert any(".reuse_rights: invalid" in error for error in errors)


def test_missing_source_file_returns_error_without_writing(tmp_path):
    """Verify missing source file returns error without writing."""
    absent = tmp_path / "absent.json"
    assert manifest_module.main([str(absent)]) == 2
    assert not absent.exists()


def test_dot_or_empty_relative_synthetic_source_path_is_rejected_not_crashed():
    """Verify dot or empty relative synthetic source path is rejected not crashed."""
    for ref in (".", "./", "fixtures", "fixtures/.", "fixtures/../fixture.geojson"):
        assert not manifest_module._source_reference("synthetic", ref)
        manifest = sample()
        manifest["study_area"]["reference"] = ref
        assert any("study_area.reference" in err for err in manifest_module.validate_manifest(manifest))
        manifest = sample()
        manifest["sources"][0]["source_ref"] = ref
        assert any("sources[0].source_ref" in err for err in manifest_module.validate_manifest(manifest))
