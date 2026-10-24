# Workflow contracts and test strategy

This document defines expected behavior for geospatial tools. It guides implementation and tests; it does not claim every current script already meets every contract.

## 1. Input contract

Validate actual input objects and declared assumptions before processing.

### Vector inputs
- Layer exists, is valid, and has a usable provider.
- Geometry type is supported by the selected algorithm.
- CRS is valid when the operation requires coordinate interpretation or measurement.
- Required fields exist with compatible types.
- Empty inputs are explicitly handled or rejected with a useful error.
- Multi-layer operations declare whether mixed CRSs are supported and how they are normalized.

### Raster inputs
- Dataset opens and has at least one usable band.
- CRS, extent, dimensions, resolution, and nodata metadata are inspected.
- Algorithms requiring a projected CRS reject unsuitable inputs or explicitly reproject them.
- Slope and terrain calculations document horizontal and vertical units; z_factor must represent the appropriate unit ratio.
- Alignment and resampling choices are explicit when combining rasters.

Never infer a CRS from coordinate values. Assigning a CRS labels existing coordinates; transforming a CRS changes coordinates. A missing CRS must not be silently guessed from coordinate range.

## 2. Output contract

- Output CRS is explicit and verified after writing.
- Vector outputs are reopened and checked for validity, geometry type, feature count, and required fields.
- Raster outputs are reopened and checked for CRS, dimensions, band count, extent/resolution, and nodata behavior as relevant.
- Tests assert spatial values or geometry relationships, not only file existence.
- Existing outputs are preserved unless overwrite was explicitly requested.
- Where practical, write to a unique temporary path in the destination directory, validate the staged artifact, then atomically replace the destination.
- Temporary files are cleaned after success and failure.
- A partial batch reports per-input status and does not pretend all inputs succeeded.

## 3. Spatial semantics

Every algorithm should document:
- CRS of inputs and outputs.
- Units used for distances, areas, buffers, elevations, and thresholds.
- Whether operations are planar or geodesic.
- Handling of invalid, empty, multipart, and null geometries.
- Boundary semantics for intersects, contains, within, clipping, and joins.
- Duplicate matches and one-to-many relationships.
- Raster resampling, alignment, nodata propagation, and pixel-edge behavior where relevant.

A projected CRS alone does not guarantee that it is appropriate for every measurement. Select a CRS suitable for the study area and purpose.

## 4. Errors, cancellation, and recovery

- Validate parameters before creating deliverables.
- Use Processing feedback and check cancellation between meaningful stages.
- Surface actionable messages identifying the failed input and operation.
- Do not swallow exceptions and continue with corrupted or incomplete results.
- Clean temporary resources in finally-style cleanup paths.
- Do not replace a known-good output until the replacement has been written and validated.
- Test invalid inputs, failed writes where feasible, cancellation, and overwrite refusal.

## 5. Reproducible tests

Use small synthetic datasets with known answers. Avoid external downloads for the core test suite.

Minimum test classes:
1. Happy path with known feature/raster result.
2. Empty input or no spatial overlap.
3. Invalid/missing CRS.
4. Unexpected geometry or missing field.
5. Duplicate identifiers or one-to-many join behavior.
6. Output schema and CRS verification after reopening.
7. Existing-output preservation and explicit overwrite.
8. Failure cleanup and cancellation.
9. Measurement-unit and nodata edge cases for raster/terrain tools.

Record QGIS/GDAL versions for runtime runs. A test that only searches source code for a string is a contract lint, not a functional test.

## 6. CI layers

- **Static:** syntax, Markdown links, notebook JSON/structure, QML XML, and resource inventory.
- **Unit/contract:** deterministic Python checks that do not need QGIS.
- **QGIS runtime:** actual algorithm execution and assertions against generated outputs.
- **Manual/representative-data:** GUI usability, target desktop behavior, and representative data not suited to small CI fixtures.

Report each layer separately. Static CI success is not runtime or production validation.

## 7. Run manifest

For multi-step workflows, record where practical:
- Tool/repository version and run identifier.
- QGIS, GDAL, and relevant provider versions.
- Parameters and target CRS.
- Input identifiers and layer names; avoid leaking credentials or sensitive paths.
- Output paths, counts, CRS, and validation results.
- Warnings, skipped inputs, failures, and elapsed time.

A manifest supports traceability; a successful file write alone does not prove analytical correctness.
