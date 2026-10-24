"""Join polygon attributes to points by spatial relationship."""
import processing
from qgis.core import QgsVectorLayer


def spatial_join(points_path, polygons_path, predicate="within"):
    points = QgsVectorLayer(points_path, "points", "ogr")
    polygons = QgsVectorLayer(polygons_path, "polygons", "ogr")
    if not points.isValid():
        raise ValueError(f"Could not load points: {points_path}")
    if not polygons.isValid():
        raise ValueError(f"Could not load polygons: {polygons_path}")
    predicates = {"intersects": 0, "within": 6}
    if predicate not in predicates:
        raise ValueError(f"Unsupported predicate {predicate!r}; choose {sorted(predicates)}")
    if not points.crs().isValid() or not polygons.crs().isValid():
        raise ValueError("Both input layers must have valid coordinate reference systems")
    if points.crs() != polygons.crs():
        raise ValueError("Input layers must share a CRS; reproject one before joining")
    result = processing.run("native:joinattributesbylocation", {
        "INPUT": points, "JOIN": polygons, "PREDICATE": [predicates[predicate]],
        "JOIN_FIELDS": [], "METHOD": 0, "DISCARD_NONMATCHING": False,
        "PREFIX": "join_", "OUTPUT": "memory:",
    })["OUTPUT"]
    if not result.isValid():
        raise RuntimeError("Spatial join returned an invalid layer")
    if result.fields().count() < points.fields().count():
        raise RuntimeError("Spatial join unexpectedly removed input fields")
    return result


if __name__ == "__main__":
    print("Import spatial_join() in QGIS; review predicate and boundary behavior for your data.")
