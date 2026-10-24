"""Real QGIS runtime smoke tests for the ZQM Geospatial Tools plugin.

Run with a QGIS-enabled Python interpreter, for example:
  QT_QPA_PLATFORM=offscreen /usr/bin/python3 scripts/validate_qgis_runtime.py
"""
import os
import sys
import tempfile
from pathlib import Path

PLUGIN_PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_PARENT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant  # noqa: E402

app = QgsApplication([], False)
app.initQgis()

try:
    from processing.core.Processing import Processing
    from zqm_geospatial_tools.batch_buffer_algorithm import BatchBufferAlgorithm
    from zqm_geospatial_tools.provider import ZqmProcessingProvider

    Processing.initialize()
    registry = QgsApplication.processingRegistry()
    provider = ZqmProcessingProvider()
    assert registry.addProvider(provider), "QGIS could not register the ZQM provider"
    assert registry.providerById("zqm_geospatial_tools") is not None
    assert any(a.name() == "zqm_batch_buffer" for a in provider.algorithms()), (
        "ZQM provider did not expose the batch buffer algorithm"
    )

    def make_points(name, crs_id="EPSG:3857", count=2):
        layer = QgsVectorLayer(f"Point?crs={crs_id}", name, "memory")
        assert layer.isValid(), f"Could not create memory layer {name}"
        layer.dataProvider().addAttributes([QgsFieldCompat("id")])
        layer.updateFields()
        features = []
        for index in range(count):
            feature = QgsFeature(layer.fields())
            feature.setAttribute("id", index + 1)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(index * 10, index * 5)))
            features.append(feature)
        result = layer.dataProvider().addFeatures(features)
        assert result[0], f"Could not add features to {name}"
        layer.updateExtents()
        return layer

    def QgsFieldCompat(name):
        from qgis.core import QgsField
        return QgsField(name, QVariant.Int)

    def run_algorithm(layers, output_dir, overwrite=False):
        algorithm = BatchBufferAlgorithm()
        algorithm.initAlgorithm()
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = QgsProcessingFeedback()
        return algorithm.processAlgorithm(
            {
                "LAYERS": layers,
                "DISTANCE": 5.0,
                "SEGMENTS": 4,
                "OUTPUT_FOLDER": str(output_dir),
                "OVERWRITE": overwrite,
            },
            context,
            feedback,
        )

    with tempfile.TemporaryDirectory(prefix="zqm-qgis-runtime-") as temp:
        root = Path(temp)
        output_dir = root / "outputs"
        points = make_points("runtime_points")
        result = run_algorithm([points], output_dir)
        output = output_dir / "runtime_points_buffer.gpkg"
        assert result["SUCCEEDED"] == 1 and result["SKIPPED"] == 0
        assert result["FAILED"] == 0
        assert output.is_file() and output.stat().st_size > 0
        reopened = QgsVectorLayer(str(output), "runtime_check", "ogr")
        assert reopened.isValid(), "Output GeoPackage failed to reopen"
        assert reopened.featureCount() == points.featureCount(), "Output feature count differs"
        assert reopened.crs() == points.crs(), "Output CRS differs from input"
        assert QgsWkbTypes.geometryType(reopened.wkbType()) == QgsWkbTypes.PolygonGeometry
        extent = reopened.extent()
        assert extent.xMinimum() <= -4.9 and extent.xMaximum() >= 14.9, (
            f"Buffer extent does not reflect the requested distance: {extent.toString()}"
        )

        # Default behavior must preserve existing output and report a skip.
        original_bytes = output.read_bytes()
        result = run_algorithm([points], output_dir, overwrite=False)
        assert result["SKIPPED"] == 1 and result["SUCCEEDED"] == 0
        assert output.read_bytes() == original_bytes, "Existing output changed without overwrite"

        # Close the reader before replacing the GeoPackage.
        del reopened

        # Explicit overwrite must successfully replace with a validated GeoPackage.
        result = run_algorithm([points], output_dir, overwrite=True)
        assert result["SUCCEEDED"] == 1
        reopened = QgsVectorLayer(str(output), "runtime_overwrite_check", "ogr")
        assert reopened.isValid() and reopened.featureCount() == 2

        # Mixed CRS must be rejected per layer, without creating that layer's output.
        mixed_dir = root / "mixed"
        geographic = make_points("different_crs", "EPSG:4326", count=1)
        result = run_algorithm([points, geographic], mixed_dir)
        assert result["SUCCEEDED"] == 1 and result["FAILED"] == 1
        assert (mixed_dir / "runtime_points_buffer.gpkg").is_file()
        assert not (mixed_dir / "different_crs_buffer.gpkg").exists()

    print("PASS: provider registration and algorithm discovery")
    print("PASS: buffer execution, GeoPackage write/reopen, feature count and CRS")
    print("PASS: existing-output preservation and explicit overwrite")
    print("PASS: mixed-CRS rejection")
finally:
    app.exitQgis()
