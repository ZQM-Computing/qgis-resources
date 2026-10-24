# Dataset inventory and QA CLI

## Purpose and status

`scripts/dataset_qa.py` is the first implementation of the repository's read-only inventory and quality-report tool. It inspects supported vector and raster datasets through GDAL/OGR and writes a JSON report plus an optional Markdown summary. It does not repair or rewrite source data.

**Status:** implemented; deterministic report-contract tests are added. Dataset-level execution still requires testing in a Python environment with GDAL bindings and synthetic datasets. Do not describe this tool as runtime-validated until those tests have been run.

## Requirements

Use a Python interpreter with `osgeo.gdal` and `osgeo.ogr` available. The QGIS Python environment usually provides these bindings. A generic Python installation may not. Check with:

```bash
python -c "from osgeo import gdal, ogr; print(gdal.VersionInfo('--version'))"
```

The script currently recognizes common file-based vector formats (GeoPackage, Shapefile, GeoJSON/JSON, GML, KML, SQLite) and raster formats (GeoTIFF, VRT, IMG, ASCII grid, JP2, NetCDF). Actual driver availability depends on the GDAL build. Directory inputs are searched recursively. Unsupported formats are ignored; recognized files that cannot be opened are reported as errors.

## Usage

Audit a folder, requiring a field and checking a candidate identifier for nulls/duplicates:

```bash
python scripts/dataset_qa.py ./data \
  --root . \
  --required-field asset_id \
  --id-field asset_id \
  --expected-crs EPSG:26917 \
  --json reports/data-qa.json \
  --markdown reports/data-qa.md
```

Audit explicit files and skip per-feature geometry-validity checks when datasets are too large for that cost:

```bash
python scripts/dataset_qa.py parcels.gpkg elevation.tif \
  --root . --skip-geometry-validity \
  --json reports/quick-inventory.json
```

Exit status:
- `0`: no errors found.
- `1`: errors found, or warnings found when `--fail-on-warning` is set.
- `2`: command-line/configuration error (including missing GDAL bindings).

## Checks currently implemented

### Vector layers
- Driver, layer name, geometry type, feature count, CRS, and field names/types.
- Missing CRS (error), configured CRS mismatch (warning), empty layer (warning).
- Configured required fields (error).
- Configured candidate identifier fields: null/blank and duplicate occurrences (warnings).
- Missing/empty geometry and provider-reported invalid geometry (warnings), unless geometry validity checks are disabled.

The identifier check treats the first configured identifier field present on a layer as the candidate key. A uniqueness rule is not inferred automatically. It does not test domain-specific uniqueness or normalize values.

### Raster datasets
- Driver, dimensions, band count, CRS, affine geotransform, extent, pixel resolution, and per-band data type, nodata, scale, offset, and block size.
- Missing CRS or nonpositive dimensions/band count (errors).
- Missing geotransform and configured CRS mismatch (warnings).
- Non-finite affine transform values (error).

This initial version does not yet compute raster statistics, inspect every pixel for nodata/NaN anomalies, compare raster alignment across a collection, or assert an expected resolution/extent. Those checks should be added only with clear configuration semantics and synthetic tests.

## Report model

JSON includes `schema_version`, inventory records, findings, a severity summary, and unreadable recognized datasets. Each finding has a stable `rule_id`, severity, dataset, message, and remediation guidance; layer/evidence fields are included when applicable. Findings are sorted deterministically to support review and diffing. Markdown is a human-readable rendering of the same findings.

Relative dataset paths are reported relative to `--root` when possible. For inputs outside that root, only the basename is reported to avoid accidentally publishing full machine paths.

## Safety and limitations

- Inputs are opened read-only. Reports are the only files this command writes.
- A missing CRS is never guessed from coordinate values.
- Findings are diagnostic signals, not automatic repair instructions. Review data provenance before changing a dataset.
- Geometry validity checks can be expensive and depend on GDAL/OGR/GEOS provider behavior.
- This is an inventory/QA first increment, not a replacement for QGIS project inspection or domain-specific validation.
- Current tests validate report schema, deterministic ordering, summary counts, and report rendering without GDAL. The runtime integration script is `scripts/validate_dataset_qa_runtime.py`. It creates synthetic GeoPackage and GeoTIFF inputs, asserts inventory values and deliberate findings, checks JSON serialization, and verifies that the source files are unchanged. The QGIS runtime workflow invokes it after installing QGIS/GDAL. This test is implemented but remains unverified until the workflow completes successfully on the current PR head.
