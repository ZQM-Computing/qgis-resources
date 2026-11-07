"""Dependency-free tests for synthetic report bundle publication and formatting."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import screening_report as report  # noqa: E402


def bundle_bytes(marker: str = "original") -> bytes:
    """Create a small valid archive for publication tests without a spatial runtime."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as handle:
        for name in report.ARCHIVE_FILES:
            handle.writestr(name, marker.encode())
    return buffer.getvalue()


def test_publish_atomic_create_rejects_duplicate_and_protects_existing(tmp_path):
    """Verify publish atomic create rejects duplicate and protects existing."""
    destination = tmp_path / "screening.zip"
    original = bundle_bytes()
    digest = report.publish_bundle(destination, original)
    assert digest == sha256(original).hexdigest()
    assert destination.read_bytes() == original
    with pytest.raises(report.ScreeningError, match="already exists"):
        report.publish_bundle(destination, bundle_bytes("new"))
    assert destination.read_bytes() == original
    revised = bundle_bytes("new")
    assert report.publish_bundle(destination, revised, overwrite=True) == sha256(revised).hexdigest()
    assert destination.read_bytes() == revised
    assert not list(tmp_path.glob(".zqm-screening-*"))


def test_failed_publication_leaves_no_partial_or_temp_file(tmp_path, monkeypatch):
    """Verify failed publication leaves no partial or temp file."""
    destination = tmp_path / "screening.zip"

    def reject_link(*args, **kwargs):
        """Simulate a filesystem publication failure before the destination is created."""
        raise OSError("simulated atomic link failure")

    monkeypatch.setattr(report.os, "link", reject_link)
    with pytest.raises(OSError):
        report.publish_bundle(destination, bundle_bytes())
    assert not destination.exists()
    assert not list(tmp_path.glob(".zqm-screening-*"))


def test_invalid_archive_or_destination_rejected_without_writes(tmp_path):
    """Verify invalid archive or destination rejected without writes."""
    with pytest.raises(report.ScreeningError, match="integrity"):
        report.publish_bundle(tmp_path / "bad.zip", b"not-a-zip")
    with pytest.raises(report.ScreeningError, match="must be"):
        report.publish_bundle(tmp_path / "bad.json", bundle_bytes())
    with pytest.raises(report.ScreeningError, match="real directory"):
        report.publish_bundle(tmp_path / "absent" / "out.zip", bundle_bytes())
    assert list(tmp_path.iterdir()) == []


def test_refuses_symlink_output_even_with_overwrite(tmp_path):
    """Verify refuses symlink output even with overwrite."""
    target = tmp_path / "protected.txt"
    target.write_text("untouched")
    symlink = tmp_path / "screening.zip"
    try:
        symlink.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks not supported by this environment")
    with pytest.raises(report.ScreeningError, match="non-symlink"):
        report.publish_bundle(symlink, bundle_bytes(), overwrite=True)
    assert target.read_text() == "untouched"


def test_report_markdown_is_explicit_about_missing_data_and_source_limitations():
    """Verify report markdown is explicit about missing data and source limitations."""
    manifest = {
        "project_id": "demo",
        "jurisdiction": {"country_code": "US", "region": "synthetic"},
    }
    measurements = {
        "study_area_m2": 1000,
        "method": "projected",
        "source_results": [
            {
                "source_id": "mapped", "declared_coverage": "verified",
                "finding": "synthetic-mapped-overlap",
                "measured_intersection_area_m2": 200,
                "measured_intersection_percent": 20,
            },
            {
                "source_id": "missing", "declared_coverage": "unavailable",
                "finding": "coverage-unavailable-no-absence-inference",
                "measured_intersection_area_m2": None,
                "measured_intersection_percent": None,
            },
        ],
    }
    first = {
        "id": "mapped", "authority": "source|title", "source_reference": "fixtures/polygon.geojson",
        "fixture_sha256": "abc123", "license_claimed": "test only", "reuse_rights_claimed": "approved",
        "effective_date_claimed": None, "retrieved_at_utc_claimed": "2026-11-07T00:00:00Z",
        "limitations": "synthetic|not regulatory",
    }
    second = {**first, "id": "missing", "source_reference": None, "fixture_sha256": None}
    rendered = report._markdown(manifest, measurements, [first, second])
    assert "Not assessed" in rendered
    assert "coverage-unavailable-no-absence-inference" in rendered
    assert r"source\|title" in rendered
    assert r"synthetic\|not regulatory" in rendered
    assert "REVIEW" not in rendered or "review" in rendered.lower()
    assert "NOT A CUSTOMER DELIVERABLE" in rendered
    assert "pending" in rendered


def test_archive_file_list_is_stable_and_reproducible():
    """Verify archive file list is stable and reproducible."""
    original = bundle_bytes()
    with zipfile.ZipFile(BytesIO(original)) as handle:
        assert tuple(sorted(handle.namelist())) == report.ARCHIVE_FILES
    assert original == bundle_bytes()
    assert report._json_bytes({"b": 2, "a": 1}) == b'{\n  "a": 1,\n  "b": 2\n}\n'


def test_optional_source_register_fields_are_null_when_unavailable_source_omits_them():
    """Verify optional source register fields are null when unavailable source omits them."""
    import copy
    import json
    manifest = json.loads((ROOT / "fixtures" / "screening-manifest.json").read_text(encoding="utf-8"))
    unknown = copy.deepcopy(manifest["sources"][1])
    for field in ("source_ref", "license", "retrieved_at_utc", "effective_date", "crs"):
        unknown.pop(field, None)
    manifest["sources"][1] = unknown
    from screening_manifest import validate_manifest
    assert validate_manifest(manifest) == []
    measurements = {
        "source_results": [
            {"finding": "synthetic-mapped-overlap"},
            {"finding": "coverage-unavailable-no-absence-inference"},
        ],
    }
    sources = report._source_register(manifest, ROOT, measurements)
    for field in ("source_reference", "license_claimed", "retrieved_at_utc_claimed", "effective_date_claimed", "declared_crs"):
        assert sources[1][field] is None
    parsed = json.loads(report._json_bytes(sources))
    assert parsed[1]["source_reference"] is None
