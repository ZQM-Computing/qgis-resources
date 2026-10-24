"""Apply native:buffer to every GeoPackage in a folder."""
import math
import os
import tempfile
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
    if not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
        raise ValueError("distance must be a finite, non-negative number")
    destination = Path(output_folder) if output_folder else None
    if destination:
        destination.mkdir(parents=True, exist_ok=True)
    results = []
    # Snapshot inputs before writing outputs. If source and destination are the
    # same directory, newly created *_buffer.gpkg files must not be reprocessed.
    input_paths = sorted(
        path for path in source_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".gpkg"
        and not path.stem.lower().endswith("_buffer")
    )
    for path in input_paths:
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
        output = "memory:"
        staged_path = None
        try:
            if output_path:
                with tempfile.NamedTemporaryFile(
                    prefix=f".{output_path.stem}.", suffix=".gpkg",
                    dir=output_path.parent, delete=False
                ) as staged_file:
                    staged_path = Path(staged_file.name)
                staged_path.unlink(missing_ok=True)
                output = str(staged_path)
            result = processing.run("native:buffer", {
                "INPUT": layer, "DISTANCE": distance, "SEGMENTS": 8,
                "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
                "DISSOLVE": False, "OUTPUT": output,
            })["OUTPUT"]
            if output_path and (staged_path is None or not staged_path.is_file() or staged_path.stat().st_size == 0):
                raise RuntimeError(f"Processing did not create a non-empty output file: {staged_path}")
            if output_path:
                check = QgsVectorLayer(str(staged_path), path.stem + "_buffer_check", "ogr")
                if not check.isValid():
                    raise RuntimeError(f"Processing output is not a valid vector layer: {output_path}")
                if check.crs() != layer.crs():
                    raise RuntimeError(
                        f"CRS mismatch for {output_path}: "
                        f"expected {layer.crs().authid()}, found {check.crs().authid()}"
                    )
                if check.featureCount() != layer.featureCount():
                    raise RuntimeError(
                        f"Feature-count mismatch for {output_path}: "
                        f"expected {layer.featureCount()}, found {check.featureCount()}"
                    )
                del check
                if output_path.exists() and not overwrite:
                    raise FileExistsError(f"Output appeared during processing: {output_path}")
                os.replace(staged_path, output_path)
                staged_path = None
            results.append({
                "input": str(path), "ok": True,
                "output": str(output_path) if output_path else result,
            })
        except Exception as exc:
            results.append({"input": str(path), "ok": False, "error": str(exc)})
        finally:
            if staged_path is not None:
                staged_path.unlink(missing_ok=True)
    return results


if __name__ == "__main__":
    print("Import batch_process() in QGIS and provide an input folder and distance.")
