"""Join synthetic polygon attributes to points; run inside QGIS with Processing."""
import processing
from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant


def run_example():
    polygons = QgsVectorLayer("Polygon?crs=EPSG:3857", "zones", "memory")
    provider = polygons.dataProvider()
    if not provider.addAttributes([QgsField("zone_name", QVariant.String)]):
        raise RuntimeError("Could not add zone_name field to polygon layer")
    polygons.updateFields()
    zone = QgsFeature(polygons.fields())
    zone.setAttribute("zone_name", "central_zone")
    zone.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,100 0,100 100,0 100,0 0))"))
    ok, _ = provider.addFeatures([zone])
    if not ok:
        raise RuntimeError("Could not insert synthetic polygon")
    polygons.updateExtents()
    points = QgsVectorLayer("Point?crs=EPSG:3857", "sites", "memory")
    inside = QgsFeature(points.fields())
    inside.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(25, 25)))
    outside = QgsFeature(points.fields())
    outside.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(150, 150)))
    ok, _ = points.dataProvider().addFeatures([inside, outside])
    if not ok:
        raise RuntimeError("Could not insert synthetic points")
    points.updateExtents()
    joined = processing.run("native:joinattributesbylocation", {
        "INPUT": points, "JOIN": polygons, "PREDICATE": [0],
        "METHOD": 0, "DISCARD_NONMATCHING": False, "OUTPUT": "memory:",
    })["OUTPUT"]
    if not joined.isValid() or joined.featureCount() != 2:
        raise RuntimeError("Spatial join did not retain both test points")
    zone_field = joined.fields().indexFromName("join_zone_name")
    if zone_field < 0:
        raise RuntimeError("Spatial join output is missing the expected zone attribute")
    rows = {feature["join_zone_name"] for feature in joined.getFeatures()}
    if rows != {"central_zone", None}:
        raise RuntimeError(f"Unexpected join results: {rows!r}")
    print(f"Spatial join completed: {joined.featureCount()} points retained")
    return joined


if __name__ == "__main__":
    run_example()
