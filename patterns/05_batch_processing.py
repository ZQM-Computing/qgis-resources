"""Apply native:buffer to every GeoPackage in a folder."""
from pathlib import Path
import processing
from qgis.core import QgsVectorLayer


def batch_process(folder, distance=100.0, output_folder=None, overwrite=False):
    """Buffer every .gpkg file; return per-file success/error records.

    Distance is in each input layer's CRS units. Use a suitable projected CRS
    when the intended distance is in metres. Existing output files are
    preserved by default; set overwrite=True only when replacement is intended.
    """
    source_dir = Path(folder)
    if not source_dir.is_dir():
        raise ValueError(f"Input folder does not exist: {source_dir}")
    if distance < 0:
        raise ValueError("distance must be non-negative")
    destination = Path(output_folder) if output_folder else None
    if destination:
        destination.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(source_dir.glob("*.gpkg")):
        layer = QgsVectorLayer(str(path), path.stem, "ogr")
        if not layer.isValid():
            results.append({"input": str(path), "ok": False, "error": "invalid vector layer"})
            continue
        output_path = destination / f"{path.stem}_buffer.gpkg" if destination else None
        if output_path and output_path.exists() and not overwrite:
            results.append({
                "input": str(path), "ok": False,
                "error": f"output already exists (set overwrite=True to replace): {output_path}",
            })
            continue
        output = str(output_path) if output_path else "memory:"
        try:
            result = processing.run("native:buffer", {
                "INPUT": layer, "DISTANCE": distance, "SEGMENTS": 8,
                "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
                "DISSOLVE": False, "OUTPUT": output,
            })["OUTPUT"]
            if output_path and (not output_path.is_file() or output_path.stat().st_size == 0):
                raise RuntimeError(f"Processing did not create a non-empty output file: {output_path}")
            if output_path:
                check = QgsVectorLayer(str(output_path), path.stem + "_buffer_check", "ogr")
                if not check.isValid():
                    raise RuntimeError(f"Processing output is not a valid vector layer: {output_path}")
            results.append({"input": str(path), "ok": True, "output": result})
        except Exception as exc:
            results.append({"input": str(path), "ok": False, "error": str(exc)})
    return results


if __name__ == "__main__":
    print("Import batch_process() in QGIS and provide an input folder and distance.")
