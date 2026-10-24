"""Reproject a DEM, clip it to a boundary, and derive slope.

Run in QGIS with GDAL and Processing providers. Choose a projected target CRS
appropriate for the study area; do not use one fixed UTM zone for global data.
"""
import processing
from qgis.core import QgsRasterLayer, QgsVectorLayer


def raster_processing(dem_path, boundary_path, target_crs):
    dem = QgsRasterLayer(dem_path, "dem")
    boundary = QgsVectorLayer(boundary_path, "boundary", "ogr")
    if not dem.isValid():
        raise ValueError(f"Could not load input raster: {dem_path}")
    if not boundary.isValid():
        raise ValueError(f"Could not load boundary layer: {boundary_path}")
    if not target_crs or not str(target_crs).strip():
        raise ValueError("target_crs must be specified explicitly")
    projected = processing.run("gdal:warpreproject", {
        "INPUT": dem, "TARGET_CRS": target_crs, "RESAMPLING": 0,
        "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    clipped = processing.run("gdal:cliprasterbymasklayer", {
        "INPUT": projected, "MASK": boundary, "CROP_TO_CUTLINE": True,
        "KEEP_RESOLUTION": True, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    slope = processing.run("qgis:slope", {
        "INPUT": clipped, "Z_FACTOR": 1, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    result = QgsRasterLayer(slope, "slope")
    if not result.isValid():
        raise RuntimeError("Slope algorithm returned an invalid raster")
    return result


if __name__ == "__main__":
    print("Import raster_processing() in QGIS and supply DEM, boundary, and an appropriate projected CRS.")
