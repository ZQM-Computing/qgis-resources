# PyQGIS snippets

Small, single-purpose Python scripts for the QGIS Python Console. Each file's header docstring says what it does, where to run it, the QGIS version it was tested with, and what to adjust before running.

| Snippet | What it does |
|---|---|
| [`batch_export_to_geopackage.py`](batch_export_to_geopackage.py) | Exports every vector layer in the current project into one GeoPackage — handy for archiving a project, handing data to a client, or packaging for QField. |
| [`add_basemaps.py`](add_basemaps.py) | Adds OpenStreetMap, Esri World Imagery, and CartoDB Positron XYZ basemaps to the project in one run. |
| [`export_layout_pdf.py`](export_layout_pdf.py) | Exports a named print layout to a 300-DPI PDF — the repetitive step in every map-production workflow. |
| [`categorize_active_layer.py`](categorize_active_layer.py) | Applies a categorized renderer to the active vector layer, one colour per distinct value of a chosen field — the fastest way to turn a coded field into a readable map. |

## Running a snippet

1. Open QGIS with a project loaded.
2. Plugins → Python Console → Show Editor (or paste into the console prompt).
3. Adjust the constants at the top of the script.
4. Run. The snippets guard their entry point with `if __name__ == "__console__":`, which is the name QGIS gives console-executed scripts — so importing a file to reuse its functions won't trigger the run.

## Conventions in these snippets

- No third-party dependencies — PyQGIS (`qgis.core`) only.
- Errors raise, they don't print-and-continue: a half-exported deliverable is worse than a loud failure.
- File-writing functions take explicit paths; nothing silently writes next to your project file.
