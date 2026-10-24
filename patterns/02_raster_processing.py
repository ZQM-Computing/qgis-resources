"""Reproject a DEM, clip it to a boundary, and derive slope.

Run in QGIS with GDAL and Processing providers. Choose a projected target CRS
appropriate for the study area; do not use one fixed UTM zone for global data.
"""
import math
import processing
from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsRasterLayer, QgsVectorLayer,
    QgsWkbTypes,
)


def raster_processing(dem_path, boundary_path, target_crs, z_factor=1.0):
    dem = QgsRasterLayer(dem_path, "dem")
    boundary = QgsVectorLayer(boundary_path, "boundary", "ogr")
    if not dem.isValid():
        raise ValueError(f"Could not load input raster: {dem_path}")
    if not boundary.isValid():
        raise ValueError(f"Could not load boundary layer: {boundary_path}")
    if not dem.crs().isValid():
        raise ValueError("Input DEM has no valid CRS; assign its true source CRS before warping")
    if not boundary.crs().isValid():
        raise ValueError("Boundary layer has no valid CRS; assign its true source CRS before reprojection")
    if QgsWkbTypes.geometryType(boundary.wkbType()) != QgsWkbTypes.PolygonGeometry:
        raise ValueError("Boundary layer must contain polygon or multipolygon geometry")
    if boundary.featureCount() <= 0:
        raise ValueError("Boundary layer contains no features; clipping would not produce a meaningful raster")
    target = (
        target_crs if isinstance(target_crs, QgsCoordinateReferenceSystem)
        else QgsCoordinateReferenceSystem(str(target_crs))
    )
    if not target.isValid():
        raise ValueError(f"Invalid target CRS: {target_crs!r}")
    if isinstance(z_factor, bool) or not isinstance(z_factor, (int, float)) or not math.isfinite(z_factor) or z_factor <= 0:
        raise ValueError("z_factor must be a finite, positive number matching the DEM vertical/horizontal unit ratio")
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
    if projected_layer.bandCount() < 1:
        raise RuntimeError("DEM reprojection returned a raster with no bands")
    projected_boundary = processing.run("native:reprojectlayer", {
        "INPUT": boundary, "TARGET_CRS": target, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    projected_boundary_layer = (
        projected_boundary if isinstance(projected_boundary, QgsVectorLayer)
        else QgsVectorLayer(str(projected_boundary), "projected_boundary", "ogr")
    )
    if not projected_boundary_layer.isValid():
        raise RuntimeError("Boundary reprojection returned an invalid layer")
    if projected_boundary_layer.crs() != target:
        raise RuntimeError("Boundary reprojection did not produce the target CRS")
    clipped = processing.run("gdal:cliprasterbymasklayer", {
        "INPUT": projected, "MASK": projected_boundary_layer, "CROP_TO_CUTLINE": True,
        "KEEP_RESOLUTION": True, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    clipped_layer = QgsRasterLayer(clipped, "clipped_dem")
    if not clipped_layer.isValid():
        raise RuntimeError("Raster clip returned an invalid raster")
    if clipped_layer.crs() != target:
        raise RuntimeError("Raster clip changed the target CRS unexpectedly")
    if clipped_layer.width() <= 0 or clipped_layer.height() <= 0 or clipped_layer.bandCount() < 1:
        raise RuntimeError("Raster clip returned an empty raster extent or no data bands")
    registry = QgsApplication.processingRegistry()
    slope_algorithm = "native:slope"
    if registry.algorithmById(slope_algorithm) is None:
        slope_algorithm = "qgis:slope"
    if registry.algorithmById(slope_algorithm) is None:
        raise RuntimeError("No compatible QGIS slope algorithm is registered")
    slope = processing.run(slope_algorithm, {
        "INPUT": clipped_layer, "Z_FACTOR": z_factor, "OUTPUT": "TEMPORARY_OUTPUT",
    })["OUTPUT"]
    result = QgsRasterLayer(slope, "slope")
    if not result.isValid():
        raise RuntimeError("Slope algorithm returned an invalid raster")
    if result.crs() != target:
        raise RuntimeError("Slope output CRS differs from the requested target CRS")
    if result.width() <= 0 or result.height() <= 0 or result.bandCount() < 1:
        raise RuntimeError("Slope algorithm returned an empty raster or no data bands")
    return result


if __name__ == "__main__":
    print("Import raster_processing() in QGIS and supply DEM, boundary, and an appropriate projected CRS.")
