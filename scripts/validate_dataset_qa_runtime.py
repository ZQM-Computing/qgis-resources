"""Integration-test the dataset QA CLI against synthetic GDAL/OGR fixtures.

Run with the same GDAL-enabled Python used by QGIS:
  /usr/bin/python3 scripts/validate_dataset_qa_runtime.py
"""
from __future__ import annotations

import json
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
    for value, x, y in [("dup", 0, 0), ("dup", 1, 1), (None, 2, 2)]:
        feature = ogr.Feature(layer.GetLayerDefn())
        if value is not None:
            feature.SetField("asset_id", value)
        geometry = ogr.Geometry(ogr.wkbPoint)
        geometry.AddPoint_2D(x, y)
        feature.SetGeometry(geometry)
        assert layer.CreateFeature(feature) == 0
        feature = None
    # Missing geometry is distinct from a null identifier and should be reported.
    empty_feature = ogr.Feature(layer.GetLayerDefn())
    empty_feature.SetField("asset_id", "empty-geometry")
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


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="zqm-dataset-qa-") as temporary:
        root = Path(temporary)
        vector_path = root / "synthetic.gpkg"
        raster_path = root / "synthetic.tif"
        create_vector_fixture(vector_path)
        create_raster_fixture(raster_path)
        before = {path.name: path.read_bytes() for path in (vector_path, raster_path)}

        report = audit_paths(
            [vector_path, raster_path],
            root=root,
            required_fields=["required_name"],
            id_fields=["asset_id"],
            expected_crs="EPSG:3857",
        )
        rules = {item["rule_id"] for item in report["findings"]}
        expected_rules = {
            "VECTOR_REQUIRED_FIELD_MISSING",
            "VECTOR_ID_DUPLICATE",
            "VECTOR_ID_NULL",
            "VECTOR_GEOMETRY_EMPTY",
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
        raster = next(item for item in report["datasets"] if item["kind"] == "raster")
        assert (raster["width"], raster["height"], raster["band_count"]) == (3, 2, 1), raster
        assert raster["crs"] == "EPSG:4326", raster
        assert raster["bands"][0]["nodata"] == -9999, raster
        assert raster["size_bytes"] == raster_path.stat().st_size, raster
        assert raster["resolution"] == [10.0, 10.0], raster
        assert raster["extent"] == {"xmin": 100.0, "ymin": 180.0, "xmax": 130.0, "ymax": 200.0}, raster
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
            id_fields=["asset_id"],
            expected_crs="EPSG:3857",
        )
        repeat_encoded = json.dumps(qa_module.json_safe(repeat_report), sort_keys=True, allow_nan=False)
        assert repeat_encoded == encoded, "Repeated audits produced nondeterministic JSON reports"
        assert "VECTOR_ID_DUPLICATE" in markdown_report(report)
        assert before == {path.name: path.read_bytes() for path in (vector_path, raster_path)}, (
            "Dataset QA modified an input file"
        )
        print(json.dumps({"status": "passed", "summary": report["summary"],
                          "datasets": report["dataset_count"], "rules": sorted(rules)}, sort_keys=True))


if __name__ == "__main__":
    main()
