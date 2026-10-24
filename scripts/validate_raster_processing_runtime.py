"""Synthetic integration test for patterns/02_raster_processing.py.

Run inside the QGIS/GDAL environment:
  QT_QPA_PLATFORM=offscreen /usr/bin/python3 scripts/validate_raster_processing_runtime.py
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

for qgis_path in ("/usr/share/qgis/python", "/usr/share/qgis/python/plugins"):
    if Path(qgis_path).is_dir() and qgis_path not in sys.path:
        sys.path.append(qgis_path)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from osgeo import gdal, ogr, osr  # noqa: E402

gdal.UseExceptions()
from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "zqm_raster_processing", ROOT / "patterns" / "02_raster_processing.py"
)
assert SPEC is not None and SPEC.loader is not None
raster_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(raster_module)


def create_dem(path: Path) -> None:
    driver = gdal.GetDriverByName("GTiff")
    assert driver is not None
    dataset = driver.Create(str(path), 20, 20, 1, gdal.GDT_Float32)
    assert dataset is not None
    dataset.SetGeoTransform((500000, 10, 0, 3200200, 0, -10))
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(32617) == 0
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-9999)
    values = [[float(col + row) for col in range(20)] for row in range(20)]
    assert band.WriteArray(np.asarray(values, dtype=np.float32)) == 0
    band.FlushCache()
    dataset = None


def create_boundary(path: Path) -> None:
    driver = ogr.GetDriverByName("GPKG")
    assert driver is not None
    dataset = driver.CreateDataSource(str(path))
    assert dataset is not None
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(32617) == 0
    layer = dataset.CreateLayer("boundary", srs, ogr.wkbPolygon)
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in [
        (500040, 3200160), (500160, 3200160),
        (500160, 3200040), (500040, 3200040), (500040, 3200160),
    ]:
        ring.AddPoint_2D(x, y)
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(polygon)
    assert layer.CreateFeature(feature) == 0
    feature = None
    dataset = None


def create_empty_boundary(path: Path) -> None:
    driver = ogr.GetDriverByName("GPKG")
    assert driver is not None
    dataset = driver.CreateDataSource(str(path))
    assert dataset is not None
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(32617) == 0
    assert dataset.CreateLayer("empty_boundary", srs, ogr.wkbPolygon) is not None
    dataset = None


def create_invalid_boundary(path: Path) -> None:
    driver = ogr.GetDriverByName("GPKG")
    assert driver is not None
    dataset = driver.CreateDataSource(str(path))
    assert dataset is not None
    srs = osr.SpatialReference()
    assert srs.ImportFromEPSG(32617) == 0
    layer = dataset.CreateLayer("invalid_boundary", srs, ogr.wkbPolygon)
    ring = ogr.Geometry(ogr.wkbLinearRing)
    # Self-crossing bow-tie polygon.
    for x, y in [
        (500040, 3200160), (500160, 3200040), (500160, 3200160),
        (500040, 3200040), (500040, 3200160),
    ]:
        ring.AddPoint_2D(x, y)
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(polygon)
    assert layer.CreateFeature(feature) == 0
    feature = None
    dataset = None


def main() -> None:
    QgsApplication.setPrefixPath("/usr", True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        from processing.core.Processing import Processing
        Processing.initialize()
        print("STAGE: Processing initialized", flush=True)
        with tempfile.TemporaryDirectory(prefix="zqm-raster-runtime-") as temporary:
            root = Path(temporary)
            dem_path = root / "synthetic_dem.tif"
            boundary_path = root / "study_boundary.gpkg"
            empty_boundary_path = root / "empty_boundary.gpkg"
            invalid_boundary_path = root / "invalid_boundary.gpkg"
            create_dem(dem_path)
            print("STAGE: synthetic DEM created", flush=True)
            create_boundary(boundary_path)
            print("STAGE: valid boundary created", flush=True)
            create_empty_boundary(empty_boundary_path)
            create_invalid_boundary(invalid_boundary_path)
            print("STAGE: invalid-input fixtures created", flush=True)
            dem_before = dem_path.read_bytes()
            boundary_before = boundary_path.read_bytes()

            print("STAGE: starting reprojection/clip/slope workflow", flush=True)
            original_processing_run = raster_module.processing.run

            def traced_processing_run(algorithm, parameters, *args, **kwargs):
                print(f"PROCESSING START: {algorithm}", flush=True)
                child_result = original_processing_run(algorithm, parameters, *args, **kwargs)
                print(f"PROCESSING END: {algorithm}", flush=True)
                return child_result

            raster_module.processing.run = traced_processing_run
            try:
                result = raster_module.raster_processing(
                    str(dem_path), str(boundary_path), "EPSG:32618", z_factor=1.0
                )
            finally:
                raster_module.processing.run = original_processing_run
            print("STAGE: reprojection/clip/slope workflow returned", flush=True)
            print("STAGE: checking result validity", flush=True)
            assert result.isValid(), "Raster workflow returned an invalid slope raster"
            print("STAGE: result validity passed", flush=True)
            target = QgsCoordinateReferenceSystem("EPSG:32618")
            assert result.crs() == target, f"Unexpected slope CRS: {result.crs().authid()}"
            print("STAGE: result CRS passed", flush=True)
            assert result.width() > 0 and result.height() > 0
            assert result.width() < 30 and result.height() < 30, (
                "Clipping did not reduce the synthetic raster to the boundary"
            )

            print("STAGE: opening slope output with GDAL", flush=True)
            output = gdal.Open(result.source(), gdal.GA_ReadOnly)
            print("STAGE: slope output opened with GDAL", flush=True)
            assert output is not None, f"Could not reopen slope output: {result.source()}"
            assert output.RasterXSize == result.width()
            assert output.RasterYSize == result.height()
            assert output.RasterCount >= 1
            projection = osr.SpatialReference()
            assert projection.ImportFromWkt(output.GetProjectionRef()) == 0
            assert projection.GetAuthorityCode(None) == "32618"
            print("STAGE: getting slope output band", flush=True)
            band = output.GetRasterBand(1)
            assert band is not None, "Slope output has no readable first band"
            nodata = band.GetNoDataValue()
            print("STAGE: reading slope output bytes", flush=True)
            # Avoid GDAL's ReadAsArray NumPy bridge in the runtime harness. Some
            # distro GDAL/NumPy combinations crash in that bridge even when the
            # raster itself is readable. ReadRaster returns a byte buffer, which
            # NumPy can interpret without invoking GDAL's array-conversion code.
            raw = band.ReadRaster(
                0, 0, output.RasterXSize, output.RasterYSize,
                buf_type=gdal.GDT_Float32,
            )
            assert raw is not None, "GDAL could not read slope output pixels"
            print(f"STAGE: slope output bytes read ({len(raw)} bytes)", flush=True)
            array = np.frombuffer(raw, dtype=np.float32).reshape(
                output.RasterYSize, output.RasterXSize
            )
            print("STAGE: slope bytes decoded", flush=True)
            # Convert to plain Python scalars before any QGIS/GDAL teardown.
            values = [
                float(value) for value in array.flat
                if math.isfinite(float(value)) and (nodata is None or float(value) != nodata)
            ]
            print(f"STAGE: collected {len(values)} finite slope cells", flush=True)
            assert values, "Slope output has no finite non-nodata cells"
            minimum, maximum = min(values), max(values)
            print(f"STAGE: slope range {minimum}..{maximum}", flush=True)
            assert minimum >= 0.0, f"Slope has negative values: {minimum}"
            assert maximum <= 90.0, f"Slope exceeds 90 degrees: {maximum}"
            assert maximum > 0.1, "Synthetic elevation gradient did not produce non-zero slope"
            print("STAGE: slope value assertions passed", flush=True)
            band = None
            output = None
            print("STAGE: GDAL slope dataset closed", flush=True)

            # Invalid physical parameters and angular horizontal units must fail early.
            print("STAGE: testing NaN z_factor rejection", flush=True)
            try:
                raster_module.raster_processing(
                    str(dem_path), str(boundary_path), "EPSG:32618", z_factor=float("nan")
                )
            except ValueError as exc:
                assert "finite, positive" in str(exc)
            else:
                raise AssertionError("NaN z_factor was accepted")

            print("STAGE: NaN z_factor rejected", flush=True)
            try:
                raster_module.raster_processing(
                    str(dem_path), str(boundary_path), "EPSG:32618", z_factor=True
                )
            except ValueError as exc:
                assert "finite, positive" in str(exc)
            else:
                raise AssertionError("Boolean z_factor was accepted as a numeric multiplier")

            print("STAGE: boolean z_factor rejected", flush=True)
            try:
                raster_module.raster_processing(
                    str(dem_path), str(empty_boundary_path), "EPSG:32618", z_factor=1.0
                )
            except ValueError as exc:
                assert "contains no features" in str(exc)
            else:
                raise AssertionError("Empty boundary layer was accepted")

            print("STAGE: empty boundary rejected", flush=True)
            try:
                raster_module.raster_processing(
                    str(dem_path), str(invalid_boundary_path), "EPSG:32618", z_factor=1.0
                )
            except ValueError as exc:
                assert "invalid geometry" in str(exc)
            else:
                raise AssertionError("Invalid polygon boundary was accepted")

            print("STAGE: invalid geometry rejected", flush=True)
            try:
                raster_module.raster_processing(
                    str(dem_path), str(boundary_path), "EPSG:4326", z_factor=1.0
                )
            except ValueError as exc:
                assert "projected target CRS" in str(exc)
            else:
                raise AssertionError("Geographic target CRS was accepted for slope analysis")

            print("STAGE: geographic target CRS rejected", flush=True)
            assert dem_path.read_bytes() == dem_before, "Raster workflow modified source DEM"
            assert boundary_path.read_bytes() == boundary_before, "Raster workflow modified source boundary"

        print("PASS: synthetic DEM reprojection, mask clipping, slope values, target CRS and dimensions")
        print("PASS: invalid z_factor, empty/invalid boundary, and geographic target CRS rejected")
        print("PASS: raster and boundary source files remain unchanged")
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
