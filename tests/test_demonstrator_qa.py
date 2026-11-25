"""Regression tests for synthetic GIS QA: never convert unknowns to PASS."""
import importlib.util
import sqlite3
from pathlib import Path

import pytest


QA_SCRIPT = Path(__file__).resolve().parents[1] / "demonstrators" / "qa-report" / "qa_report.py"


def load_qa(tmp_path, monkeypatch, with_gpkg=False):
    spec = importlib.util.spec_from_file_location("synthetic_demo_qa", QA_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "BASE_DIR", tmp_path)
    gpkg_path = tmp_path / "test.gpkg"
    monkeypatch.setattr(module, "GPKG_PATH", gpkg_path)
    if with_gpkg:
        gpkg_path.write_bytes(b"synthetic test placeholder")
    return module


def fixture_as_gpkg(module, monkeypatch, edit=None):
    fixture, layers = module.load_fixture_json()
    if edit is not None:
        edit(layers, fixture)
    register = fixture["source_register"]
    srs_by_layer = {"parcels": module.EXPECTED_EPSG, "wetland_indicator": module.EXPECTED_EPSG,
                    "flood_hazard": module.EXPECTED_EPSG}
    monkeypatch.setattr(module, "load_gpkg", lambda: (layers, srs_by_layer, register))


def test_missing_geopackage_uses_fixture_but_zero_coverage_remains_unknown(tmp_path, monkeypatch):
    qa = load_qa(tmp_path, monkeypatch)
    assert qa.main() == 0
    report = (tmp_path / "qa_report.md").read_text(encoding="utf-8")
    row = next(line for line in report.splitlines() if line.startswith("| DEMO-P2 | wetland |"))
    assert "| FLAG |" in row
    assert "NOT a verified overlap" in row
    assert "| Overlap accounting — recomputed vs stored (±1 m2) | FLAG |" in report


def test_present_corrupt_geopackage_cannot_silently_pass_as_fixture(tmp_path, monkeypatch):
    qa = load_qa(tmp_path, monkeypatch, with_gpkg=True)

    def broken():
        raise ValueError("parcels layer missing or empty in GeoPackage")

    monkeypatch.setattr(qa, "load_gpkg", broken)
    assert qa.main() == 1
    report = (tmp_path / "qa_report.md").read_text(encoding="utf-8")
    assert "| GeoPackage source integrity | FAIL |" in report
    assert "fell back to fixture" in report


def test_geopackage_without_parcels_rejected(tmp_path, monkeypatch):
    qa = load_qa(tmp_path, monkeypatch)
    with sqlite3.connect(qa.GPKG_PATH) as conn:
        conn.execute("CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, srs_id INTEGER)")
        conn.execute("INSERT INTO gpkg_geometry_columns VALUES ('wetland_indicator', 'geom', 32617)")
        conn.execute("CREATE TABLE wetland_indicator (id INTEGER, geom BLOB)")
    with pytest.raises(ValueError, match="parcels layer missing or empty"):
        qa.load_gpkg()


def test_missing_geopackage_stored_overlap_is_unverified(tmp_path, monkeypatch):
    qa = load_qa(tmp_path, monkeypatch, with_gpkg=True)

    def remove_stored(layers, _fixture):
        layers["parcels"][0]["stored"]["wetland_overlap_m2"] = None

    fixture_as_gpkg(qa, monkeypatch, remove_stored)
    assert qa.main() == 0  # A flagged measurement is not a structural failure.
    report = (tmp_path / "qa_report.md").read_text(encoding="utf-8")
    row = next(line for line in report.splitlines() if line.startswith("| DEMO-P1 | wetland |"))
    assert "| FLAG |" in row
    assert "stored wetland overlap is missing" in row


def test_blank_accessed_timestamp_fails_even_if_effective_date_exists(tmp_path, monkeypatch):
    qa = load_qa(tmp_path, monkeypatch, with_gpkg=True)

    def remove_accessed(_layers, fixture):
        fixture["source_register"][0]["accessed"] = ""
        fixture["source_register"][0]["effective_date"] = "2026-11-02"

    fixture_as_gpkg(qa, monkeypatch, remove_accessed)
    assert qa.main() == 1
    report = (tmp_path / "qa_report.md").read_text(encoding="utf-8")
    assert "accessed_utc missing or blank" in report
    assert "| Source freshness" in report
