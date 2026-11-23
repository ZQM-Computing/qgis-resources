# Synthetic GIS Demonstrators — Alex Zelenski

**SYNTHETIC DATA ONLY — no real property, project, place, or client is
represented.** Every file, map, and report in this folder is a
demonstration built from invented fixtures. Nothing here deploys,
registers, or spends money; everything runs from local files.

Built 2026-11-16 to support Upwork applications (direct-buyer rows
371–379 in the outreach tracker). The four demonstrators share one
fixture family so their numbers agree with each other and with the live
site's synthetic samples for [environmental screening](https://zqmlabs.com/computing/services/environmental-screening/) and
[GIS automation](https://zqmlabs.com/computing/services/gis-automation/).

## Shared fixture

- **Parcels:** six synthetic 100 × 100 m parcels, EPSG:32617, each
  10,000 m² (2.471053814671653 acres). DEMO-P1/DEMO-P2 are the two-parcel
  fixture from the live site; DEMO-P3–P6 extend it with the same CRS
  and QA vocabulary.
  - DEMO-P1: wetland 5,000 m² (50%), coverage 100%; flood 0 m², coverage 100%.
  - DEMO-P2: wetland 0 m², coverage **unknown** (0% coverage — the overlap
    is unknown, not zero); flood 2,500 m² (25%), coverage 50%.
  - DEMO-P3: wetland 5,000 m² (50%), coverage 100%; flood 0 m², coverage unknown.
  - DEMO-P4: wetland 2,500 m² (25%), coverage 50%; flood 2,500 m² (25%), coverage 100%.
  - DEMO-P5: wetland 0 m², coverage unknown; flood 0 m², coverage 50%.
  - DEMO-P6: wetland 10,000 m² (100%), coverage 100%; flood 2,500 m² (25%), coverage 100%.
- **Source register:** synthetic sources only (`https://example.org/synthetic/…`),
  accessed 2026-11-02T12:00:00Z, effective date / accuracy / resolution
  null (unknown). Boundary basis on every record: "synthetic fixture;
  not a surveyed boundary".
- **QA vocabulary:** reject reasons are duplicate identifier, missing
  name, unusable geometry, wrong geometry type, outside boundary. A row
  can carry more than one reason, so reason totals are never a second
  row count.

## The four demonstrators

### (a) Parcel screening + constraints GeoPackage — `parcel-screening/`

What it proves: a real, QGIS-openable GeoPackage with parcels,
wetland/flood constraint layers, a flood-coverage extent layer, and a
source-register table, all internally consistent (overlap numbers
recomputed from the stored geometries match the stored attributes).

- `parcel_screening.gpkg` — layers `parcels` (6), `wetland_indicator` (4),
  `flood_hazard` (3), `flood_coverage` (5), `source_register` (4 rows).
- `parcel_screening.geojson` — same 6 parcels (EPSG:32617 metre coords).
- `build_parcel_screening.py` / `verify_parcel_screening.py` — build +
  independent read-back verification.
- Open in QGIS: drag the `.gpkg` in; all layers are EPSG:32617.
- Verified: `python3 verify_parcel_screening.py` → exit 0, 35 PASS,
  "VERIFICATION PASSED: all checks green."

Limits: synthetic fixture only; wetland coverage is carried as an
attribute (there is no separate `wetland_coverage` layer). Not a survey,
delineation, or regulatory determination.

### (b) Internal land-parcel web map — `parcel-web-map/`

What it proves: a static MapLibre GL map of the same six parcels with
click/hover popups carrying the screening numbers, wetland/flood layer
toggles, and client-side-only KML/KMZ import (toGeoJSON + JSZip — files
are parsed in the browser, nothing is uploaded).

- `index.html` — double-click to open; no server. Needs internet for the
  CDN libraries (MapLibre GL JS, toGeoJSON, JSZip) and CartoDB basemap tiles.
- `parcels.geojson` — the embedded fixture as a standalone file,
  byte-identical to the GeoJSON embedded in the page (13 features).
- Honesty note (on the page and in its README): this is a **static
  front-end demonstration, not a live PostGIS app** — the production
  version would be PostGIS-backed.
- Verified: `node --check` exit 0; embedded GeoJSON parses (13 features);
  UTM→WGS84 conversion asserted to reproduce the original DEMO-P1/DEMO-P2
  corners exactly; headless render (Playwright + chromium headless shell,
  throwaway copy with local library files) verified exact popups for
  DEMO-P1, DEMO-P2, DEMO-P4, DEMO-P5, DEMO-P6 and the flood/wetland
  overlays, KML import ("Imported 1 feature(s) from test.kml"), and the
  wetland toggle. Sandbox-only caveats: basemap tiles are blank in the
  sandbox (no internet; tiles verified HTTP 200 via curl), GeoJSON layers
  can need a few extra seconds before answering queries in the slow
  headless shell, and clicking exactly on a polygon corner is hit-test
  ambiguous (interior clicks work).

Limits: no backend, no PostGIS, no saved state. Do not present as a live
PostGIS application.

### (c) Python data QA report — `qa-report/`

What it proves: a standard-library-only Python script that really
computes QA checks against the GeoPackage from (a) and writes a
reconciliation report — nothing is hardcoded.

- `qa_report.py` — run with `python3 qa_report.py` (exit 0). Reads the
  GeoPackage when present (else the bundled `fixtures/parcel_screening.json`).
  Checks: CRS consistency, geometry validity (closure / area /
  self-intersection), parcel_id null/duplicate, overlap accounting
  recomputed from the geometries vs stored attributes, source timestamp
  freshness, and a planted-defect 8-record incoming batch (2 clean, 6
  defective) accepted/rejected by the same validators.
- `qa_report.md` / `qa_report.html` — generated reports (regenerate by
  re-running the script).
- Verified (2026-11-16, against the real GeoPackage): exit 0; every check
  PASS except the four source-freshness FLAGs (correct — effective dates
  are null/unknown, and the register is now read from the GeoPackage's
  own `source_register` table); all 12 recomputed overlaps match stored;
  main reconciliation 6 = 6 + 0; incoming batch 8 = 2 + 6 with 7 reason
  instances across 6 rejected rows.

Limits: the planted-defect batch is a test batch by design; FLAG means
"cannot be verified", not "wrong".

### (d) Accessible interactive project map — `project-map/`

What it proves: a public-style project map driven by an editable CSV,
with full keyboard accessibility.

- `projects.csv` — 6 synthetic projects; edit the CSV and reload the page
  to update the map (a byte-identical copy is embedded as a `file://`
  fallback, disclosed on screen, because browsers often block local `fetch()`).
- `index.html` — double-click to open. Markers are real `<button>` elements
  with aria-labels; arrow keys move between projects; Enter/Space opens the
  detail panel; focus moves into the panel and returns on Close/Escape;
  a text list alternative carries the same details; category filter with
  `aria-live` count; visible `:focus-visible` outlines; WCAG 2.1 AA
  contrast (worst passing pair 5.98:1 for the focus outline, body text
  17.40:1).
- Verified: CSV parses (6 rows, expected columns, coordinates in range);
  `node --check` exit 0; arrow-key/focus/list wiring inspected; all CDN
  URLs return HTTP 200.

Limits: demonstration projects only — fictional names, illustrative
points near New Smyrna Beach, no real sites. Do not present as a client
project map.

## What is NOT claimed

No ArcGIS Enterprise experience, no professional survey or engineering
licensure, no client results or references. All prices, rates, and
delivery claims live in the offer package, not in these files. These
demonstrators show workflow and method on synthetic data only.

## Note on the GitHub copy

`parcel-screening/parcel_screening.gpkg` is a binary file and is not
stored in git; regenerate it with
`python3 parcel-screening/build_parcel_screening.py` (its contents are
fully described by `parcel_screening.geojson` plus the build script).
