"""ZQM Geospatial Tools QGIS plugin entry point."""
from .plugin import ZqmGeospatialToolsPlugin


def classFactory(iface):
    return ZqmGeospatialToolsPlugin(iface)
