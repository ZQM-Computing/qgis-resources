![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![GitHub](https://img.shields.io/github/stars/ZQM-Computing/qgis-resources?style=social)
# qgis-resources — QGIS & PyQGIS Resources for GIS Analysts and Geospatial Developers

<!-- ZQM-START -->
<!-- markdownlint-disable MD033 -->
<p align="center">
  <strong>ZQM Computing — Geospatial Engineering & Scientific Computing</strong><br>
  <a href="https://github.com/ZQM-Computing">ZQM Computing</a> •
  <a href="https://github.com/ZQM-Labs">ZQM Labs</a>
</p>
<!-- markdownlint-enable MD033 -->
<!-- ZQM-END -->

[![Validate resources](https://github.com/ZQM-Computing/qgis-resources/actions/workflows/validate.yml/badge.svg)](https://github.com/ZQM-Computing/qgis-resources/actions)

Free, ready-to-use **QGIS resources**: documented **expression functions**, **PyQGIS code snippets**, **Processing workflow scripts**, **layer styles (.qml)**, and **QField field-data-collection templates** — the reusable pieces that speed up everyday desktop GIS work.

Everything here is meant to be dropped into a real project and adapted. Each resource states what it does, which QGIS version it needs, and the assumptions it makes about your layers and fields.

## Repository role and status

**Status:** Active, public.

**What this repository is:** QGIS resources for GIS analysts — documented expression functions, PyQGIS code snippets, Processing workflow scripts, layer styles (.qml), and QField field-data-collection templates, ready to drop into a real project.

**What it contributes:** Part of the ZQM Computing public geospatial portfolio — production-grade pattern and reference repositories that document geospatial engineering practice across the stack. This repository is the reusable pattern library for its layer: working code and runbooks that practitioners can lift into their own pipelines, and portfolio evidence of the engineering practice behind ZQM Computing. The umbrella index for the series is [geospatial-patterns](https://github.com/ZQM-Computing/geospatial-patterns).

**Standing:** The portfolio program was completed and Tier-1 hardened on 2026-10-15, with prose CI enforced as required status checks. This repository is standalone — no other repository or deployment depends on it.

## What's inside

| Resource | What you get | Folder |
|---|---|---|
| Expression functions | Acreage in a projected CRS, attributes from intersecting or nearest features, label formatting, centroid coordinates — each explained line by line | [`expressions/`](expressions/) |
| PyQGIS snippets | Batch-export a whole project to GeoPackage, add XYZ basemaps in one run, export a print layout to a 300-DPI PDF | [`pyqgis/`](pyqgis/) |
| Processing workflows | A clip-and-reproject Processing script for analysis prep, plus a step-by-step Graphical Modeler recipe for zonal summaries | [`processing/`](processing/) |
| Layer styles | Parcel-boundary and zone `.qml` styles, plus documented color palettes for land use and risk cartography | [`styles/`](styles/) |
| QField templates | A field-data-collection setup guide: offline GeoPackage packaging, value maps, constraints, photo attachments, and a pre-flight checklist | [`qfield/`](qfield/) |
| Walkthrough examples | Numbered worked examples — expression basics and a Processing script run — pairing the resources above with sample workflows | [`examples/`](examples/) |
| Validation scripts | Documentation and link checks (`check_docs.py`) run by CI | [`scripts/`](scripts/) |
| Tests | Validation tests for the expression resources (`test_expressions.py`) | [`tests/`](tests/) |

## Who this is for

GIS analysts and geospatial developers who work in QGIS daily and keep re-solving the same problems: calculating real-world areas without falling into the Web Mercator trap, pulling attributes across layers without a messy join, styling the same layer types for the hundredth time, or packaging a project for offline field collection with QField. If you are moving from ArcGIS Pro to QGIS, the expression and PyQGIS examples are written to map onto concepts you already know.

## Quick start

- **Expressions:** open a layer's Field Calculator or label settings, switch to the expression editor, and paste the expression from [`expressions/`](expressions/) — each one names the fields and layers it expects.
- **PyQGIS snippets:** open Plugins → Python Console in QGIS, paste a script from [`pyqgis/`](pyqgis/), adjust the constants at the top, and run.
- **Processing script:** in the Processing Toolbox, choose Scripts → Add Script from File and select [`processing/clip_and_reproject.py`](processing/clip_and_reproject.py).
- **Styles:** Layer Properties → Symbology → Style (bottom-left menu) → Load Style, then pick a file from [`styles/`](styles/).
- **QField:** follow the packaging checklist in [`qfield/`](qfield/) before your next field day.
- **Examples:** work through the numbered walkthroughs in [`examples/`](examples/) — `01-expression-basics` and `02-processing-script`.

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
├── examples/      # numbered worked examples (expression basics, Processing script)
├── scripts/       # documentation/link checks (check_docs.py)
├── tests/         # validation tests for expressions (test_expressions.py)
└── .github/       # CI that syntax-checks the Python and XML
```

## Contributing

Issues and pull requests are welcome — especially resources you have used in production and can document honestly: what it does, the QGIS version, the layer/field assumptions, and any sharp edges. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Maintainer

Maintained by [ZQM Computing](https://github.com/ZQM-Computing). Resources distilled from production GIS analysis and environmental permitting work — and from running QGIS/QField as the open-source side of a working geospatial practice — by Alex Zelenski, GISP.

## Related repositories

- [postgis-patterns](https://github.com/ZQM-Computing/postgis-patterns) — Production PostGIS patterns: spatial indexing, joins & KNN, SRID management, vector tiles, data quality, partitioning
- [duckdb-spatial-patterns](https://github.com/ZQM-Computing/duckdb-spatial-patterns) — DuckDB Spatial patterns for analytical geospatial SQL: GeoParquet, spatial joins, KNN, H3 aggregation — no server required
- [pgrouting-patterns](https://github.com/ZQM-Computing/pgrouting-patterns) — pgRouting network analysis on PostGIS: shortest path, driving distance, isochrones, turn restrictions, traffic-aware routing
- [geopandas-patterns](https://github.com/ZQM-Computing/geopandas-patterns) — GeoPandas/Shapely patterns for Python geospatial workflows: spatial joins, CRS handling, overlays, interpolation, performance
- [gdal-patterns](https://github.com/ZQM-Computing/gdal-patterns) — GDAL/OGR command-line patterns: conversion, reprojection, clipping, mosaicking — production-tested, runnable examples
- [stac-patterns](https://github.com/ZQM-Computing/stac-patterns) — STAC patterns for geospatial data discovery: catalogs, item validation, search API, bulk operations, cloud deployment
- [maplibre-patterns](https://github.com/ZQM-Computing/maplibre-patterns) — MapLibre GL JS patterns for frontend vector tile rendering: custom layers, 3D terrain, performance tuning, interactive maps
- [cog-patterns](https://github.com/ZQM-Computing/cog-patterns) — Cloud Optimized GeoTIFF patterns: creation, validation, TiTiler serving, xarray integration, performance benchmarking
- [geoparquet-patterns](https://github.com/ZQM-Computing/geoparquet-patterns) — GeoParquet patterns for columnar geospatial analytics: partitioning, predicate pushdown, DuckDB/Spark integration
- [h3-patterns](https://github.com/ZQM-Computing/h3-patterns) — H3 hexagonal grid patterns: indexing, aggregation, visualization, grid comparisons, performance benchmarks
- [geospatial-api-reference](https://github.com/ZQM-Computing/geospatial-api-reference) — OGC API – Features reference implementation with FastAPI and PostGIS backends
- [ollama-fleet-patterns](https://github.com/ZQM-Computing/ollama-fleet-patterns) — Ollama fleet operations: model management, health checks, load-spreading, VRAM budgeting, dependency-light RAG
- [proxmox-ceph-operations](https://github.com/ZQM-Computing/proxmox-ceph-operations) — Proxmox VE + Ceph operations runbooks: health checks, backup discipline, OSD replacement, upgrade checklists
- [geospatial-patterns](https://github.com/ZQM-Computing/geospatial-patterns) — Umbrella index for all ZQM geospatial pattern repos

## Documentation and validation

For setup instructions, reproducible examples, data provenance, CRS/SRID assumptions, security guidance, and dependency labels, follow the [ZQM geospatial repository documentation standard](https://github.com/ZQM-Computing/geospatial-patterns/blob/main/docs/repository-documentation-standard.md).

The configured CI workflow is the source of truth for automated checks. A passing workflow establishes only that its checks passed for that commit; it does not certify production deployment or prove that every dependency and operating environment was covered.

## Installation

No installation — clone the repository and browse the resource collection.

## License

MIT — see [`LICENSE`](LICENSE).

*Part of [ZQM Computing](https://github.com/ZQM-Computing) — geospatial engineering, scientific computing, and infrastructure patterns; the geospatial arm of [ZQM Labs](https://zqmlabs.com), makers of Z's Quests & Mischief location games.*

<!-- ZQM-FOOTER-START -->
<!-- markdownlint-disable MD033 -->
---

<p align="center">
  <em>Play more. Plan less.</em><br>
  <a href="https://zqmlabs.com">zqmlabs.com</a> •
  <a href="https://github.com/ZQM-Labs">ZQM Labs</a> •
  <a href="https://github.com/ZQM-Computing">ZQM Computing</a>
</p>
<!-- markdownlint-enable MD033 -->
<!-- ZQM-FOOTER-END -->
