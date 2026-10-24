"""Join synthetic polygon attributes to points; run inside QGIS with Processing."""
import processing
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer


def run_example():
    polygons = QgsVectorLayer("Polygon?crs=EPSG:3857", "zones", "memory")
    zone = QgsFeature(polygons.fields())
    zone.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,100 0,100 100,0 100,0 0))"))
    polygons.dataProvider().addFeatures([zone])
    polygons.updateExtents()
    points = QgsVectorLayer("Point?crs=EPSG:3857", "sites", "memory")
    inside = QgsFeature(points.fields())
    inside.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(25, 25)))
    outside = QgsFeature(points.fields())
    outside.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(150, 150)))
    points.dataProvider().addFeatures([inside, outside])
    points.updateExtents()
    joined = processing.run("native:joinattributesbylocation", {
        "INPUT": points, "JOIN": polygons, "PREDICATE": [0],
        "METHOD": 0, "DISCARD_NONMATCHING": False, "OUTPUT": "memory:",
    })["OUTPUT"]
    assert joined.isValid() and joined.featureCount() == 2
    print(f"Spatial join completed: {joined.featureCount()} points retained")
    return joined


if __name__ == "__main__":
    run_example()
