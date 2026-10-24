"""Reproject a DEM, clip it to a boundary, and derive slope.

Run in QGIS with GDAL and Processing providers. Choose a projected target CRS
appropriate for the study area; do not use one fixed UTM zone for global data.
"""
import processing
from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsRasterLayer, QgsVectorLayer,
)


def raster_processing(dem_path, boundary_path, target_crs):
    dem = QgsRasterLayer(dem_path, "dem")
    boundary = QgsVectorLayer(boundary_path, "boundary", "ogr")
    if not dem.isValid():
        raise ValueError(f"Could not load input raster: {dem_path}")
    if not boundary.isValid():
        raise ValueError(f"Could not load boundary layer: {boundary_path}")
    target = QgsCoordinateReferenceSystem(str(target_crs))
    if not target.isValid():
        raise ValueError(f"Invalid target CRS: {target_crs!r}")
    if target.isGeographic():
        raise ValueError(
            "Choose a projected target CRS for slope analysis so horizontal units "
            "are linear; also verify DEM vertical units and Z_FACTOR."
        )
    projected = processing.run("gdal:warpreproject", {
        "INPUT": dem, "TARGET_CRS": target, "RESAMPLING": 0,
        "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    projected_layer = QgsRasterLayer(projected, "projected_dem")
    if not projected_layer.isValid() or projected_layer.crs() != target:
        raise RuntimeError("DEM reprojection did not produce a valid raster in the target CRS")
    projected_boundary = processing.run("native:reprojectlayer", {
        "INPUT": boundary, "TARGET_CRS": target, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    if not projected_boundary.isValid():
        raise RuntimeError("Boundary reprojection returned an invalid layer")
    clipped = processing.run("gdal:cliprasterbymasklayer", {
        "INPUT": projected, "MASK": projected_boundary, "CROP_TO_CUTLINE": True,
        "KEEP_RESOLUTION": True, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    clipped_layer = QgsRasterLayer(clipped, "clipped_dem")
    if not clipped_layer.isValid():
        raise RuntimeError("Raster clip returned an invalid raster")
    registry = QgsApplication.processingRegistry()
    slope_algorithm = "native:slope"
    if registry.algorithmById(slope_algorithm) is None:
        slope_algorithm = "qgis:slope"
    if registry.algorithmById(slope_algorithm) is None:
        raise RuntimeError("No compatible QGIS slope algorithm is registered")
    slope = processing.run(slope_algorithm, {
        "INPUT": clipped_layer, "Z_FACTOR": 1, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    result = QgsRasterLayer(slope, "slope")
    if not result.isValid():
        raise RuntimeError("Slope algorithm returned an invalid raster")
    return result


if __name__ == "__main__":
    print("Import raster_processing() in QGIS and supply DEM, boundary, and an appropriate projected CRS.")
