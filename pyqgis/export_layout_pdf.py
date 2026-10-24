"""Export a named QGIS print layout to PDF."""
import os
import tempfile
from pathlib import Path

from qgis.core import QgsLayoutExporter, QgsProject

LAYOUT_NAME = "Main Map"
OUTPUT_PDF = os.path.expanduser("~/main_map.pdf")
DPI = 300


def export_layout_pdf(layout_name: str, output_path: str, dpi: int = 300, overwrite: bool = False) -> None:
    if not isinstance(dpi, int) or not 72 <= dpi <= 1200:
        raise ValueError("dpi must be an integer between 72 and 1200")
    destination = Path(output_path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {destination}. Pass overwrite=True to replace it."
        )

    project = QgsProject.instance()
    layout = project.layoutManager().layoutByName(layout_name)
    if layout is None:
        raise ValueError(f"Layout not found in this project: {layout_name}")

    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = dpi
    # Stage beside the destination so publication stays on the same filesystem.
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.stem}.", suffix=destination.suffix,
        dir=destination.parent, delete=False
    ) as staged_file:
        temporary = Path(staged_file.name)
    temporary.unlink(missing_ok=True)
    result = exporter.exportToPdf(str(temporary), settings)
    if result != QgsLayoutExporter.Success:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"PDF export failed (exporter result code {result})")
    if not temporary.is_file() or temporary.stat().st_size < 5:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("QGIS reported success but the temporary PDF is missing or empty")
    with temporary.open("rb") as pdf_file:
        if pdf_file.read(5) != b"%PDF-":
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Exported file does not have a PDF signature")
    if destination.exists() and not overwrite:
        temporary.unlink(missing_ok=True)
        raise FileExistsError(f"Output appeared during export: {destination}")
    os.replace(temporary, destination)
    print(f"Exported {destination} at {dpi} DPI")
