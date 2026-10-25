# qgis-resources — QGIS & PyQGIS Resources for GIS Analysts and Geospatial Developers

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![GitHub](https://img.shields.io/github/stars/ZQM-Computing/qgis-resources?style=social)

<!-- ZQM-START -->
<!-- markdownlint-disable MD033 -->
<p align="center">
  <strong>ZQM Computing — Geospatial Engineering & Scientific Computing</strong><br>
  <a href="https://github.com/ZQM-Computing">ZQM Computing</a> •
  <a href="https://github.com/ZQM-Labs">ZQM Labs</a>
</p>
<!-- markdownlint-enable MD033 -->
<!-- ZQM-END -->

[![Validate resources](https://github.com/ZQM-Computing/qgis-resources/actions/workflows/ci.yml/badge.svg)](https://github.com/ZQM-Computing/qgis-resources/actions)

QGIS and PyQGIS resources for GIS analysts and geospatial developers: expressions, Python utilities, Processing scripts, QML styles, QField field-collection guidance, and dataset QA tools. Examples document runtime requirements, coordinate reference system (CRS) assumptions, inputs, outputs, and limitations.

## Repository role and status

**Status:** Active, public.

This repository is the QGIS-specific part of the ZQM Computing geospatial portfolio. Examples use synthetic data where practical. Scripts intended for the QGIS Python Console or a QGIS Python environment are labelled accordingly. Static CI checks do not substitute for executing algorithms inside QGIS.

## What we are building

The roadmap prioritizes trustworthy runtime validation, a read-only dataset inventory/QA report, a reproducible preparation workflow, focused Processing algorithms, and one end-to-end synthetic reference project. See the [product roadmap](docs/PRODUCT_ROADMAP.md) for priorities and exit criteria and the [workflow contracts](docs/WORKFLOW_CONTRACTS.md) for input/output safety, spatial semantics, and test expectations. These documents describe intended direction; they do not imply every planned capability is implemented.

## What's inside

| Resource | What you get | Folder |
|---|---|---|
| Expressions | Area, overlay, label, and coordinate expression guidance | [expressions/](expressions/) |
| PyQGIS utilities | GeoPackage export, XYZ basemaps, PDF layout export | [pyqgis/](pyqgis/) |
| Processing workflows | Clip/reproject algorithm and Graphical Modeler recipe | [patterns/](patterns/) and [processing/](processing/) |
| Styles | QML starting styles and cartographic palettes | [styles/](styles/) |
| Field collection | QField offline-collection and packaging guidance | [qfield/](qfield/) |
| Worked examples | Expression basics, Processing, spatial join, CRS transform, buffering, plugin lifecycle | [examples/](examples/) |
| Dataset QA | Read-only GDAL/OGR vector/raster inventory and JSON/Markdown findings | [dataset QA guide](docs/DATASET_QA.md) and [scripts/dataset_qa.py](scripts/dataset_qa.py) |
| Validation | Documentation checks, static audits, unit/contract tests, and QGIS runtime tests | [scripts/](scripts/) and [tests/](tests/) |
| Engineering plan | Prioritized product roadmap and geospatial workflow contracts | [docs/PRODUCT_ROADMAP.md](docs/PRODUCT_ROADMAP.md) and [docs/WORKFLOW_CONTRACTS.md](docs/WORKFLOW_CONTRACTS.md) |
| QGIS plugin | Processing provider with batch-buffer tool | [zqm_geospatial_tools/](zqm_geospatial_tools/) |

## Quick start

- **Expressions:** use [expressions/README.md](expressions/README.md); verify layer CRS and field names before using measurement expressions.
- **PyQGIS:** run scripts from the QGIS Python Console after reviewing configuration constants.
- **Processing script:** add [patterns/clip_and_reproject.py](patterns/clip_and_reproject.py) through Processing Toolbox → Scripts → Add Script from File.
- **Styles:** load .qml files through Layer Properties → Symbology → Style → Load Style. These are starting styles, not validated thematic classification schemes.
- **Dataset inventory and QA:** see [docs/DATASET_QA.md](docs/DATASET_QA.md). The initial CLI reads supported datasets through GDAL/OGR and writes JSON plus optional Markdown reports; it does not modify inputs. A synthetic GeoPackage/GeoTIFF integration test and a separate synthetic DEM reprojection/clip/slope test are wired into the QGIS runtime workflow. Coverage now includes semantic CRS equivalence, safe repeat audits, invalid/empty mask rejection, and source immutability; both tests require an exact-head passing run before runtime validation can be claimed.
- **Examples:** see [examples/](examples/). QGIS-dependent examples must run in a QGIS Python environment with Processing initialized.
- **ZQM Geospatial Tools plugin:** see [zqm_geospatial_tools/README.md](zqm_geospatial_tools/README.md) for installation. The initial Processing tool buffers selected vector layers into separate GeoPackages.
- **Notebooks:** notebooks require a Python kernel with QGIS bindings available; they will not run in a generic Python kernel without QGIS.

## Coordinate reference system policy

Coordinate transformations change coordinates; CRS assignment does not. Area, distance, and buffer values use the relevant geometry or algorithm units. Do not assume degrees are metres or that EPSG:3857 is suitable for measurement. Select a local or regional projected CRS appropriate to the study area and state the choice in analysis outputs. EPSG:4326 is used for interchange examples, not as a universal measurement CRS.

## Validation levels

Use [workflow contracts and test strategy](docs/WORKFLOW_CONTRACTS.md) when adding or changing a tool. Use [the product roadmap](docs/PRODUCT_ROADMAP.md) to prioritize work; do not add snippets solely to increase repository size.

- **Static checks:** Python syntax, notebook structure and cell parsing, QML structure, empty/placeholder implementation checks, existing-script contracts, and internal Markdown links.
- **Unit tests:** repository contracts and deterministic checks that do not require QGIS.
- **QGIS runtime:** the QGIS-enabled workflow executes the expression and synthetic examples, checks file-backed vector/join/CRS/batch patterns, runs clip/reproject, loads existing QML styles, and exercises the packaged batch-buffer algorithm. Raster processing has strengthened output/CRS/dimension checks and a synthetic DEM integration test wired into QGIS CI; representative-data validation and a successful exact-head CI run remain outstanding. GUI-driven plugin interactions require manual checks. A green static workflow does not imply complete production validation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions should include tool versions, synthetic test data where possible, expected outputs, and documented CRS and boundary assumptions.

## Related geospatial repositories

- [geospatial-cookbooks](https://github.com/ZQM-Computing/geospatial-cookbooks) — umbrella index.
- [postgis-cookbook](https://github.com/ZQM-Computing/postgis-cookbook) — spatial SQL and PostGIS.
- [geopandas-cookbook](https://github.com/ZQM-Computing/geopandas-cookbook) — Python vector analysis.
- [gdal-cookbook](https://github.com/ZQM-Computing/gdal-cookbook) — raster and vector conversion.
- [geospatial-api-reference](https://github.com/ZQM-Computing/geospatial-api-reference) — OGC API Features reference implementation.

For shared documentation conventions, see the [geospatial-cookbooks documentation standard](https://github.com/ZQM-Computing/geospatial-cookbooks/blob/main/docs/repository-documentation-standard.md).

## License

MIT — see [LICENSE](LICENSE).

*Part of [ZQM Computing](https://github.com/ZQM-Computing) — geospatial engineering, scientific computing, and infrastructure patterns.*
