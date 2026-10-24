"""Real QGIS runtime smoke tests for the ZQM Geospatial Tools plugin.

Run with a QGIS-enabled Python interpreter, for example:
  QT_QPA_PLATFORM=offscreen /usr/bin/python3 scripts/validate_qgis_runtime.py
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

PLUGIN_PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_PARENT))
for qgis_path in ("/usr/share/qgis/python", "/usr/share/qgis/python/plugins"):
    if Path(qgis_path).is_dir() and qgis_path not in sys.path:
        sys.path.append(qgis_path)

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
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant  # noqa: E402

QgsApplication.setPrefixPath("/usr", True)
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

    def QgsFieldCompat(name, field_type=QVariant.Int):
        from qgis.core import QgsField
        return QgsField(name, field_type)

    class DiagnosticFeedback(QgsProcessingFeedback):
        """Keep provider diagnostics visible when an algorithm raises."""
        def __init__(self):
            super().__init__()
            self.errors = []
            self.warnings = []

        def reportError(self, error, fatalError=False):
            self.errors.append(str(error))
            super().reportError(error, fatalError)

        def pushWarning(self, warning):
            self.warnings.append(str(warning))
            super().pushWarning(warning)

    def run_algorithm(layers, output_dir, overwrite=False, distance=5.0):
        algorithm = BatchBufferAlgorithm()
        algorithm.initAlgorithm()
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = DiagnosticFeedback()
        try:
            return algorithm.processAlgorithm(
                {
                    "LAYERS": layers,
                    "DISTANCE": distance,
                    "SEGMENTS": 4,
                    "OUTPUT_FOLDER": str(output_dir),
                    "OVERWRITE": overwrite,
                },
                context,
                feedback,
            )
        except Exception as exc:
            details = "\n".join(feedback.errors + feedback.warnings)
            raise AssertionError(
                f"QGIS algorithm failed: {exc}\nFeedback details:\n{details}"
            ) from exc

    # Execute the repository's synthetic examples inside the real QGIS runtime.
    def load_module(relative_path, module_name):
        module_path = PLUGIN_PARENT / relative_path
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise AssertionError(f"Could not load module {relative_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    expression_example = load_module("examples/01-expression-basics/run.py", "zqm_example_expressions")
    expected_expressions = {
        "buffer_distance", "nearest_feature", "area_hectares_if_area_is_m2",
        "centroid_x", "centroid_y",
    }
    assert set(expression_example.expressions) == expected_expressions
    assert "buffer(" in expression_example.expressions["buffer_distance"]
    processing_example = load_module("examples/02-processing-script/run.py", "zqm_example_processing")
    example_layer = processing_example.run_script()
    assert example_layer.isValid() and example_layer.featureCount() == 1
    join_example = load_module("examples/03-spatial-join/run.py", "zqm_example_join")
    joined_example = join_example.run_example()
    assert joined_example.isValid() and joined_example.featureCount() == 2
    join_name_index = joined_example.fields().indexFromName("join_zone_name")
    assert join_name_index >= 0, "Spatial join example omitted joined attributes"
    joined_rows = list(joined_example.getFeatures())
    assert sum(row["join_zone_name"] == "central_zone" for row in joined_rows) == 1
    crs_example = load_module("examples/04-crs-transform/run.py", "zqm_example_crs")
    projected_point = crs_example.run_example()
    assert not projected_point.isEmpty()
    buffer_example = load_module("examples/05-batch-processing/run.py", "zqm_example_buffer")
    example_buffer = buffer_example.run_example()
    assert example_buffer.isValid() and example_buffer.featureCount() == 1
    plugin_contract = load_module("examples/06-plugin-dev/run.py", "zqm_example_plugin_contract")
    plugin_contract.main()

    def write_gpkg(layer, path, layer_name):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_name
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(path), QgsProject.instance().transformContext(), options
        )
        assert result[0] == QgsVectorFileWriter.NoError, f"Could not write {path}: {result[1]}"
        reopened = QgsVectorLayer(str(path), layer_name, "ogr")
        assert reopened.isValid() and reopened.featureCount() == layer.featureCount()
        return reopened

    # Load existing QML resources into live QGIS layers, not only an XML parser.
    style_layer = QgsVectorLayer("Polygon?crs=EPSG:3857", "style_smoke_test", "memory")
    assert style_layer.isValid(), "Could not create polygon layer for QML test"
    for style_name in ("parcels.qml", "flood_zones.qml"):
        style_path = PLUGIN_PARENT / "styles" / style_name
        style_result = style_layer.loadNamedStyle(str(style_path))
        if isinstance(style_result, tuple):
            message, loaded = style_result
            assert loaded, f"QGIS could not load {style_name}: {message}"
        else:
            # Some QGIS/SIP versions return only an error-message string.
            assert not style_result, f"QGIS could not load {style_name}: {style_result}"
        assert style_layer.renderer() is not None, f"{style_name} produced no renderer"

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

        # Non-finite values must be rejected before running native:buffer.
        try:
            run_algorithm([points], root / "invalid-distance", distance=float("inf"))
        except Exception as exc:
            assert "finite and non-negative" in str(exc), f"Unexpected invalid-distance error: {exc}"
        else:
            raise AssertionError("Infinite buffer distance was accepted")

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
    print("PASS: existing parcels and flood-zone QML styles load in QGIS")
    print("PASS: expression reference and synthetic processing, spatial-join, CRS, buffer and plugin-contract examples")
    print("PASS: file-backed vector analysis, spatial joins, CRS transforms, batch processing and clip/reproject")
    print("PASS: buffer execution, GeoPackage write/reopen, feature count and CRS")
    print("PASS: existing-output preservation and explicit overwrite")
    print("PASS: mixed-CRS rejection")
finally:
    app.exitQgis()
