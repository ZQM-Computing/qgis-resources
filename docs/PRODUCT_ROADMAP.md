# Product roadmap: from resource collection to geospatial toolkit

## Purpose

This repository should help GIS analysts and geospatial developers inspect, prepare, analyze, verify, and deliver spatial data reproducibly. Success is measured by whether a user can solve a documented problem from a clean checkout and trust the outputs—not by the number of scripts, notebooks, or CI workflows.

## Current assessment

The repository has useful building blocks: expression recipes, vector and raster patterns, CRS transformations, spatial joins, batch processing, QML styles, PyQGIS exporters, QField guidance, worked examples, and an initial Processing plugin.

The main gaps are integration and evidence:
- Many resources are isolated examples rather than complete, reproducible workflows.
- Static checks cannot establish that QGIS algorithms produce correct spatial results.
- The plugin currently offers a narrow batch-buffer operation rather than a cohesive data-preparation toolkit.
- Styles, notebooks, and expressions need runnable examples and expected results to be approachable.
- Workflow duplication and publishing configuration should be justified by user outcomes.
- Runtime claims must identify the QGIS version and exact commit actually tested.

This is a working assessment, not a claim that every existing resource is defective. Preserve useful code unless tests or user value provide a reason to change it.

## Product principles

1. Solve real GIS tasks; prefer complete workflows over disconnected snippets.
2. Preserve source data. Audits are read-only by default; repair and replacement require explicit choices.
3. Make spatial assumptions visible: CRS, coordinate units, area/distance units, vertical units, nodata behavior, geometry semantics, and boundary rules.
4. Verify outputs, not implementation markers. Assert real features, values, schemas, CRS, raster properties, and files.
5. Fail clearly and recover safely. Report errors per input, clean temporary outputs, and never publish partial deliverables as complete.
6. Prefer reproducible synthetic fixtures and known expected results.
7. Keep architecture proportionate. Share validation and reporting logic when it prevents drift; avoid unnecessary frameworks.
8. Distinguish implemented, tested, and validated-for-use capabilities.

## Priority roadmap

### P0 — Establish a trustworthy baseline

- [ ] Obtain CI results for the exact PR head before treating it as validated.
- [ ] Run the QGIS runtime suite on a supported QGIS version and record the version in test output.
- [x] Add a synthetic-raster integration test for reprojection, clipping, slope generation, CRS, dimensions, nodata handling, and expected numeric bounds; execution on the current PR head remains pending.
- [ ] Test invalid/missing CRS, empty intersection, malformed inputs, cancellation, unwritable destinations, and existing-output preservation.
- [ ] Review output-type assumptions (paths versus live QGIS layers), Processing result validation, and resource cleanup.
- [ ] Keep the PR in draft until these checks pass; a missing run is not a passing run.

**Exit criteria:** a fresh checkout runs the documented static and QGIS runtime commands; the exact commit has visible passing checks; remaining gaps are documented.

### P1 — Build a read-only dataset inventory and QA report (initial CLI implemented; runtime validation outstanding)

The first CLI increment exists at `scripts/dataset_qa.py`; its usage and current limits are documented in [DATASET_QA.md](DATASET_QA.md). It inventories supported vector and raster inputs through GDAL/OGR and emits JSON plus an optional Markdown report. Report-contract tests cover stable findings, sorting, summaries, Markdown rendering, non-finite metadata, and undefined CRS placeholders. A synthetic GeoPackage/GeoTIFF runtime test is wired into the QGIS workflow; the run has not yet been observed on the current PR head.

Initial checks:
- Dataset/layer discovery, file format, and size.
- Vector geometry type, feature count, CRS, field names/types, empty or invalid geometries, and duplicate/null identifiers when configured.
- Raster dimensions, band count, CRS, resolution, extent, and nodata metadata.
- Configurable required fields, expected geometry types, and expected CRS.
- Findings with stable rule IDs, severity, evidence, and remediation guidance.

The default audit must not modify source data or silently assign a CRS, repair geometries, delete features, or rewrite fields.

**Remaining exit criteria:** obtain an exact-head passing QGIS/GDAL workflow run; extend malformed-input and provider-compatibility cases as issues are found; keep source immutability checks. The synthetic GeoPackage/GeoTIFF fixtures, deliberate CRS/schema/identifier/empty-geometry checks, repeated-report determinism assertion, and source immutability checks are implemented and wired into CI, but not yet runtime-verified.

### P2 — Integrate a reproducible preparation workflow

Build on existing scripts rather than rewriting them wholesale. Support explicit configuration for:
1. Discovering inputs.
2. Validating preconditions.
3. Reprojecting to a user-selected CRS.
4. Clipping/filtering where configured.
5. Running selected analyses.
6. Verifying outputs.
7. Writing a run manifest and summary.

Where available, the manifest records repository/tool version, QGIS/GDAL versions, parameters, input identities, output paths, counts, CRS, warnings, failures, and timestamps. Do not include secrets or unnecessary sensitive paths.

**Exit criteria:** a synthetic example runs end-to-end; reruns are predictable; a deliberately bad input produces a clear failure without damaging successful or pre-existing outputs.

### P3 — Expand the Processing plugin around repeated work

Prioritize:
1. Dataset inventory and validation.
2. Batch reproject and export.
3. Geometry and attribute QA.
4. Clip and standardize multiple layers.
5. Spatial joins and zonal summaries.
6. Raster preparation and validation.
7. Report/map production.

Each algorithm must define parameters, supported geometry types, CRS behavior, units, output schema, overwrite policy, feedback/cancellation behavior, and failure modes. Use shared helpers only where they establish consistent behavior across algorithms.

**Exit criteria:** runtime tests cover Processing Toolbox discovery, parameter validation, cancellation, output writing, overwrite behavior, and expected spatial results.

### P4 — Ship one complete reference project

Use synthetic data to demonstrate an end-to-end watershed or land-cover assessment:
- Study boundary, land-cover polygons, sample observations, and a small synthetic elevation raster.
- A QGIS project and explicit processing configuration.
- Expected output layers and a print layout.
- A QA report and run manifest.
- A clean-checkout run guide and automated assertions.

**Exit criteria:** a new contributor can reproduce expected outputs without private data, undocumented credentials, or manual edits to source files.

### P5 — Make supporting resources teach and demonstrate

- Expressions: include input schema, QGIS version, expression, expected output, and edge cases.
- Notebooks: define learning outcomes, run top-to-bottom, use deterministic inputs, and assert meaningful results.
- QML styles: demonstrate against compatible sample data and state whether the style is a starter symbol or validated thematic renderer.
- QField: provide a small working project with form/constraint configuration and documented offline/synchronization checks.
- Examples: each demonstrates a distinct concept and runs from a clean checkout or clearly states its required QGIS environment.

### P6 — Simplify maintenance and publishing

- Review overlapping CI jobs; consolidate duplicate work without removing meaningful security or runtime coverage.
- Keep publishing only if it produces a maintained, useful documentation site.
- Remove stale, duplicative, or misleading content only after verifying that no supported workflow depends on it.
- Keep the README focused on installation, first success, supported environments, and links to detailed guides.

## Definition of done for any new resource

A resource is not complete merely because its file exists or parses. It should include:
- The problem it solves and when not to use it.
- Supported QGIS/Python/GDAL versions or explicit assumptions.
- Inputs, parameters, outputs, schema, and failure behavior.
- CRS and measurement assumptions.
- A deterministic test or a clear explanation of why automated execution is not possible.
- A runnable usage example and expected result.
- Safe output handling and no hidden destructive behavior.
- Updated documentation and risk-appropriate CI coverage.

## Status vocabulary

- **Implemented:** code is present.
- **Static-checked:** syntax or structural checks passed.
- **Runtime-tested:** executed in the stated environment and assertions passed.
- **Validated for use:** runtime tests plus representative-data and operational checks support the documented use case.

Do not use a stronger status than the evidence supports.

## Out of scope until the core toolkit is reliable

- Adding low-value snippets solely to increase repository size.
- A generalized workflow engine before multiple proven workflows need one.
- Automatic destructive repair of user data.
- Claims of universal QGIS compatibility without a tested version matrix.
- Expanding CI complexity without a concrete quality or security benefit.

## Review cadence

Revisit priorities after each phase. Prefer completing and demonstrating one useful capability over starting several partial features.
