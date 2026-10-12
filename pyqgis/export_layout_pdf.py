"""
Export a named print layout to a print-ready PDF (300 DPI by default).

Where to run: QGIS Python Console, or adapt into a processing script for
batch map production. Tested with QGIS 3.34.

Adjust before running:
    LAYOUT_NAME -- name of the layout in the current project.
    OUTPUT_PDF  -- destination file.
    DPI         -- export resolution.
"""

import os

from qgis.core import QgsLayoutExporter, QgsProject

LAYOUT_NAME = "Main Map"
OUTPUT_PDF = os.path.expanduser("~/main_map.pdf")
DPI = 300


def export_layout_pdf(layout_name: str, output_path: str, dpi: int = 300) -> None:
    project = QgsProject.instance()
    layout = project.layoutManager().layoutByName(layout_name)
    if layout is None:
        raise ValueError(f"Layout not found in this project: {layout_name}")

    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = dpi

    result = exporter.exportToPdf(output_path, settings)
    if result != QgsLayoutExporter.Success:
        raise RuntimeError(f"PDF export failed (exporter result code {result})")
    print(f"Exported {output_path}")


if __name__ == "__console__":
    export_layout_pdf(LAYOUT_NAME, OUTPUT_PDF, DPI)
