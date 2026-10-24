"""Tests for deterministic QA report contracts; dataset execution needs GDAL bindings."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dataset_qa", ROOT / "scripts" / "dataset_qa.py")
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


def test_finding_has_stable_schema_and_rejects_unknown_severity():
    item = qa.finding("VECTOR_CRS_MISSING", "error", "Missing CRS", dataset="data.gpkg", layer="roads")
    assert item == {
        "rule_id": "VECTOR_CRS_MISSING",
        "severity": "error",
        "dataset": "data.gpkg",
        "message": "Missing CRS",
        "remediation": "",
        "layer": "roads",
    }
    try:
        qa.finding("BAD", "critical", "invalid severity", dataset="x")
    except ValueError as exc:
        assert "Unsupported severity" in str(exc)
    else:
        raise AssertionError("Unknown severity should be rejected")


def test_findings_sort_by_severity_then_stable_location_and_rule():
    items = [
        qa.finding("Z", "warning", "second", dataset="b.gpkg"),
        qa.finding("A", "error", "first", dataset="z.gpkg"),
        qa.finding("B", "error", "second", dataset="a.gpkg"),
        qa.finding("C", "info", "third", dataset="a.gpkg"),
    ]
    assert [item["rule_id"] for item in qa.sort_findings(items)] == ["B", "A", "Z", "C"]


def test_summary_counts_findings_by_severity():
    items = [
        qa.finding("E", "error", "error", dataset="a"),
        qa.finding("W", "warning", "warning", dataset="a"),
        qa.finding("I", "info", "info", dataset="a"),
        qa.finding("W2", "warning", "warning 2", dataset="b"),
    ]
    assert qa.summarize(items) == {"error": 1, "warning": 2, "info": 1, "total": 4}


def test_markdown_report_includes_inventory_findings_and_read_only_notice():
    report = {
        "dataset_count": 1,
        "datasets": [{
            "path": "inputs/roads.gpkg", "kind": "vector", "crs": None,
            "layers": [{"name": "roads", "feature_count": 0, "geometry_type": "Line String"}],
        }],
        "findings": [qa.finding(
            "VECTOR_CRS_MISSING", "error", "No declared CRS", dataset="inputs/roads.gpkg",
            layer="roads", remediation="Check authoritative metadata.",
        )],
        "summary": {"error": 1, "warning": 0, "info": 0, "total": 1},
    }
    markdown = qa.markdown_report(report)
    assert "inputs/roads.gpkg" in markdown
    assert "MISSING" in markdown
    assert "VECTOR_CRS_MISSING" in markdown
    assert "Check authoritative metadata." in markdown
    assert "does not assign CRSs" in markdown


def test_dataset_qa_documents_real_gdal_inspection_and_read_only_open():
    source = (ROOT / "scripts" / "dataset_qa.py").read_text(encoding="utf-8")
    for contract in (
        "ogr.Open(str(path), 0)",
        "gdal.GA_ReadOnly",
        "GetFeatureCount",
        "GetSpatialRef",
        "GetRasterBand",
        "VECTOR_GEOMETRY_INVALID",
        "RASTER_CRS_MISSING",
        "VECTOR_REQUIRED_FIELD_MISSING",
        "sort_findings",
        "size_bytes",
        "math.hypot(float(transform[1]), float(transform[4]))",
        "math.hypot(float(transform[2]), float(transform[5]))",
    ):
        assert contract in source, f"Missing dataset QA contract: {contract}"



def test_json_safe_normalizes_nonfinite_metadata_without_invalid_json():
    import json
    report = {"nan": float("nan"), "positive": float("inf"), "negative": float("-inf")}
    safe = qa.json_safe(report)
    assert safe == {"nan": "nan", "positive": "infinity", "negative": "-infinity"}
    assert json.loads(json.dumps(safe, allow_nan=False)) == safe


def test_crs_placeholder_marked_undefined_is_not_reported_as_real_crs():
    class UndefinedSpatialReference:
        def GetAuthorityCode(self, _):
            return None

        def GetAuthorityName(self, _):
            return None

        def ExportToWkt(self):
            return 'LOCAL_CS["Undefined Cartesian SRS"]'

    assert qa._crs_text(UndefinedSpatialReference()) is None


def test_geometry_check_metadata_distinguishes_skipped_from_clean():
    source = (ROOT / "scripts" / "dataset_qa.py").read_text(encoding="utf-8")
    assert '"enabled": check_geometry' in source
    assert '"unchecked_validity": unchecked_geometries' in source
    assert "VECTOR_FEATURE_COUNT_UNKNOWN" in source
    assert "field_index_by_name" in source
    assert "RASTER_GEOREFERENCE_NONFINITE" in source
