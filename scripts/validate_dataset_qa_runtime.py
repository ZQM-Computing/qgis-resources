"""Integration-test the dataset QA CLI against synthetic GDAL/OGR fixtures.

Run with the same GDAL-enabled Python used by QGIS:
  /usr/bin/python3 scripts/validate_dataset_qa_runtime.py
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

from osgeo import gdal, ogr, osr

from dataset_qa import audit_paths, markdown_report


def create_vector_fixture(path: Path) -> None:
    driver = ogr.GetDriverByName("GPKG")
    assert driver is not None, "GDAL build lacks GeoPackage vector driver"
    ds = driver.CreateDataSource(str(path))
    assert ds is not None, "Could not create synthetic GeoPackage"
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(4326) == 0
    layer = ds.CreateLayer("observations", srs, ogr.wkbPoint)
    assert layer is not None
    assert layer.CreateField(ogr.FieldDefn("asset_id", ogr.OFTString)) == 0
    assert layer.CreateField(ogr.FieldDefn("alternate_id", ogr.OFTString)) == 0
    for index, (value, x, y) in enumerate([("dup", 0, 0), ("dup", 1, 1), (None, 2, 2)]):
        feature = ogr.Feature(layer.GetLayerDefn())
        if value is not None:
            feature.SetField("asset_id", value)
        feature.SetField("alternate_id", f"alternate-{index + 1}")
        geometry = ogr.Geometry(ogr.wkbPoint)
        geometry.AddPoint_2D(x, y)
        feature.SetGeometry(geometry)
        assert layer.CreateFeature(feature) == 0
        feature = None
    # Missing geometry is distinct from a null identifier and should be reported.
    empty_feature = ogr.Feature(layer.GetLayerDefn())
    empty_feature.SetField("asset_id", "empty-geometry")
    empty_feature.SetField("alternate_id", "alternate-4")
    assert layer.CreateFeature(empty_feature) == 0
    empty_feature = None
    unreferenced = ds.CreateLayer("unreferenced", None, ogr.wkbPoint)
    assert unreferenced is not None
    feature = ogr.Feature(unreferenced.GetLayerDefn())
    geometry = ogr.Geometry(ogr.wkbPoint)
    geometry.AddPoint_2D(4, 5)
    feature.SetGeometry(geometry)
    assert unreferenced.CreateFeature(feature) == 0
    feature = None

    # A self-crossing polygon exercises topology validity independently from
    # the missing/empty-geometry cases in the point layer.
    invalid_layer = ds.CreateLayer("invalid_polygons", srs, ogr.wkbPolygon)
    assert invalid_layer is not None
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in [(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)]:
        ring.AddPoint_2D(x, y)
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    invalid_feature = ogr.Feature(invalid_layer.GetLayerDefn())
    invalid_feature.SetGeometry(polygon)
    assert invalid_layer.CreateFeature(invalid_feature) == 0
    invalid_feature = None
    ds = None


def create_raster_fixture(path: Path) -> None:
    driver = gdal.GetDriverByName("GTiff")
    assert driver is not None, "GDAL build lacks GeoTIFF driver"
    ds = driver.Create(str(path), 3, 2, 1, gdal.GDT_Int16)
    assert ds is not None, "Could not create synthetic GeoTIFF"
    ds.SetGeoTransform((100, 10, 0, 200, 0, -10))
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(4326) == 0
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999)
    band.WriteArray([[1, 2, 3], [4, 5, -9999]])
    band.FlushCache()
    ds = None


def create_rotated_raster_fixture(path: Path) -> None:
    """Create a raster whose rotation terms make axis swaps observable."""
    driver = gdal.GetDriverByName("GTiff")
    assert driver is not None
    ds = driver.Create(str(path), 2, 3, 1, gdal.GDT_Byte)
    assert ds is not None
    ds.SetGeoTransform((10, 2, 3, 20, 4, -5))
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(32617) == 0
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).WriteArray([[1, 2], [3, 4], [5, 6]])
    ds = None


def create_rotated_raster_fixture(path: Path) -> None:
    driver = gdal.GetDriverByName("GTiff")
    assert driver is not None, "GDAL build lacks GeoTIFF driver"
    ds = driver.Create(str(path), 3, 2, 1, gdal.GDT_Int16)
    assert ds is not None, "Could not create rotated synthetic GeoTIFF"
    # Non-zero rotation terms catch axis swaps in affine extent calculations.
    ds.SetGeoTransform((100, 10, 2, 200, 3, -10))
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(32617) == 0
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).WriteArray([[1, 2, 3], [4, 5, 6]])
    ds = None


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="zqm-dataset-qa-") as temporary:
        root = Path(temporary)
        vector_path = root / "synthetic.gpkg"
        raster_path = root / "synthetic.tif"
        rotated_raster_path = root / "rotated.tif"
        create_vector_fixture(vector_path)
        create_raster_fixture(raster_path)
        create_rotated_raster_fixture(rotated_raster_path)
        before = {path.name: path.read_bytes() for path in (vector_path, raster_path)}

        report = audit_paths(
            [vector_path, raster_path],
            root=root,
            required_fields=["required_name"],
            id_fields=["asset_id", "alternate_id"],
            expected_crs="EPSG:3857",
        )
        # Equivalent authority-code and WKT representations should not produce
        # a false CRS mismatch warning.
        srs_wkt = osr.SpatialReference()
        assert srs_wkt.ImportFromEPSG(4326) == 0
        assert __import__("dataset_qa")._crs_matches(srs_wkt.ExportToWkt(), "EPSG:4326")
        semantic_raster_report = audit_paths(
            [raster_path],
            root=root,
            expected_crs="EPSG:4326",
        )
        assert "RASTER_CRS_UNEXPECTED" not in {
            item["rule_id"] for item in semantic_raster_report["findings"]
        }, semantic_raster_report
        rules = {item["rule_id"] for item in report["findings"]}
        expected_rules = {
            "VECTOR_REQUIRED_FIELD_MISSING",
            "VECTOR_ID_DUPLICATE",
            "VECTOR_ID_NULL",
            "VECTOR_GEOMETRY_EMPTY",
            "VECTOR_GEOMETRY_INVALID",
            "VECTOR_CRS_MISSING",
            "VECTOR_CRS_UNEXPECTED",
            "RASTER_CRS_UNEXPECTED",
        }
        missing = expected_rules - rules
        assert not missing, f"Expected QA findings missing: {sorted(missing)}; got {sorted(rules)}"
        assert report["dataset_count"] == 2, report
        vector = next(item for item in report["datasets"] if item["kind"] == "vector")
        observations = next(layer for layer in vector["layers"] if layer["name"] == "observations")
        assert observations["feature_count"] == 4, observations
        assert observations["crs"] == "EPSG:4326", observations
        assert observations["geometry_checks"]["enabled"] is True, observations
        assert observations["geometry_checks"]["empty"] == 1, observations
        id_findings = {
            item["rule_id"]: item
            for item in report["findings"]
            if item["rule_id"] in {"VECTOR_ID_NULL", "VECTOR_ID_DUPLICATE"}
            and item.get("layer") == "observations"
        }
        assert id_findings["VECTOR_ID_NULL"]["evidence"]["fields"] == ["asset_id"], id_findings
        assert id_findings["VECTOR_ID_DUPLICATE"]["evidence"]["fields"] == ["asset_id"], id_findings
        invalid_polygons = next(layer for layer in vector["layers"] if layer["name"] == "invalid_polygons")
        assert invalid_polygons["geometry_checks"]["invalid"] == 1, invalid_polygons

        # The explicit performance option must mark geometry validation as
        # disabled rather than silently presenting skipped checks as clean.
        skipped_geometry_report = audit_paths(
            [vector_path],
            root=root,
            check_geometry=False,
        )
        skipped_vector = skipped_geometry_report["datasets"][0]
        skipped_observations = next(
            layer for layer in skipped_vector["layers"] if layer["name"] == "observations"
        )
        assert skipped_observations["geometry_checks"]["enabled"] is False
        assert skipped_observations["geometry_checks"]["empty"] == 0
        assert "VECTOR_GEOMETRY_EMPTY" not in {
            item["rule_id"] for item in skipped_geometry_report["findings"]
        }

        raster = next(item for item in report["datasets"] if item["kind"] == "raster")
        assert (raster["width"], raster["height"], raster["band_count"]) == (3, 2, 1), raster
        assert raster["crs"] == "EPSG:4326", raster
        assert raster["bands"][0]["nodata"] == -9999, raster
        assert raster["size_bytes"] == raster_path.stat().st_size, raster
        assert raster["resolution"] == [10.0, 10.0], raster
        assert raster["extent"] == {"xmin": 100.0, "ymin": 180.0, "xmax": 130.0, "ymax": 200.0}, raster

        rotated_report = audit_paths([rotated_raster_path], root=root)
        rotated = rotated_report["datasets"][0]
        assert rotated["extent"] == {
            "xmin": 100.0, "ymin": 180.0, "xmax": 134.0, "ymax": 209.0
        }, rotated
        assert math.isclose(rotated["resolution"][0], math.sqrt(109.0)), rotated
        assert math.isclose(rotated["resolution"][1], math.sqrt(104.0)), rotated
        qa_module = __import__("dataset_qa")
        encoded = json.dumps(qa_module.json_safe(report), sort_keys=True, allow_nan=False)
        assert json.loads(encoded)["summary"]["error"] >= 1
        # Reports commonly live under the scanned root. Existing JSON reports
        # must be excluded or a rerun would incorrectly ingest the report itself.
        prior_report = root / "dataset-report.json"
        prior_report.write_text('{"previous": true}', encoding="utf-8")
        directory_report = audit_paths(
            [root],
            root=root,
            exclude_paths=[prior_report],
        )
        assert directory_report["dataset_count"] == 2, directory_report
        assert "DATASET_UNREADABLE" not in {f["rule_id"] for f in directory_report["findings"]}

        repeat_report = audit_paths(
            [vector_path, raster_path],
            root=root,
            required_fields=["required_name"],
            id_fields=["asset_id", "alternate_id"],
            expected_crs="EPSG:3857",
        )
        repeat_encoded = json.dumps(qa_module.json_safe(repeat_report), sort_keys=True, allow_nan=False)
        assert repeat_encoded == encoded, "Repeated audits produced nondeterministic JSON reports"
        assert "VECTOR_ID_DUPLICATE" in markdown_report(report)
        assert before == {path.name: path.read_bytes() for path in (vector_path, raster_path)}, (
            "Dataset QA modified an input file"
        )

        # Rotation terms affect both axes of the affine transform. This fixture
        # catches extent calculations that accidentally swap GT(2) and GT(4).
        rotated_path = root / "rotated.tif"
        create_rotated_raster_fixture(rotated_path)
        rotated_report = audit_paths([rotated_path], root=root)
        rotated = rotated_report["datasets"][0]
        assert rotated["extent"] == {
            "xmin": 10.0, "ymin": 5.0, "xmax": 23.0, "ymax": 28.0
        }, rotated
        assert rotated["resolution"] == [
            __import__("math").hypot(2, 4), __import__("math").hypot(3, -5)
        ], rotated

        print(json.dumps({"status": "passed", "summary": report["summary"],
                          "datasets": report["dataset_count"], "rules": sorted(rules)}, sort_keys=True))


if __name__ == "__main__":
    main()
