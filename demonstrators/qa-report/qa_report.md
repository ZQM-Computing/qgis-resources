# QA Report — Synthetic Parcel Screening Data

**SYNTHETIC DATA ONLY — no real property is represented.** No client records were used. No survey/engineering licensure or ArcGIS Enterprise experience is claimed.

**Historical report snapshot:** The original GeoPackage run predates the QA hardening. Coverage-zero rows below have been conservatively relabeled FLAG after review; this edited snapshot is not evidence that the new generator was rerun. Regenerate with `python3 qa_report.py` against a newly built synthetic GeoPackage before client-facing use.

## Input

- Input used: GeoPackage
- Input file: `/home/hatch/workspace/commercial/demonstrators/parcel-screening/parcel_screening.gpkg`
- Input SHA-256: `6c65d13c3bf6d9e8adeea64261660453e00a15354b80860b5fb56ac276f04f8a`
- Note: layers read: flood_coverage, flood_hazard, parcels, wetland_indicator; source register read from the GeoPackage source_register table
- CRS: EPSG:32617 (WGS 84 / UTM zone 17N) on all layers
- Software: Python 3.12.3 (standard library only: sqlite3 3.45.1, struct, math, hashlib); no geopandas / fiona / shapely / ogr2ogr

## Per-check results

| Check | Result | Detail |
| --- | --- | --- |
| CRS consistency — all layers EPSG:32617 | PASS | layers report EPSG [32617]; expected [32617]. layers read: flood_coverage, flood_hazard, parcels, wetland_indicator; source register read from the GeoPackage source_register table |
| Geometry validity — ring closure, non-zero area, self-intersection spot-check | PASS | DEMO-P1: closed=True, area=10,000 m2, self-intersects=False; DEMO-P2: closed=True, area=10,000 m2, self-intersects=False; DEMO-P3: closed=True, area=10,000 m2, self-intersects=False; DEMO-P4: closed=True, area=10,000 m2, self-intersects=False; DEMO-P5: closed=True, area=10,000 m2, self-intersects=False; DEMO-P6: closed=True, area=10,000 m2, self-intersects=False |
| Attribute checks — parcel_id null / duplicate | PASS | parcels=6, duplicate parcel_id=none, null parcel_id=none |
| Overlap accounting — recomputed vs stored (±1 m2) | FLAG | DEMO-P1 wetland: 5,000 m2 recomputed vs 5,000 m2 stored [PASS]; DEMO-P1 flood: 0 m2 recomputed vs 0 m2 stored [PASS]; DEMO-P2 wetland: 0 m2 recomputed vs 0 m2 stored [FLAG]; DEMO-P2 flood: 2,500 m2 recomputed vs 2,500 m2 stored [PASS]; DEMO-P3 wetland: 5,000 m2 recomputed vs 5,000 m2 stored [PASS]; DEMO-P3 flood: 0 m2 recomputed vs 0 m2 stored [FLAG]; DEMO-P4 wetland: 2,500 m2 recomputed vs 2,500 m2 stored [PASS]; DEMO-P4 flood: 2,500 m2 recomputed vs 2,500 m2 stored [PASS]; DEMO-P5 wetland: 0 m2 recomputed vs 0 m2 stored [FLAG]; DEMO-P5 flood: 0 m2 recomputed vs 0 m2 stored [PASS]; DEMO-P6 wetland: 10,000 m2 recomputed vs 10,000 m2 stored [PASS]; DEMO-P6 flood: 2,500 m2 recomputed vs 2,500 m2 stored [PASS] |
| Source freshness — SYNTH-PARCELS-2026 | FLAG | accessed 2026-11-02T12:00:00Z; effective_date is null — unknown — freshness cannot be verified; accuracy/resolution also null (unknown) |
| Source freshness — SYNTH-WETLAND-2026 | FLAG | accessed 2026-11-02T12:00:00Z; effective_date is null — unknown — freshness cannot be verified; accuracy/resolution also null (unknown) |
| Source freshness — SYNTH-FLOOD-HAZARD-2026 | FLAG | accessed 2026-11-02T12:00:00Z; effective_date is null — unknown — freshness cannot be verified; accuracy/resolution also null (unknown) |
| Source freshness — SYNTH-FLOOD-COVERAGE-2026 | FLAG | accessed 2026-11-02T12:00:00Z; effective_date is null — unknown — freshness cannot be verified; accuracy/resolution also null (unknown) |
| Incoming batch — accept/reject computed from the checks | PASS | inputs 8, accepted 2, rejected 6; reason instances 7 across 6 rejected rows (a row can carry more than one reason) |

## Parcel geometry (recomputed)

| Parcel | Name | Type | Ring closed | Area (m2) | Area (acres) | Self-intersects | Defects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEMO-P1 | — | Polygon | True | 10,000 | 2.471053814671653 | False | none |
| DEMO-P2 | — | Polygon | True | 10,000 | 2.471053814671653 | False | none |
| DEMO-P3 | — | Polygon | True | 10,000 | 2.471053814671653 | False | none |
| DEMO-P4 | — | Polygon | True | 10,000 | 2.471053814671653 | False | none |
| DEMO-P5 | — | Polygon | True | 10,000 | 2.471053814671653 | False | none |
| DEMO-P6 | — | Polygon | True | 10,000 | 2.471053814671653 | False | none |

## Overlap accounting (recomputed from the geometries)

Overlap is recomputed by polygon clipping against the hazard geometry and compared with the stored attribute (tolerance 1 m2). Flood coverage is recomputed from the flood_coverage layer when present (the known-coverage extent, never hazard). Coverage is the share of the parcel the source is known to cover; where coverage is below 100% the overlap is verified for the known area only, and where coverage is 0% the overlap is unknown, not zero.

| Parcel | Hazard | Recomputed overlap (m2) | Overlap (% of parcel) | Stored overlap (m2) | Coverage (%) | Result | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEMO-P1 | wetland | 5,000 | 50 | 5,000 | 100.0 | PASS | recomputed 5,000 m2 matches stored 5,000 m2 (diff 0.00 m2, tolerance 1 m2) |
| DEMO-P1 | flood | 0 | 0 | 0 | 100.0 | PASS | recomputed 0 m2 matches stored 0 m2 (diff 0.00 m2, tolerance 1 m2); coverage recomputed 100% from the flood_coverage layer — matches stored |
| DEMO-P2 | wetland | 0 | 0 | 0 | 0.0 | FLAG | unknown — wetland coverage is 0.0%; recomputed 0 m2 is NOT a verified overlap |
| DEMO-P2 | flood | 2,500 | 25 | 2,500 | 50.0 | PASS | recomputed 2,500 m2 matches stored 2,500 m2 (diff 0.00 m2, tolerance 1 m2); coverage recomputed 50% from the flood_coverage layer — matches stored; note: flood coverage is only 50.0% of this parcel — the verified overlap covers the known area only |
| DEMO-P3 | wetland | 5,000 | 50 | 5,000 | 100.0 | PASS | recomputed 5,000 m2 matches stored 5,000 m2 (diff 0.00 m2, tolerance 1 m2) |
| DEMO-P3 | flood | 0 | 0 | 0 | 0.0 | FLAG | unknown — flood coverage is 0.0%; recomputed 0 m2 is NOT a verified overlap |
| DEMO-P4 | wetland | 2,500 | 25 | 2,500 | 50.0 | PASS | recomputed 2,500 m2 matches stored 2,500 m2 (diff 0.00 m2, tolerance 1 m2); note: wetland coverage is only 50.0% of this parcel — the verified overlap covers the known area only |
| DEMO-P4 | flood | 2,500 | 25 | 2,500 | 100.0 | PASS | recomputed 2,500 m2 matches stored 2,500 m2 (diff 0.00 m2, tolerance 1 m2); coverage recomputed 100% from the flood_coverage layer — matches stored |
| DEMO-P5 | wetland | 0 | 0 | 0 | 0.0 | FLAG | unknown — wetland coverage is 0.0%; recomputed 0 m2 is NOT a verified overlap |
| DEMO-P5 | flood | 0 | 0 | 0 | 50.0 | PASS | recomputed 0 m2 matches stored 0 m2 (diff 0.00 m2, tolerance 1 m2); coverage recomputed 50% from the flood_coverage layer — matches stored; note: flood coverage is only 50.0% of this parcel — the verified overlap covers the known area only |
| DEMO-P6 | wetland | 10,000 | 100 | 10,000 | 100.0 | PASS | recomputed 10,000 m2 matches stored 10,000 m2 (diff 0.00 m2, tolerance 1 m2) |
| DEMO-P6 | flood | 2,500 | 25 | 2,500 | 100.0 | PASS | recomputed 2,500 m2 matches stored 2,500 m2 (diff 0.00 m2, tolerance 1 m2); coverage recomputed 100% from the flood_coverage layer — matches stored |

## Source register — timestamp validation

| Source | Accessed | Effective date | Accuracy | Resolution | Finding |
| --- | --- | --- | --- | --- | --- |
| SYNTH-PARCELS-2026 | 2026-11-02T12:00:00Z | null (unknown) | null (unknown) | null (unknown) | effective_date null — unknown — freshness cannot be verified |
| SYNTH-WETLAND-2026 | 2026-11-02T12:00:00Z | null (unknown) | null (unknown) | null (unknown) | effective_date null — unknown — freshness cannot be verified |
| SYNTH-FLOOD-HAZARD-2026 | 2026-11-02T12:00:00Z | null (unknown) | null (unknown) | null (unknown) | effective_date null — unknown — freshness cannot be verified |
| SYNTH-FLOOD-COVERAGE-2026 | 2026-11-02T12:00:00Z | null (unknown) | null (unknown) | null (unknown) | effective_date null — unknown — freshness cannot be verified |

## Reconciliation

Counts account for every input row. A row can have more than one reject reason, so reason totals are not a second row count.

| Batch | Inputs | Accepted | Rejected | Check |
| --- | --- | --- | --- | --- |
| Main parcels (6 synthetic parcels) | 6 | 6 | 0 | inputs = accepted + rejected ✓ |
| Incoming test batch | 8 | 2 | 6 | inputs = accepted + rejected ✓ |

## Incoming test batch — reason-coded reject list

| Record | Parcel ID | Name | Type | Reasons | Disposition |
| --- | --- | --- | --- | --- | --- |
| B-001 | B-001 | Batch Parcel 1 | Polygon | — | ACCEPT |
| B-002 | B-002 | Batch Parcel 2 | Polygon | — | ACCEPT |
| B-001 | B-001 | Batch Parcel 1 duplicate | Polygon | DUPLICATE_IDENTIFIER (duplicate identifier) | REJECT |
| B-004 | B-004 | (missing) | Polygon | MISSING_NAME (missing name) | REJECT |
| B-005 | B-005 | Batch Parcel 5 | Polygon | UNUSABLE_GEOMETRY (unusable geometry) | REJECT |
| B-006 | B-006 | Batch Parcel 6 | Point | WRONG_GEOMETRY_TYPE (wrong geometry type) | REJECT |
| B-007 | B-007 | Batch Parcel 7 | Polygon | OUTSIDE_BOUNDARY (record outside the boundary) | REJECT |
| B-008 | B-008 | (missing) | Polygon | MISSING_NAME (missing name), OUTSIDE_BOUNDARY (record outside the boundary) | REJECT |

### Reject reason totals (instances, not rows)

- DUPLICATE_IDENTIFIER (duplicate identifier): 1
- MISSING_NAME (missing name): 2
- OUTSIDE_BOUNDARY (record outside the boundary): 2
- UNUSABLE_GEOMETRY (unusable geometry): 1
- WRONG_GEOMETRY_TYPE (wrong geometry type): 1
- **Total reason instances: 7 across 6 rejected rows** — a row can carry more than one reason, so this total is not a row count.
