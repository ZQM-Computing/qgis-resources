"""Transform a sample point from geographic to projected coordinates in QGIS."""
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry,
    QgsPointXY, QgsProject,
)


def run_example():
    source = QgsCoordinateReferenceSystem("EPSG:4326")
    target = QgsCoordinateReferenceSystem("EPSG:32617")
    if not source.isValid() or not target.isValid():
        raise RuntimeError("Required coordinate reference system is unavailable")
    # Example point near central Florida. Select an appropriate CRS for other areas.
    point = QgsGeometry.fromPointXY(QgsPointXY(-81.0, 28.5))
    transform = QgsCoordinateTransform(source, target, QgsProject.instance())
    point.transform(transform)
    x, y = point.asPoint().x(), point.asPoint().y()
    assert 0 < x < 1_000_000 and 0 < y < 10_000_000
    print(f"Projected sample point (metres): x={x:.2f}, y={y:.2f}")
    return point


if __name__ == "__main__":
    run_example()
