"""Processing Toolbox algorithm: safely buffer several selected vector layers.

Install the complete zqm_geospatial_tools directory as a QGIS plugin and enable it.
Requires QGIS with the native Processing provider initialized.
"""
import math
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
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingOutputNumber,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsWkbTypes,
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
            "are skipped unless overwrite is explicitly enabled. Point and line "
            "inputs require a positive distance. Each layer "
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
            QgsProcessingParameterNumber(
                self.DISTANCE,
                self.tr("Buffer distance (input layer CRS units)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=100.0,
                minValue=0.0,
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
        stem = stem[:80].rstrip("._")
        return stem or "layer"

    def processAlgorithm(self, parameters, context, feedback):
        layers = self.parameterAsLayerList(parameters, self.LAYERS, context)
        if not layers:
            raise QgsProcessingException("Select at least one input vector layer.")

        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
        if not math.isfinite(distance) or distance < 0:
            raise QgsProcessingException("Buffer distance must be finite and non-negative.")

        segments = self.parameterAsInt(parameters, self.SEGMENTS, context)
        if segments < 1:
            raise QgsProcessingException("Segments per quarter circle must be at least 1.")

        output_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        if not output_folder:
            raise QgsProcessingException("Choose an output folder.")
        output_dir = Path(output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        overwrite = self.parameterAsBool(parameters, self.OVERWRITE, context)

        feedback.pushInfo(
            f"Inputs: {len(layers)} | distance: {distance:g} layer CRS units | "
            f"segments: {segments} | overwrite: {overwrite}"
        )
        successes = 0
        skipped = 0
        failures = 0
        failure_details = []
        used_names = set()
        reference_crs = None

        for index, layer in enumerate(layers):
            if feedback.isCanceled():
                break
            label = layer.name() if layer else f"input_{index + 1}"
            if layer is None or not layer.isValid():
                message = f"{label}: invalid input layer; skipped."
                feedback.reportError(message)
                failure_details.append(message)
                failures += 1
                continue
            if QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.NullGeometry:
                message = f"{label}: non-spatial layer; skipped."
                feedback.reportError(message)
                failure_details.append(message)
                failures += 1
                continue
            if not layer.crs().isValid():
                message = f"{label}: missing or invalid CRS; skipped."
                feedback.reportError(message)
                failure_details.append(message)
                failures += 1
                continue
            if reference_crs is None:
                reference_crs = layer.crs()
            elif layer.crs() != reference_crs:
                message = (
                    f"{label}: CRS {layer.crs().authid()} differs from "
                    f"{reference_crs.authid()}; batch inputs must share one CRS."
                )
                feedback.reportError(message)
                failure_details.append(message)
                failures += 1
                continue
            if distance == 0 and QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
                message = f"{label}: zero-distance buffers are not meaningful for point/line inputs; use a positive distance."
                feedback.reportError(message)
                failure_details.append(message)
                failures += 1
                continue
            if layer.crs().isGeographic() and distance > 0:
                feedback.pushWarning(
                    f"{label}: distance is in angular CRS units, not metres. "
                    "Use a suitable projected CRS for metric buffers."
                )

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

                for feature in buffered.getFeatures():
                    geometry = feature.geometry()
                    if geometry is None or geometry.isNull() or geometry.isEmpty():
                        raise RuntimeError(f"buffer produced an empty geometry for feature {feature.id()}")
                    if not geometry.isGeosValid():
                        raise RuntimeError(f"buffer produced invalid geometry for feature {feature.id()}")

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
                if check.crs() != layer.crs():
                    raise RuntimeError(
                        f"written CRS mismatch: expected={layer.crs().authid()}, "
                        f"actual={check.crs().authid()}"
                    )
                if QgsWkbTypes.geometryType(check.wkbType()) != QgsWkbTypes.PolygonGeometry:
                    raise RuntimeError("written output geometry type is not polygonal")
                if check.featureCount() != layer.featureCount():
                    raise RuntimeError(
                        f"written feature-count mismatch: expected={layer.featureCount()}, "
                        f"actual={check.featureCount()}"
                    )
                del check

                # Recheck immediately before publication to avoid a concurrent
                # run silently replacing a destination when overwrite is disabled.
                if output_path.exists() and not overwrite:
                    raise FileExistsError(f"output appeared during processing: {output_path}")
                # Replace only after the temporary output has passed validation.
                os.replace(temporary_path, output_path)
                successes += 1
                feedback.pushInfo(
                    f"{label}: wrote {buffered.featureCount()} feature(s) to {output_path}"
                )
            except Exception as exc:
                failures += 1
                message = f"{label}: {exc}"
                feedback.reportError(message)
                failure_details.append(message)
            finally:
                try:
                    if temporary_path.exists():
                        temporary_path.unlink()
                except OSError as exc:
                    feedback.reportError(
                        f"Could not remove temporary file {temporary_path}: {exc}"
                    )

        if feedback.isCanceled():
            raise QgsProcessingException(
                "Canceled by user. Completed per-layer outputs remain on disk; "
                "review the log before rerunning."
            )

        feedback.pushInfo(
            f"Batch buffer summary — succeeded: {successes}; skipped: {skipped}; "
            f"failed: {failures}; total: {len(layers)}."
        )
        if failures and successes == 0 and skipped == 0:
            details = " | ".join(failure_details)
            raise QgsProcessingException(
                f"All batch buffer operations failed; see the log. Details: {details}"
            )
        return {
            self.OUTPUT_FOLDER: str(output_dir),
            "SUCCEEDED": successes,
            "SKIPPED": skipped,
            "FAILED": failures,
        }
