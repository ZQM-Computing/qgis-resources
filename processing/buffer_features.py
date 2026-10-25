"""
Buffer every feature in a vector layer by one fixed distance.

Install: Processing Toolbox -> Scripts -> Add Script from File, then run
"Buffer features (fixed distance)" from the ZQM Examples group.

Inputs: any vector layer, a buffer distance, and a segment count.
Output: a new layer with one buffered feature per input feature that had a
non-empty geometry. Features with no geometry, or whose buffer comes back
empty, are skipped and counted in the run log instead of failing the run.

Distance units are the layer's CRS units. Use a projected CRS (for example
a local UTM zone or a state-plane CRS) when the distance is meant to be in
metres. Do not run this on a layer in EPSG:4326 and read the distance as
metres: in geographic coordinates the distance is in degrees.

Tested against the QGIS 3.28+ Processing framework. A quick synthetic test
inside QGIS: create a memory point layer, add one point, run this algorithm
on it, and confirm the output has one polygon feature.

This script is intentionally self-contained: it buffers with QgsGeometry
directly rather than chaining another Processing algorithm, so the whole
behaviour is visible in this one file.
"""

from qgis.core import (
    QgsFeature,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
)
from qgis.PyQt.QtCore import QCoreApplication


class BufferFeaturesAlgorithm(QgsProcessingAlgorithm):
    """Buffer input features by a fixed distance."""

    INPUT = "INPUT"
    DISTANCE = "DISTANCE"
    SEGMENTS = "SEGMENTS"
    OUTPUT = "OUTPUT"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return BufferFeaturesAlgorithm()

    def name(self):
        return "bufferfeatures"

    def displayName(self):
        return self.tr("Buffer features (fixed distance)")

    def group(self):
        return self.tr("ZQM Examples")

    def groupId(self):
        return "zqmexamples"

    def shortHelpString(self):
        return self.tr(
            "Buffers every feature in the input layer by the given distance "
            "and writes the result to a new layer. Distance units are the "
            "input layer's CRS units, so use a projected CRS for distances "
            "in metres. Features without a usable geometry are skipped and "
            "counted, not silently dropped without a trace."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input layer"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DISTANCE,
                self.tr("Buffer distance (layer CRS units)"),
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
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Buffered"),
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.tr("Invalid input layer"))
        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
        if distance <= 0:
            raise QgsProcessingException(
                self.tr("Buffer distance must be greater than zero")
            )
        segments = self.parameterAsInt(parameters, self.SEGMENTS, context)
        if segments < 1:
            raise QgsProcessingException(
                self.tr("Segments per quarter circle must be at least 1")
            )

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException(self.tr("Could not create output sink"))

        written = 0
        skipped = 0
        total = source.featureCount()
        for current, feature in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geometry = feature.geometry()
            if geometry is None or geometry.isEmpty():
                skipped += 1
                continue
            buffered = geometry.buffer(distance, segments)
            if buffered is None or buffered.isEmpty():
                skipped += 1
                continue
            out_feature = QgsFeature(sink.fields())
            out_feature.setGeometry(buffered)
            out_feature.setAttributes(feature.attributes())
            sink.addFeature(out_feature)
            written += 1
            if total > 0:
                feedback.setProgress(int(100 * (current + 1) / total))

        feedback.pushInfo(
            self.tr(f"Buffered {written} features, skipped {skipped}.")
        )
        return {self.OUTPUT: dest_id}
