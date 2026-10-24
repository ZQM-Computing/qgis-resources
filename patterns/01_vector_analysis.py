"""Buffer and dissolve a vector layer, then calculate planar geometry area.

Run in QGIS with Processing initialized. Buffer distance uses the layer CRS
units; reproject to an appropriate projected CRS before using metres.
"""
import processing
from qgis.core import QgsField, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant


def vector_analysis(input_path, buffer_distance=500.0, area_field="area_crs_units2"):
    layer = QgsVectorLayer(input_path, "input", "ogr")
    if not layer.isValid():
        raise ValueError(f"Could not load input vector layer: {input_path}")
    if buffer_distance < 0:
        raise ValueError("buffer_distance must be non-negative")
    buffered = processing.run("native:buffer", {
        "INPUT": layer, "DISTANCE": buffer_distance, "SEGMENTS": 8,
        "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
        "DISSOLVE": False, "OUTPUT": "memory:",
    })["OUTPUT"]
    dissolved = processing.run("native:dissolve", {
        "INPUT": buffered, "FIELD": [], "SEPARATE_DISJOINT": False,
        "OUTPUT": "memory:",
    })["OUTPUT"]
    provider = dissolved.dataProvider()
    if dissolved.fields().indexFromName(area_field) < 0:
        provider.addAttributes([QgsField(area_field, QVariant.Double)])
        dissolved.updateFields()
    area_index = dissolved.fields().indexFromName(area_field)
    if area_index < 0:
        raise RuntimeError(f"Could not create area field {area_field!r}")
    for feature in dissolved.getFeatures():
        geometry = feature.geometry()
        if geometry is None or geometry.isNull() or geometry.isEmpty():
            raise ValueError(f"Feature {feature.id()} has no usable geometry")
        provider.changeAttributeValues({feature.id(): {area_index: geometry.area()}})
    dissolved.updateFields()
    stats = processing.run("qgis:basicstatisticsforfields", {
        "INPUT": dissolved, "FIELD_NAME": area_field, "OUTPUT": "memory:",
    })
    return dissolved, stats


if __name__ == "__main__":
    print("Import vector_analysis() from the QGIS Python Console and provide a vector path.")
