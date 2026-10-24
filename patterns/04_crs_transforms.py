"""Reproject a vector layer to an explicitly chosen coordinate reference system."""
import processing
from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer


def crs_transform(layer_path, target_crs="EPSG:4326"):
    layer = QgsVectorLayer(layer_path, "input", "ogr")
    if not layer.isValid():
        raise ValueError(f"Could not load input layer: {layer_path}")
    target = QgsCoordinateReferenceSystem(target_crs)
    if not target.isValid():
        raise ValueError(f"Invalid target CRS: {target_crs!r}")
    result = processing.run("native:reprojectlayer", {
        "INPUT": layer, "TARGET_CRS": target, "OUTPUT": "memory:",
    })["OUTPUT"]
    if not result.isValid() or result.crs() != target:
        raise RuntimeError("Reprojection did not produce a valid layer in the target CRS")
    return result


if __name__ == "__main__":
    print("Import crs_transform() in QGIS and choose a CRS appropriate for the intended analysis.")
