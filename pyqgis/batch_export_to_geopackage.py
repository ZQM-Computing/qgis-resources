"""Export vector layers in the current QGIS project into one GeoPackage.

Run from the QGIS Python Console. Existing output is protected by default:
pass overwrite=True only when replacing the destination is intentional.
"""
import os
import re
import tempfile
from pathlib import Path

from qgis.core import QgsProject, QgsVectorFileWriter, QgsVectorLayer

OUTPUT_GPKG = os.path.expanduser("~/qgis_project_export.gpkg")


def export_project_layers(output_path: str, overwrite: bool = False) -> list:
    project = QgsProject.instance()
    destination = Path(output_path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {destination}. Choose another path or pass overwrite=True."
        )

    vector_layers = [
        layer for layer in project.mapLayers().values()
        if isinstance(layer, QgsVectorLayer) and layer.isValid()
    ]
    if not vector_layers:
        raise ValueError("The current project has no valid vector layers to export")

    transform_context = project.transformContext()
    # Build the complete GeoPackage beside the destination and publish it only
    # after every layer is exported successfully. This protects an existing file.
    with tempfile.TemporaryDirectory(prefix="qgis-gpkg-export-", dir=destination.parent) as temp_dir:
        staged = Path(temp_dir) / destination.name
        exported = []
        used_names = set()
        for index, layer in enumerate(vector_layers):
            base_name = layer.name().strip() or f"layer_{index + 1}"
            base_name = re.sub(r"[^A-Za-z0-9_ -]", "_", base_name)[:50] or f"layer_{index + 1}"
            name = base_name
            suffix = 2
            while name.casefold() in used_names:
                name = f"{base_name}_{suffix}"
                suffix += 1
            used_names.add(name.casefold())

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = name
            if index == 0:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            else:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            result = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer, str(staged), transform_context, options
            )
            if result[0] != QgsVectorFileWriter.NoError:
                raise RuntimeError(f"Export failed for {layer.name()}: {result[3]}")
            exported.append({"source_layer": layer.name(), "output_layer": name})
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError("Staged GeoPackage is missing or empty")
        # Verify every intended layer can be reopened before publication.
        for item in exported:
            layer_uri = str(staged) + "|layername=" + item["output_layer"]
            check = QgsVectorLayer(layer_uri, item["output_layer"], "ogr")
            if not check.isValid():
                raise RuntimeError("Staged layer failed to reopen: " + item["output_layer"])
            source = next(layer for layer in vector_layers if layer.name() == item["source_layer"])
            if check.featureCount() != source.featureCount():
                raise RuntimeError("Feature count mismatch for exported layer " + item["output_layer"])
            del check
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Output appeared during export: {destination}")
        staged.replace(destination)
    print(f"Exported {len(exported)} vector layer(s) to {destination}")
    return exported


if __name__ in {"__main__", "__console__"}:
    export_project_layers(OUTPUT_GPKG)
