"""Pattern 01: Vector analysis — buffer, dissolve, area stats."""
from qgis.core import QgsVectorLayer, QgsProject, QgsField
from qgis.PyQt.QtCore import QVariant

def vector_analysis(input_path, buffer_dist=500):
    layer = QgsVectorLayer(input_path, "input", "ogr")
    buf = processing.run("native:buffer", {"INPUT": layer, "DISTANCE": buffer_dist, "OUTPUT": "memory:"})["OUTPUT"]
    dissolved = processing.run("native:dissolve", {"INPUT": buf, "OUTPUT": "memory:"})["OUTPUT"]
    stats = processing.run("qgis:basicstatisticsforfields", {"INPUT": dissolved, "FIELD_NAME": "area"})["OUTPUT"]
    return dissolved, stats

if __name__ == "__main__":
    print("Pattern 01: vector analysis ready")
