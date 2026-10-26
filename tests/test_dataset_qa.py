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

def test_markdown_report_escapes_untrusted_metadata_in_table_cells():
    report = {
        "dataset_count": 1,
        "datasets": [{
            "path": "inputs/roads|east.gpkg",
            "kind": "vector",
            "crs": "EPSG:4326|candidate",
            "layers": [{
                "name": "roads|east\nsecond-line",
                "feature_count": 2,
                "geometry_type": "Line|String",
            }],
        }],
        "findings": [qa.finding(
            "VECTOR_FIELD_MISSING", "warning", "Missing | field\nneeds review",
            dataset="inputs/roads|east.gpkg", layer="roads|east",
            remediation="Check | source\nmetadata.",
        )],
        "summary": {"error": 0, "warning": 1, "info": 0, "total": 1},
    }
    markdown = qa.markdown_report(report)
    inventory_row = next(line for line in markdown.splitlines() if "inputs/roads" in line)
    assert r"inputs/roads\\|east.gpkg" in inventory_row
    assert r"roads\\|east second-line" in inventory_row
    assert r"EPSG:4326\\|candidate" in inventory_row
    finding_row = next(line for line in markdown.splitlines() if "VECTOR_FIELD_MISSING" in line)
    assert r"Missing \\| field needs review" in finding_row
    assert r"Check \\| source metadata." in finding_row


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


def test_crs_comparison_accepts_equivalent_authority_and_wkt_forms():
    # No GDAL dependency for the fallback form; real semantic comparison is
    # exercised by the GDAL runtime test.
    assert qa._crs_matches(" EPSG:4326 ", "epsg:4326")


def test_audit_paths_supports_excluding_generated_report_paths():
    source = (ROOT / "scripts" / "dataset_qa.py").read_text(encoding="utf-8")
    assert "exclude_paths: list[Path] | None = None" in source
    assert "exclude_paths=[args.json_path" in source


def test_provider_exception_evidence_does_not_include_raw_exception_text():
    source = (ROOT / "scripts" / "dataset_qa.py").read_text(encoding="utf-8")
    assert 'evidence={"error_type": type(exc).__name__}' in source
    assert 'evidence={"error_type": type(exc).__name__, "message": str(exc)}' not in source

def test_cli_exit_code_and_reports_for_clean_dataset_run(tmp_path, monkeypatch, capsys):
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    report = {
        "schema_version": 1,
        "root": ".",
        "dataset_count": 0,
        "datasets": [],
        "findings": [],
        "summary": {"error": 0, "warning": 0, "info": 0, "total": 0},
        "unreadable_datasets": [],
    }
    captured = {}

    def fake_audit_paths(paths, **kwargs):
        captured["paths"] = paths
        captured.update(kwargs)
        return report

    monkeypatch.setattr(qa, "audit_paths", fake_audit_paths)
    assert qa.main([str(tmp_path), "--json", str(output_json), "--markdown", str(output_md)]) == 0
    assert output_json.exists()
    assert output_md.exists()
    assert '"error": 0' in capsys.readouterr().out
    assert captured["exclude_paths"] == [output_json, output_md]


def test_cli_fail_on_warning_returns_nonzero(tmp_path, monkeypatch):
    report = {
        "schema_version": 1,
        "root": ".",
        "dataset_count": 0,
        "datasets": [],
        "findings": [qa.finding("VECTOR_LAYER_EMPTY", "warning", "empty", dataset="x.gpkg")],
        "summary": {"error": 0, "warning": 1, "info": 0, "total": 1},
        "unreadable_datasets": [],
    }
    monkeypatch.setattr(qa, "audit_paths", lambda paths, **kwargs: report)
    assert qa.main([str(tmp_path), "--json", str(tmp_path / "report.json"), "--fail-on-warning"]) == 1


def test_cli_returns_nonzero_when_errors_are_reported(tmp_path, monkeypatch):
    report = {
        "schema_version": 1,
        "root": ".",
        "dataset_count": 0,
        "datasets": [],
        "findings": [qa.finding("VECTOR_CRS_MISSING", "error", "missing CRS", dataset="x.gpkg")],
        "summary": {"error": 1, "warning": 0, "info": 0, "total": 1},
        "unreadable_datasets": ["x.gpkg"],
    }
    monkeypatch.setattr(qa, "audit_paths", lambda paths, **kwargs: report)
    assert qa.main([str(tmp_path), "--json", str(tmp_path / "report.json")]) == 1




def test_report_destinations_cannot_overwrite_input_datasets(tmp_path):
    source = tmp_path / "source.tif"
    source.write_bytes(b"source dataset")
    report = tmp_path / "report.json"
    qa._validate_report_destinations([source], report, None)
    try:
        qa._validate_report_destinations([source], source, None)
    except ValueError as exc:
        assert "matches an input dataset" in str(exc)
    else:
        raise AssertionError("Report destination was allowed to overwrite an input dataset")
    assert source.read_bytes() == b"source dataset"


def test_json_and_markdown_report_destinations_must_be_distinct(tmp_path):
    destination = tmp_path / "report.out"
    try:
        qa._validate_report_destinations([], destination, destination)
    except ValueError as exc:
        assert "must be different files" in str(exc)
    else:
        raise AssertionError("Conflicting report destinations were accepted")


def test_report_destination_collision_is_rejected_before_audit(tmp_path, monkeypatch):
    source = tmp_path / "source.gpkg"
    source.write_bytes(b"immutable input")
    monkeypatch.setattr(qa, "audit_paths", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("audit must not run after an output collision")
    ))
    try:
        qa.main([str(source), "--json", str(source)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("CLI did not reject output collision")
    assert source.read_bytes() == b"immutable input"



def test_existing_json_report_inside_scanned_root_can_be_replaced(tmp_path):
    import json

    report = tmp_path / "report.json"
    report.write_text(json.dumps({
        "schema_version": 1,
        "root": ".",
        "dataset_count": 0,
        "datasets": [],
        "findings": [],
        "summary": {"error": 0, "warning": 0, "info": 0, "total": 0},
        "unreadable_datasets": [],
    }), encoding="utf-8")
    qa._validate_report_destinations([tmp_path], report, None)


def test_existing_geojson_input_is_not_mistaken_for_prior_report(tmp_path):
    source = tmp_path / "features.geojson"
    source.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    try:
        qa._validate_report_destinations([tmp_path], source, None)
    except ValueError as exc:
        assert "matches an input dataset" in str(exc)
    else:
        raise AssertionError("GeoJSON input collision was not rejected")

def test_cli_rejects_missing_input_paths_before_audit_or_report_creation(tmp_path, monkeypatch):
    missing = tmp_path / "does-not-exist.gpkg"
    output = tmp_path / "report.json"
    monkeypatch.setattr(qa, "audit_paths", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("audit must not run when an input path is missing")
    ))
    try:
        qa.main([str(missing), "--json", str(output)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("CLI accepted a missing input path")
    assert not output.exists()

def test_empty_scan_is_reported_as_an_error(tmp_path, monkeypatch):
    import sys
    import types

    gdal = types.SimpleNamespace(UseExceptions=lambda: None)
    ogr = types.SimpleNamespace(UseExceptions=lambda: None)
    monkeypatch.setitem(sys.modules, "osgeo", types.SimpleNamespace(gdal=gdal, ogr=ogr))

    report = qa.audit_paths([tmp_path], root=tmp_path)
    assert report["dataset_count"] == 0
    assert any(item["rule_id"] == "NO_SUPPORTED_DATASETS_FOUND"
               and item["severity"] == "error" for item in report["findings"])
    assert report["summary"]["error"] >= 1


def test_explicit_unsupported_file_is_not_silently_ignored(tmp_path, monkeypatch):
    import sys
    import types

    source = tmp_path / "notes.txt"
    source.write_text("not a geospatial dataset", encoding="utf-8")
    gdal = types.SimpleNamespace(UseExceptions=lambda: None)
    ogr = types.SimpleNamespace(UseExceptions=lambda: None)
    monkeypatch.setitem(sys.modules, "osgeo", types.SimpleNamespace(gdal=gdal, ogr=ogr))

    report = qa.audit_paths([source], root=tmp_path)
    assert report["dataset_count"] == 0
    rules = {item["rule_id"] for item in report["findings"]}
    assert "INPUT_FORMAT_UNSUPPORTED" in rules
    assert "NO_SUPPORTED_DATASETS_FOUND" in rules

def test_vector_dataset_with_no_layers_is_an_error(tmp_path):
    class Driver:
        @staticmethod
        def GetName():
            return "FakeVector"

    class Dataset:
        @staticmethod
        def GetDriver():
            return Driver()

        @staticmethod
        def GetLayerCount():
            return 0

    class OGR:
        @staticmethod
        def Open(path, mode):
            assert mode == 0
            return Dataset()

    source = tmp_path / "empty.gpkg"
    source.write_bytes(b"fake dataset")
    result = qa._audit_vector(
        source, "empty.gpkg", object(), OGR(),
        required_fields=[], id_fields=[], expected_crs=None, check_geometry=True,
    )
    assert result is not None
    assert result["inventory"]["layers"] == []
    assert any(item["rule_id"] == "VECTOR_DATASET_NO_LAYERS"
               and item["severity"] == "error" for item in result["findings"])



def test_vector_report_states_identifier_coverage_and_skipped_geometry_checks(tmp_path):
    class FieldDefn:
        def __init__(self, name):
            self.name = name

        def GetName(self):
            return self.name

        def GetTypeName(self):
            return "String"

    class LayerDefn:
        def GetFieldCount(self):
            return 1

        def GetFieldDefn(self, index):
            assert index == 0
            return FieldDefn("asset_id")

    class Feature:
        def __init__(self, value):
            self.value = value

        def GetField(self, index):
            assert index == 0
            return self.value

        def GetGeometryRef(self):
            raise AssertionError("geometry access must be skipped when disabled")

    class Layer:
        def __init__(self):
            self.features = iter([Feature(None), Feature("A-1"), Feature("A-1")])

        def GetName(self):
            return "assets"

        def GetSpatialRef(self):
            return None

        def GetLayerDefn(self):
            return LayerDefn()

        def GetFeatureCount(self, force=1):
            return 3

        def GetGeomType(self):
            return 1

        def ResetReading(self):
            self.features = iter([Feature(None), Feature("A-1"), Feature("A-1")])

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.features)

    class Driver:
        def GetName(self):
            return "FakeVector"

    class Dataset:
        def GetDriver(self):
            return Driver()

        def GetLayerCount(self):
            return 1

        def GetLayerByIndex(self, index):
            assert index == 0
            return Layer()

    class OGR:
        @staticmethod
        def Open(path, mode):
            assert mode == 0
            return Dataset()

        @staticmethod
        def GeometryTypeToName(_):
            return "Point"

    source = tmp_path / "assets.gpkg"
    source.write_bytes(b"fake vector")
    result = qa._audit_vector(
        source, "assets.gpkg", object(), OGR(),
        required_fields=[], id_fields=["asset_id", "fid"],
        expected_crs=None, check_geometry=False,
    )

    layer = result["inventory"]["layers"][0]
    assert layer["identifier_check"] == {
        "enabled": True,
        "status": "checked",
        "configured_fields": ["asset_id", "fid"],
        "selected_field": "asset_id",
        "null_or_blank_count": 1,
        "duplicate_occurrences": 1,
    }
    assert layer["geometry_checks"]["enabled"] is False
    assert layer["geometry_checks"]["status"] == "disabled_by_option"
    assert layer["geometry_checks"]["checked_nonempty"] == 0
    assert not any(item["rule_id"] == "VECTOR_GEOMETRY_INVALID"
                   for item in result["findings"])


def test_vector_report_distinguishes_unconfigured_identifier_check(tmp_path):
    class Definition:
        def GetFieldCount(self):
            return 0

    class Layer:
        def GetName(self):
            return "roads"

        def GetSpatialRef(self):
            return None

        def GetLayerDefn(self):
            return Definition()

        def GetFeatureCount(self, force=1):
            return 0

        def GetGeomType(self):
            return 1

        def ResetReading(self):
            pass

        def __iter__(self):
            return iter(())

    class Driver:
        def GetName(self):
            return "FakeVector"

    class Dataset:
        def GetDriver(self):
            return Driver()

        def GetLayerCount(self):
            return 1

        def GetLayerByIndex(self, index):
            return Layer()

    class OGR:
        @staticmethod
        def Open(path, mode):
            return Dataset()

        @staticmethod
        def GeometryTypeToName(_):
            return "Line String"

    source = tmp_path / "roads.gpkg"
    source.write_bytes(b"fake vector")
    result = qa._audit_vector(
        source, "roads.gpkg", object(), OGR(),
        required_fields=[], id_fields=[], expected_crs=None, check_geometry=True,
    )
    layer = result["inventory"]["layers"][0]
    assert layer["identifier_check"]["status"] == "not_configured"
    assert layer["identifier_check"]["selected_field"] is None
    assert layer["geometry_checks"]["status"] == "enabled"


def test_raster_inventory_preserves_rotated_extent_and_band_metadata(tmp_path):
    class Driver:
        ShortName = "GTiff"

    class Band:
        DataType = 6

        def GetNoDataValue(self):
            return float("nan")

        def GetScale(self):
            return 2.0

        def GetOffset(self):
            return -1.0

        def GetBlockSize(self):
            return (16, 16)

    class Dataset:
        RasterXSize = 10
        RasterYSize = 5
        RasterCount = 1

        def GetProjectionRef(self):
            return ""

        def GetGeoTransform(self, can_return_null=True):
            # x = 100 + 2*col + 3*row; y = 200 + 4*col - 5*row
            return (100, 2, 3, 200, 4, -5)

        def GetDriver(self):
            return Driver()

        def GetRasterBand(self, index):
            assert index == 1
            return Band()

    class GDAL:
        GA_ReadOnly = 0

        @staticmethod
        def Open(path, mode):
            assert mode == 0
            return Dataset()

        @staticmethod
        def GetDataTypeName(_):
            return "Float32"

    source = tmp_path / "rotated.tif"
    source.write_bytes(b"fake raster")
    result = qa._audit_raster(source, "rotated.tif", GDAL(), expected_crs=None)
    assert result is not None
    inventory = result["inventory"]
    # All four affine corners are considered; rotation terms are not dropped.
    assert inventory["extent"] == {
        "xmin": 100, "ymin": 175, "xmax": 135, "ymax": 240,
    }
    assert inventory["resolution"] == [
        (2 ** 2 + 4 ** 2) ** 0.5,
        (3 ** 2 + (-5) ** 2) ** 0.5,
    ]
    assert inventory["bands"] == [{
        "index": 1, "data_type": "Float32", "nodata": "nan",
        "scale": 2.0, "offset": -1.0, "block_size": [16, 16],
    }]


def test_raster_nonfinite_geotransform_withholds_extent(tmp_path):
    class Driver:
        ShortName = "GTiff"

    class Dataset:
        RasterXSize = 4
        RasterYSize = 4
        RasterCount = 1

        def GetProjectionRef(self):
            return ""

        def GetGeoTransform(self, can_return_null=True):
            return (0, 1, 0, 0, float("inf"), -1)

        def GetDriver(self):
            return Driver()

        def GetRasterBand(self, index):
            return Band()

    class Band:
        DataType = 1

        def GetNoDataValue(self):
            return None

        def GetScale(self):
            return None

        def GetOffset(self):
            return None

        def GetBlockSize(self):
            return (4, 4)

    class GDAL:
        GA_ReadOnly = 0

        @staticmethod
        def GetDataTypeName(_):
            return "Byte"

        @staticmethod
        def Open(path, mode):
            return Dataset()

    source = tmp_path / "bad-transform.tif"
    source.write_bytes(b"fake raster")
    result = qa._audit_raster(source, "bad-transform.tif", GDAL(), expected_crs=None)
    assert result is not None
    assert result["inventory"]["extent"] is None
    assert result["inventory"]["resolution"] is None
    assert any(item["rule_id"] == "RASTER_GEOREFERENCE_NONFINITE"
               and item["severity"] == "error" for item in result["findings"])
    assert any(item["rule_id"] == "RASTER_CRS_MISSING"
               and item["severity"] == "error" for item in result["findings"])
