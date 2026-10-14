"""
Add common XYZ tile basemaps (OpenStreetMap, Esri World Imagery,
CartoDB Positron) to the current QGIS project in one run.

Where to run: QGIS Python Console. Tested with QGIS 3.28+.

Notes:
    XYZ services are loaded through the "wms" provider with a type=xyz URI --
    the standard trick QGIS itself uses for saved XYZ connections.
    Respect each provider's tile usage policy; these endpoints are for
    ordinary desktop mapping, not bulk tile scraping.
"""

from qgis.core import QgsProject, QgsRasterLayer

BASEMAPS = {
    "OpenStreetMap": (
        "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19"
    ),
    "Esri World Imagery": (
        "type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}&zmax=18"
    ),
    "CartoDB Positron": (
        "type=xyz&url=https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png&zmax=20"
    ),
}


def add_basemap(name: str, uri: str):
    layer = QgsRasterLayer(uri, name, "wms")
    if not layer.isValid():
        print(f"Failed to load basemap: {name}")
        return None
    QgsProject.instance().addMapLayer(layer)
    return layer


if __name__ == "__console__":
    for basemap_name, basemap_uri in BASEMAPS.items():
        add_basemap(basemap_name, basemap_uri)
