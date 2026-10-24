"""Register the ZQM Processing provider in QGIS."""
from qgis.core import QgsApplication

from .provider import ZqmProcessingProvider


class ZqmGeospatialToolsPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        if self.provider is not None:
            return
        self.provider = ZqmProcessingProvider()
        if not QgsApplication.processingRegistry().addProvider(self.provider):
            self.provider = None
            raise RuntimeError("QGIS could not register the ZQM Processing provider")

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
