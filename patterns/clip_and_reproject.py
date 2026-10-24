"""
Clip a vector layer to a boundary and reproject the result in one step --
the standard "prep this layer for analysis" move, as a Processing script.

Install: Processing Toolbox -> Scripts -> Add Script from File, then run
"Clip and reproject (analysis prep)" from the ZQM Examples group.

Designed for the QGIS Processing framework. The chain is:
    native:reprojectlayer  ->  native:clip  ->  sink
Reprojecting first means the clip runs in the analysis CRS, so any
downstream area/distance math is consistent.
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
)
from qgis.PyQt.QtCore import QCoreApplication

import processing


class ClipAndReprojectAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BOUNDARY = "BOUNDARY"
    TARGET_CRS = "TARGET_CRS"
    OUTPUT = "OUTPUT"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return ClipAndReprojectAlgorithm()

    def name(self):
        return "clipandreproject"

    def displayName(self):
        return self.tr("Clip and reproject (analysis prep)")

    def group(self):
        return self.tr("ZQM Examples")

    def groupId(self):
        return "zqmexamples"

    def shortHelpString(self):
        return self.tr(
            "Reprojects the input layer to the target CRS, clips it to the "
            "boundary layer (also reprojected), and writes the result. Use "
            "before area, distance, or overlay analysis so every layer "
            "shares one CRS."
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
            QgsProcessingParameterFeatureSource(
                self.BOUNDARY,
                self.tr("Boundary (clip) layer"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterCrs(
                self.TARGET_CRS,
                self.tr("Target CRS"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Clipped"))
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT)
            )
        boundary = self.parameterAsSource(parameters, self.BOUNDARY, context)
        if boundary is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.BOUNDARY)
            )
        target_crs = self.parameterAsCrs(parameters, self.TARGET_CRS, context)
        if not source.sourceCrs().isValid():
            raise QgsProcessingException("Input layer has no valid source CRS; assign the correct CRS before reprojection.")
        if not boundary.sourceCrs().isValid():
            raise QgsProcessingException("Boundary layer has no valid source CRS; assign the correct CRS before reprojection.")
        if not target_crs.isValid():
            raise QgsProcessingException("Choose a valid target CRS appropriate for the study area and measurements.")
        if feedback.isCanceled():
            raise QgsProcessingException("Processing was canceled before reprojection.")

        # Step 1: reproject both inputs into the analysis CRS.
        feedback.pushInfo("Reprojecting input layer...")
        reprojected_input = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": parameters[self.INPUT],
                "TARGET_CRS": target_crs,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

        if feedback.isCanceled():
            raise QgsProcessingException("Processing was canceled after input reprojection.")
        reprojected_boundary = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": parameters[self.BOUNDARY],
                "TARGET_CRS": target_crs,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

        if feedback.isCanceled():
            raise QgsProcessingException("Processing was canceled after boundary reprojection.")
        # Step 2: clip.
        feedback.pushInfo("Clipping...")
        clipped = processing.run(
            "native:clip",
            {
                "INPUT": reprojected_input,
                "OVERLAY": reprojected_boundary,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

        if feedback.isCanceled():
            raise QgsProcessingException("Processing was canceled after clipping.")
        # Step 3: write to the sink in the target CRS.
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            target_crs,
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        if not clipped or not clipped.isValid():
            raise QgsProcessingException("Clip algorithm returned an invalid output layer.")
        feature_count = 0
        for feature in clipped.getFeatures():
            if feedback.isCanceled():
                raise QgsProcessingException("Processing was canceled; output may be incomplete.")
            if not sink.addFeature(feature):
                raise QgsProcessingException(f"Could not write clipped feature {feature.id()} to the output sink.")
            feature_count += 1

        feedback.pushInfo(f"Wrote {feature_count} feature(s).")
        return {self.OUTPUT: dest_id}
