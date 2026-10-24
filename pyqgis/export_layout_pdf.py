"""Export a named QGIS print layout to PDF."""
import os
from pathlib import Path

from qgis.core import QgsLayoutExporter, QgsProject

LAYOUT_NAME = "Main Map"
OUTPUT_PDF = os.path.expanduser("~/main_map.pdf")
DPI = 300


def export_layout_pdf(layout_name: str, output_path: str, dpi: int = 300) -> None:
    if not isinstance(dpi, int) or not 72 <= dpi <= 1200:
        raise ValueError("dpi must be an integer between 72 and 1200")
    destination = Path(output_path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)

    project = QgsProject.instance()
    layout = project.layoutManager().layoutByName(layout_name)
    if layout is None:
        raise ValueError(f"Layout not found in this project: {layout_name}")

    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = dpi
    result = exporter.exportToPdf(str(destination), settings)
    if result != QgsLayoutExporter.Success:
        raise RuntimeError(f"PDF export failed (exporter result code {result})")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("QGIS reported success but the PDF output is missing or empty")
    print(f"Exported {destination} at {dpi} DPI")
