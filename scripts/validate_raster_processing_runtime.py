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

for qgis_path in ("/usr/share/qgis/python", "/usr/share/qgis/python/plugins"):
    if Path(qgis_path).is_dir() and qgis_path not in sys.path:
        sys.path.append(qgis_path)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from osgeo import gdal, ogr, osr  # noqa: E402
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
    assert band.WriteArray(values) == 0
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


def main() -> None:
    QgsApplication.setPrefixPath("/usr", True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        from processing.core.Processing import Processing
        Processing.initialize()
        with tempfile.TemporaryDirectory(prefix="zqm-raster-runtime-") as temporary:
            root = Path(temporary)
            dem_path = root / "synthetic_dem.tif"
            boundary_path = root / "study_boundary.gpkg"
            create_dem(dem_path)
            create_boundary(boundary_path)
            dem_before = dem_path.read_bytes()
            boundary_before = boundary_path.read_bytes()

            result = raster_module.raster_processing(
                str(dem_path), str(boundary_path), "EPSG:32618", z_factor=1.0
            )
            assert result.isValid(), "Raster workflow returned an invalid slope raster"
            target = QgsCoordinateReferenceSystem("EPSG:32618")
            assert result.crs() == target, f"Unexpected slope CRS: {result.crs().authid()}"
            assert result.width() > 0 and result.height() > 0
            assert result.width() < 30 and result.height() < 30, (
                "Clipping did not reduce the synthetic raster to the boundary"
            )

            output = gdal.Open(result.source(), gdal.GA_ReadOnly)
            assert output is not None, f"Could not reopen slope output: {result.source()}"
            assert output.RasterXSize == result.width()
            assert output.RasterYSize == result.height()
            assert output.RasterCount >= 1
            projection = osr.SpatialReference()
            assert projection.ImportFromWkt(output.GetProjectionRef()) == 0
            assert projection.GetAuthorityCode(None) == "32618"
            band = output.GetRasterBand(1)
            array = band.ReadAsArray()
            nodata = band.GetNoDataValue()
            values = [
                float(value) for row in array for value in row
                if math.isfinite(float(value)) and (nodata is None or float(value) != nodata)
            ]
            assert values, "Slope output has no finite non-nodata cells"
            assert min(values) >= 0.0, f"Slope has negative values: {min(values)}"
            assert max(values) <= 90.0, f"Slope exceeds 90 degrees: {max(values)}"
            assert max(values) > 0.1, "Synthetic elevation gradient did not produce non-zero slope"
            output = None

            # Invalid physical parameters and angular horizontal units must fail early.
            try:
                raster_module.raster_processing(
                    str(dem_path), str(boundary_path), "EPSG:32618", z_factor=float("nan")
                )
            except ValueError as exc:
                assert "finite, positive" in str(exc)
            else:
                raise AssertionError("NaN z_factor was accepted")

            try:
                raster_module.raster_processing(
                    str(dem_path), str(boundary_path), "EPSG:4326", z_factor=1.0
                )
            except ValueError as exc:
                assert "projected target CRS" in str(exc)
            else:
                raise AssertionError("Geographic target CRS was accepted for slope analysis")

            assert dem_path.read_bytes() == dem_before, "Raster workflow modified source DEM"
            assert boundary_path.read_bytes() == boundary_before, "Raster workflow modified source boundary"

        print("PASS: synthetic DEM reprojection, mask clipping, slope values, target CRS and dimensions")
        print("PASS: invalid z_factor and geographic target CRS rejected")
        print("PASS: raster and boundary source files remain unchanged")
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
