"""
Batch-export every vector layer in the current QGIS project into a single
GeoPackage, one GeoPackage layer per project layer.

Where to run: QGIS Python Console (Plugins -> Python Console), or as a
project macro. Tested with QGIS 3.34.

Adjust before running:
    OUTPUT_GPKG -- destination file (created or overwritten).
"""

import os

from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

OUTPUT_GPKG = os.path.expanduser("~/qgis_project_export.gpkg")


def export_project_layers(output_path: str) -> None:
    project = QgsProject.instance()
    transform_context = project.transformContext()

    exported = []
    skipped = []

    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            skipped.append(layer.name())
            continue

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer.name()
        # First layer creates (or overwrites) the file; later layers are
        # added to the same GeoPackage.
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile
            if not exported
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )

        error = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            output_path,
            transform_context,
            options,
        )
        # writeAsVectorFormatV3 returns (error, new_file, new_layer, message).
        if error[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Export failed for {layer.name()}: {error[3]}")
        exported.append(layer.name())

    print(f"Exported {len(exported)} layer(s) to {output_path}: {exported}")
    if skipped:
        print(f"Skipped non-vector layer(s): {skipped}")


if __name__ == "__console__":
    export_project_layers(OUTPUT_GPKG)
