"""Create and validate a small synthetic vector layer inside QGIS."""
from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant


def run_script():
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "points", "memory")
    provider = layer.dataProvider()
    if not layer.isValid():
        raise RuntimeError("Could not create in-memory point layer")
    if not provider.addAttributes([
        QgsField("name", QVariant.String),
        QgsField("value", QVariant.Double),
    ]):
        raise RuntimeError("Could not add expected point attributes")
    layer.updateFields()

    feature = QgsFeature(layer.fields())
    feature.setAttributes(["sample_site", 12.5])
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-81.0, 28.5)))
    if feature.geometry().isEmpty():
        raise RuntimeError("Synthetic point geometry is empty")
    ok, _ = provider.addFeatures([feature])
    layer.updateExtents()
    if not ok or not layer.isValid() or layer.featureCount() != 1:
        raise RuntimeError("Failed to create the expected synthetic point feature")
    stored = next(layer.getFeatures())
    if stored["name"] != "sample_site" or stored["value"] != 12.5:
        raise RuntimeError("Stored attributes do not match the input feature")
    print(f"Layer: {layer.name()} | features: {layer.featureCount()} | CRS: {layer.crs().authid()}")
    return layer


if __name__ == "__main__":
    run_script()
