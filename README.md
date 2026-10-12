# qgis-resources — QGIS & PyQGIS Resources for GIS Analysts and Geospatial Developers

[![Validate resources](https://github.com/ZQM-Computing/qgis-resources/actions/workflows/validate.yml/badge.svg)](https://github.com/ZQM-Computing/qgis-resources/actions)

Free, ready-to-use **QGIS resources**: documented **expression functions**, **PyQGIS code snippets**, **Processing workflow scripts**, **layer styles (.qml)**, and **QField field-data-collection templates** — the reusable pieces that speed up everyday desktop GIS work.

Everything here is meant to be dropped into a real project and adapted. Each resource states what it does, which QGIS version it needs, and the assumptions it makes about your layers and fields.

## What's inside

| Resource | What you get | Folder |
|---|---|---|
| Expression functions | Acreage in a projected CRS, attributes from intersecting or nearest features, label formatting, centroid coordinates — each explained line by line | [`expressions/`](expressions/) |
| PyQGIS snippets | Batch-export a whole project to GeoPackage, add XYZ basemaps in one run, export a print layout to a 300-DPI PDF | [`pyqgis/`](pyqgis/) |
| Processing workflows | A clip-and-reproject Processing script for analysis prep, plus a step-by-step Graphical Modeler recipe for zonal summaries | [`processing/`](processing/) |
| Layer styles | Parcel-boundary and flood-zone `.qml` styles, plus documented color palettes for land use and flood risk cartography | [`styles/`](styles/) |
| QField templates | A field-data-collection setup guide: offline GeoPackage packaging, value maps, constraints, photo attachments, and a pre-flight checklist | [`qfield/`](qfield/) |

## Who this is for

GIS analysts and geospatial developers who work in QGIS daily and keep re-solving the same problems: calculating real-world areas without falling into the Web Mercator trap, pulling attributes across layers without a messy join, styling the same layer types for the hundredth time, or packaging a project for offline field collection with QField. If you are moving from ArcGIS Pro to QGIS, the expression and PyQGIS examples are written to map onto concepts you already know.

## Quick start

- **Expressions:** open a layer's Field Calculator or label settings, switch to the expression editor, and paste the expression from [`expressions/`](expressions/) — each one names the fields and layers it expects.
- **PyQGIS snippets:** open Plugins → Python Console in QGIS, paste a script from [`pyqgis/`](pyqgis/), adjust the constants at the top, and run.
- **Processing script:** in the Processing Toolbox, choose Scripts → Add Script from File and select [`processing/clip_and_reproject.py`](processing/clip_and_reproject.py).
- **Styles:** Layer Properties → Symbology → Style (bottom-left menu) → Load Style, then pick a file from [`styles/`](styles/).
- **QField:** follow the packaging checklist in [`qfield/`](qfield/) before your next field day.

## Design principles

1. **No mystery code.** Every snippet is commented at the decision points, not line by line — you should be able to defend each choice in a code review or a project meeting.
2. **CRS honesty.** Area, distance, and buffer examples work in a projected CRS or say exactly why not. Nothing here silently measures in EPSG:3857.
3. **Versions stated.** QGIS moves fast; each resource names the oldest version it is known to fit (most target QGIS 3.28 LTR and newer).
4. **Adapt, don't worship.** Field names and layer names are placeholders — the value is the pattern, not the literal text.

## Repository layout

```text
.
├── expressions/   # documented QGIS expression functions
├── pyqgis/        # Python console / macro snippets
├── processing/  # Processing toolbox scripts + modeler recipes
├── styles/        # .qml layer styles + cartographic palettes
├── qfield/        # QField offline field-collection guidance
└── .github/       # CI that syntax-checks the Python and XML
```

## Contributing

Issues and pull requests are welcome — especially resources you have used in production and can document honestly: what it does, the QGIS version, the layer/field assumptions, and any sharp edges. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Maintainer

Maintained by [ZQM Computing](https://github.com/ZQM-Computing). Resources distilled from production GIS analysis, environmental permitting, and climate-resilience work — and from running QGIS/QField as the open-source side of a working geospatial practice — by Alex Zelenski, GISP.

## More from this series

- [postgis-patterns](https://github.com/ZQM-Computing/postgis-patterns) — Production PostGIS patterns: spatial indexing, joins & KNN, SRID management, vector tiles, data quality, partitioning
- [duckdb-spatial-patterns](https://github.com/ZQM-Computing/duckdb-spatial-patterns) — DuckDB Spatial patterns for analytical geospatial SQL: GeoParquet, spatial joins, KNN, H3 aggregation — no server required
- [geospatial-api-reference](https://github.com/ZQM-Computing/geospatial-api-reference) — OGC API – Features reference implementation with FastAPI and PostGIS backends
- [ollama-fleet-patterns](https://github.com/ZQM-Computing/ollama-fleet-patterns) — Ollama fleet operations: model management, health checks, load-spreading, VRAM budgeting, dependency-light RAG
- [proxmox-ceph-operations](https://github.com/ZQM-Computing/proxmox-ceph-operations) — Proxmox VE + Ceph operations runbooks: health checks, backup discipline, OSD replacement, upgrade checklists

## License

MIT — see [`LICENSE`](LICENSE).
