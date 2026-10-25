"""Minimal functional QGIS plugin lifecycle example."""
from qgis.PyQt.QtWidgets import QAction


class MyPlugin:
    """Example plugin controller; QGIS supplies the interface object."""
    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):
        """Register a menu and toolbar action when the plugin is enabled."""
        if self.action is not None:
            return
        self.action = QAction("QGIS Resource Example", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&QGIS Resource Example", self.action)
        self.iface.addToolBarIcon(self.action)

    def run(self):
        self.iface.messageBar().pushInfo(
            "QGIS Resource Example", "Plugin action executed successfully."
        )

    def unload(self):
        """Remove UI registrations when the plugin is disabled."""
        if self.action is None:
            return
        self.iface.removePluginMenu("&QGIS Resource Example", self.action)
        self.iface.removeToolBarIcon(self.action)
        self.action.deleteLater()
        self.action = None
