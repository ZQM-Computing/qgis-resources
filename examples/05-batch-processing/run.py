"""Buffer a synthetic point layer; run inside QGIS with Processing initialized."""
import processing
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer


def run_example():
    points = QgsVectorLayer("Point?crs=EPSG:3857", "sample_points", "memory")
    feature = QgsFeature(points.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
    ok, _ = points.dataProvider().addFeatures([feature])
    if not ok or not points.isValid():
        raise RuntimeError("Could not create synthetic point input")
    points.updateExtents()
    result = processing.run("native:buffer", {
        "INPUT": points, "DISTANCE": 25, "SEGMENTS": 8,
        "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
        "DISSOLVE": False, "OUTPUT": "memory:",
    })["OUTPUT"]
    if not result.isValid() or result.featureCount() != 1:
        raise RuntimeError("Buffer algorithm returned an invalid or incomplete layer")
    buffered = next(result.getFeatures())
    if buffered.geometry().isNull() or buffered.geometry().isEmpty():
        raise RuntimeError("Buffer output geometry is empty")
    print("Synthetic buffer passed feature-count and geometry checks")
    return result


if __name__ == "__main__":
    run_example()
