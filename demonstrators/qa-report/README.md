# QA Report — Python Data QA + Source Timestamp Validation

**SYNTHETIC DATA ONLY — no real property is represented.** No client
records, no real parcels. No survey/engineering licensure or ArcGIS
Enterprise experience is claimed. No client names or references are
invented. Nothing here deploys, registers, or spends money; it is
local files only.

## What the script proves

`qa_report.py` runs real, computed QA checks — outcomes are never
hardcoded — against the synthetic parcel fixture from the
GIS-automation service page (EPSG:32617, 100 × 100 m parcels, each
10,000 m² / 2.471053814671653 acres). The core is the two-parcel
fixture DEMO-P1/DEMO-P2; the GeoPackage extends it to six parcels
(DEMO-P1–DEMO-P6) with the same CRS and the same QA vocabulary:

- **Geometry validity** — every parcel ring is checked for closure,
  non-zero area (shoelace), and self-intersection (segment-intersection
  spot-check).
- **CRS consistency** — every layer must report EPSG:32617.
- **Attribute checks** — `parcel_id` null / duplicate checks on the
  main parcels (they carry no name attribute by design — they are
  identified by `parcel_id`; the missing-name check applies to the
  incoming named records, not to them).
- **Overlap accounting** — each parcel's wetland/flood overlap is
  **recomputed from the actual geometries** (Sutherland–Hodgman polygon
  clipping; the fixture polygons are convex rectangles, so the clip is
  exact) and compared with the stored attribute, tolerance 1 m².
  Expected recomputed values: DEMO-P1 wetland 5,000 m² (50%),
  flood 0 m²; DEMO-P2 wetland unknown (0% coverage — the recomputed
  0 m² is *not* a verified overlap), flood 2,500 m² (25%). DEMO-P3–P6
  are verified the same way against their stored attributes. Flood
  overlap is recomputed against the `flood_hazard` layer only; flood
  coverage is recomputed from the separate `flood_coverage` layer
  (the known-coverage extent, never hazard).
- **Source timestamp freshness** — the register is read from the
  GeoPackage's `source_register` table when present (four synthetic
  sources: parcels, wetland inventory, flood hazard, flood coverage),
  or from the bundled fixture JSON otherwise (two sources:
  `synthetic-flood_hazard`, `synthetic-wetland_inventory`). All are
  accessed 2026-11-02T12:00:00Z with `effective_date` null.
  The script flags that as **"unknown — freshness cannot be verified"**
  (accuracy/resolution are likewise null/unknown). It does not invent
  a freshness verdict from the access date alone.
- **Planted-defect incoming batch** — an 8-record test batch defined
  in the script (2 clean records that must pass; 6 defective records
  covering the documented reasons: duplicate identifier, missing name,
  unusable geometry, wrong geometry type, outside boundary). One
  record (B-008) carries two reasons, so the 6 rejected rows produce
  7 reason instances — reason totals are *not* a second row count.
  Accept/reject is computed by running the same validators as on the
  main parcels.

## How to run

```bash
cd ~/workspace/commercial/demonstrators/qa-report
python3 qa_report.py
```

Exit code is 0 on a successful run (a run that completes and writes
the reports). QA findings are reported in the output, not hidden by
the exit code.

## What it reads

1. `~/workspace/commercial/demonstrators/parcel-screening/parcel_screening.gpkg`
   — the GeoPackage built in parallel. When present, it is validated
   (read with the standard library only: `sqlite3` + `struct` WKB
   parsing, including the GeoPackage `GP` header). The report states
   which input was used and its SHA-256.
2. `fixtures/parcel_screening.json` — the bundled fixture (the exact
   numbers above), used when the GeoPackage does not exist yet. It is
   also the fallback source of the source register and the expected
   overlap values for the two-parcel core. When the GeoPackage is
   present, the GeoPackage is the live input and its
   `source_register` table is the register of record.

Tooling: Python 3.12 standard library only. `geopandas` / `fiona` /
`shapely` / `ogr2ogr` are not installed and are not needed.

## Outputs

- `qa_report.md` — the full report: per-check results, recomputed
  parcel geometry, overlap accounting, source register, reconciliation
  table, reason-coded reject list.
- `qa_report.html` — a simple styled HTML version of the same report.

## How to interpret the report

- **PASS / FLAG / FAIL** per check. FLAG means "cannot be verified"
  (not "wrong") — e.g. DEMO-P2's wetland overlap and both sources'
  freshness are FLAGs, because the coverage / effective date is
  unknown.
- **Reconciliation table** — inputs = accepted + rejected, for both
  the main parcels (6 = 6 + 0) and the incoming batch (8 = 2 + 6).
  If those sums ever fail, the run is broken, not the data.
- **Reject reason totals** — counted as *instances*; B-008 contributes
  two, so 7 instances across 6 rejected rows is correct.
