"""Processing provider for ZQM Geospatial Tools."""
from qgis.core import QgsProcessingProvider

from .batch_buffer_algorithm import BatchBufferAlgorithm


class ZqmProcessingProvider(QgsProcessingProvider):
    def id(self):
        return "zqm_geospatial_tools"

    def name(self):
        return "ZQM Geospatial Tools"

    def longName(self):
        return self.name()

    def loadAlgorithms(self):
        self.addAlgorithm(BatchBufferAlgorithm())
