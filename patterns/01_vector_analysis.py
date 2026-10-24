"""Buffer and dissolve a vector layer, then calculate planar geometry area.

Run in QGIS with Processing initialized. Buffer distance uses the layer CRS
units; reproject to an appropriate projected CRS before using metres. The area
field is expressed in squared CRS units, which are not always square metres.
"""
import math
import processing
from qgis.core import QgsField, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant


def vector_analysis(input_path, buffer_distance=500.0, area_field="area_crs_units2"):
    layer = QgsVectorLayer(input_path, "input", "ogr")
    if not layer.isValid():
        raise ValueError(f"Could not load input vector layer: {input_path}")
    if not isinstance(buffer_distance, (int, float)) or not math.isfinite(buffer_distance) or buffer_distance < 0:
        raise ValueError("buffer_distance must be a finite, non-negative number")
    buffered = processing.run("native:buffer", {
        "INPUT": layer, "DISTANCE": buffer_distance, "SEGMENTS": 8,
        "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
        "DISSOLVE": False, "OUTPUT": "memory:",
    })["OUTPUT"]
    if not buffered.isValid():
        raise RuntimeError("Buffer algorithm returned an invalid layer")
    dissolved = processing.run("native:dissolve", {
        "INPUT": buffered, "FIELD": [], "SEPARATE_DISJOINT": False,
        "OUTPUT": "memory:",
    })["OUTPUT"]
    if not dissolved.isValid():
        raise RuntimeError("Dissolve algorithm returned an invalid layer")
    provider = dissolved.dataProvider()
    if dissolved.fields().indexFromName(area_field) < 0:
        if not provider.addAttributes([QgsField(area_field, QVariant.Double)]):
            raise RuntimeError(f"Could not add area field {area_field!r}")
        dissolved.updateFields()
    area_index = dissolved.fields().indexFromName(area_field)
    if area_index < 0:
        raise RuntimeError(f"Could not create area field {area_field!r}")
    areas = []
    for feature in dissolved.getFeatures():
        geometry = feature.geometry()
        if geometry is None or geometry.isNull() or geometry.isEmpty():
            raise ValueError(f"Feature {feature.id()} has no usable geometry")
        area = geometry.area()
        areas.append(area)
        if not provider.changeAttributeValues({feature.id(): {area_index: area}}):
            raise RuntimeError(f"Could not write area for feature {feature.id()}")
    dissolved.updateFields()
    stats = {
        "count": len(areas),
        "sum": sum(areas),
        "minimum": min(areas) if areas else None,
        "maximum": max(areas) if areas else None,
        "mean": sum(areas) / len(areas) if areas else None,
        "units": "squared layer CRS units; not necessarily m²",
    }
    return dissolved, stats


if __name__ == "__main__":
    print("Import vector_analysis() from the QGIS Python Console and provide a vector path.")
