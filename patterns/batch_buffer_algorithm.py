"""Processing Toolbox algorithm: safely buffer several selected vector layers.

Install this file through Processing Toolbox -> Scripts -> Add Script from File.
Requires QGIS with the native Processing provider initialized.
"""
import os
import re
import uuid
from pathlib import Path

import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingOutputNumber,
    QgsVectorLayer,
    QgsVectorFileWriter,
)


class BatchBufferAlgorithm(QgsProcessingAlgorithm):
    LAYERS = "LAYERS"
    DISTANCE = "DISTANCE"
    SEGMENTS = "SEGMENTS"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    OVERWRITE = "OVERWRITE"

    def tr(self, text):
        return QCoreApplication.translate("BatchBufferAlgorithm", text)

    def createInstance(self):
        return BatchBufferAlgorithm()

    def name(self):
        return "zqm_batch_buffer"

    def displayName(self):
        return self.tr("ZQM — Batch buffer selected layers")

    def group(self):
        return self.tr("ZQM Geospatial Tools")

    def groupId(self):
        return "zqm_geospatial_tools"

    def shortHelpString(self):
        return self.tr(
            "Buffers each selected vector layer into its own GeoPackage. "
            "Distance uses the layer's CRS units; choose a suitable projected "
            "CRS when the intended distance is in metres. Existing outputs "
            "are skipped unless overwrite is explicitly enabled. Each layer "
            "is processed independently and the log reports successes/failures."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.LAYERS,
                self.tr("Input vector layers"),
                layerType=QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                self.DISTANCE,
                self.tr("Buffer distance (layer CRS units)"),
                defaultValue=100.0,
                minValue=0.0,
                parentParameterName=self.LAYERS,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SEGMENTS,
                self.tr("Segments per quarter circle"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=8,
                minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER, self.tr("Output folder")
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.OVERWRITE,
                self.tr("Replace existing output GeoPackages"),
                defaultValue=False,
            )
        )
        self.addOutput(QgsProcessingOutputNumber("SUCCEEDED", self.tr("Successful layers")))
        self.addOutput(QgsProcessingOutputNumber("SKIPPED", self.tr("Skipped layers")))
        self.addOutput(QgsProcessingOutputNumber("FAILED", self.tr("Failed layers")))

    @staticmethod
    def _safe_stem(name):
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
        return stem or "layer"

    def processAlgorithm(self, parameters, context, feedback):
        layers = self.parameterAsLayerList(parameters, self.LAYERS, context)
        if not layers:
            raise QgsProcessingException("Select at least one input vector layer.")

        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
        if distance < 0:
            raise QgsProcessingException("Buffer distance must be non-negative.")

        segments = self.parameterAsInt(parameters, self.SEGMENTS, context)
        if segments < 1:
            raise QgsProcessingException("Segments per quarter circle must be at least 1.")

        output_dir = Path(self.parameterAsString(parameters, self.OUTPUT_FOLDER, context))
        if not str(output_dir):
            raise QgsProcessingException("Choose an output folder.")
        output_dir.mkdir(parents=True, exist_ok=True)
        overwrite = self.parameterAsBool(parameters, self.OVERWRITE, context)

        feedback.pushInfo(
            f"Inputs: {len(layers)} | distance: {distance:g} layer CRS units | "
            f"segments: {segments} | overwrite: {overwrite}"
        )
        successes = 0
        skipped = 0
        failures = 0
        used_names = set()

        for index, layer in enumerate(layers):
            if feedback.isCanceled():
                break
            label = layer.name() if layer else f"input_{index + 1}"
            if layer is None or not layer.isValid():
                feedback.reportError(f"{label}: invalid input layer; skipped.")
                failures += 1
                continue
            if not layer.isSpatial():
                feedback.reportError(f"{label}: non-spatial layer; skipped.")
                failures += 1
                continue

            stem = self._safe_stem(layer.name())
            # Avoid collisions where different layer names sanitize to the same stem.
            candidate = stem
            suffix = 2
            while candidate.casefold() in used_names:
                candidate = f"{stem}_{suffix}"
                suffix += 1
            used_names.add(candidate.casefold())

            output_path = output_dir / f"{candidate}_buffer.gpkg"
            if output_path.exists() and not overwrite:
                feedback.pushWarning(f"{label}: output exists, preserving it: {output_path}")
                skipped += 1
                continue

            temporary_path = output_dir / f".{candidate}_{uuid.uuid4().hex}.tmp.gpkg"
            try:
                feedback.pushInfo(f"Buffering {label} ({index + 1}/{len(layers)})...")
                buffered = processing.run(
                    "native:buffer",
                    {
                        "INPUT": layer,
                        "DISTANCE": distance,
                        "SEGMENTS": segments,
                        "END_CAP_STYLE": 0,
                        "JOIN_STYLE": 0,
                        "MITER_LIMIT": 2.0,
                        "DISSOLVE": False,
                        "OUTPUT": "memory:",
                    },
                    context=context,
                    feedback=feedback,
                    is_child_algorithm=True,
                )["OUTPUT"]

                if not isinstance(buffered, QgsVectorLayer):
                    buffered = QgsVectorLayer(str(buffered), f"{label}_buffer", "ogr")
                if not buffered.isValid():
                    raise RuntimeError("buffer algorithm returned an invalid layer")
                if buffered.featureCount() != layer.featureCount():
                    raise RuntimeError(
                        f"feature-count mismatch: input={layer.featureCount()}, "
                        f"buffer={buffered.featureCount()}"
                    )

                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = "GPKG"
                options.fileEncoding = "UTF-8"
                options.layerName = f"{candidate}_buffer"
                result = QgsVectorFileWriter.writeAsVectorFormatV3(
                    buffered, str(temporary_path), context.transformContext(), options
                )
                error_code, error_message = result[0], result[1]
                if error_code != QgsVectorFileWriter.NoError:
                    raise RuntimeError(f"GeoPackage write failed: {error_message}")

                check = QgsVectorLayer(str(temporary_path), options.layerName, "ogr")
                if not check.isValid():
                    raise RuntimeError("written GeoPackage cannot be reopened")
                if check.featureCount() != layer.featureCount():
                    raise RuntimeError(
                        f"written feature-count mismatch: expected={layer.featureCount()}, "
                        f"actual={check.featureCount()}"
                    )
                del check

                # Replace only after the temporary output has passed validation.
                os.replace(temporary_path, output_path)
                successes += 1
                feedback.pushInfo(
                    f"{label}: wrote {buffered.featureCount()} feature(s) to {output_path}"
                )
            except Exception as exc:
                failures += 1
                feedback.reportError(f"{label}: {exc}")
            finally:
                try:
                    if temporary_path.exists():
                        temporary_path.unlink()
                except OSError as exc:
                    feedback.reportError(
                        f"Could not remove temporary file {temporary_path}: {exc}"
                    )

        feedback.pushInfo(
            f"Batch buffer summary — succeeded: {successes}; skipped: {skipped}; "
            f"failed: {failures}; total: {len(layers)}."
        )
        if failures and successes == 0 and skipped == 0:
            raise QgsProcessingException("All batch buffer operations failed; see the log.")
        return {
            self.OUTPUT_FOLDER: str(output_dir),
            "SUCCEEDED": successes,
            "SKIPPED": skipped,
            "FAILED": failures,
        }
