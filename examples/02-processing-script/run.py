"""Example 02: QGIS Processing script template."""

from qgis.core import QgsField, QgsVectorLayer


def run_script():
    """Example processing script for QGIS."""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "points", "memory")

    # Add fields
    from qgis.PyQt.QtCore import QVariant

    layer.dataProvider().addAttributes(
        [
            QgsField("name", QVariant.String),
            QgsField("value", QVariant.Double),
        ]
    )
    layer.updateFields()

    print(f"Layer: {layer.name()}")
    print(f"Feature count: {layer.featureCount()}")
    print(f"CRS: {layer.crs().authid()}")
    print("Script executed successfully.")


if __name__ == "__main__":
    run_script()
