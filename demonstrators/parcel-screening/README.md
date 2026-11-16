# Parcel Screening — Synthetic Demonstrator (a)

**SYNTHETIC DATA ONLY — no real property is represented.**
Every parcel, wetland polygon, and flood polygon in this folder is an
invented fixture drawn on a blank 100 m grid. No client records, no real
parcels, and no real property data were used. Nothing here is a surveyed
boundary, a flood determination, or a wetland delineation, and nothing in
this demonstrator claims survey or engineering licensure or ArcGIS
Enterprise experience.

Prepared for Alex Zelenski (individual GISP, New Smyrna Beach, FL) as a
portfolio demonstrator of a parcel-screening + constraints workflow:
given a parcel, report how much of it overlaps mapped constraints and how
much of it the source inventory actually covers — because an overlap of
"0%" means something very different when coverage is 100% (mapped, clear)
than when coverage is 0% (unmapped, unknown).

## Files

| File | Contents |
|---|---|
| `parcel_screening.gpkg` | GeoPackage (EPSG:32617) — layers `parcels`, `wetland_indicator`, `flood_hazard`, `flood_coverage`, `source_register` |
| `parcel_screening.geojson` | Same six parcels, identical attributes, same CRS — for the web-map demonstrator to reuse |
| `build_parcel_screening.py` | Build script (geopandas/shapely); regenerates both files |
| `verify_parcel_screening.py` | Read-back verification; exits non-zero on any failed check |
| `README.md` | This file |

Static/local files only. Nothing here is deployed, registered, or charged.

## Coordinate system and fixture geometry

- CRS: **EPSG:32617** (UTM zone 17N, metres). Grid origin (500000, 3200000).
- Every parcel is a 100 × 100 m square = **10,000 m² = 2.471053814671653 acres**
  (1 m² = 0.0002471053814671653 ac).

| Parcel | Bounds (EPSG:32617) |
|---|---|
| DEMO-P1 | (500000, 3200000)–(500100, 3200100) |
| DEMO-P2 | (500100, 3200000)–(500200, 3200100) |
| DEMO-P3 | (500200, 3200000)–(500300, 3200100) |
| DEMO-P4 | (500300, 3200000)–(500400, 3200100) |
| DEMO-P5 | (500000, 3200100)–(500100, 3200200) |
| DEMO-P6 | (500100, 3200100)–(500200, 3200200) |

Constraint polygons (all axis-aligned rectangles on the same grid):

- **Wetland indicator** — western half of DEMO-P1 (500000,3200000)–(500050,3200100),
  5,000 m²; southern half of DEMO-P3, 5,000 m²; north-west quarter of DEMO-P4
  (500300,3200050)–(500350,3200100), 2,500 m²; whole of DEMO-P6, 10,000 m².
- **Flood hazard** — 50 × 50 m square in the northern half of DEMO-P2
  (500100,3200050)–(500150,3200100), 2,500 m²; southern strip of DEMO-P4
  (500300,3200000)–(500400,3200025), 2,500 m²; south-west quarter of DEMO-P6
  (500100,3200100)–(500150,3200150), 2,500 m².
- **Flood coverage extent** — whole of DEMO-P1; northern half of DEMO-P2
  (500100,3200050)–(500200,3200100), 5,000 m²; whole of DEMO-P4; eastern half
  of DEMO-P5 (500050,3200100)–(500100,3200200), 5,000 m²; whole of DEMO-P6.
  DEMO-P3 has no flood coverage.

## Schema

### `parcels` (Polygon, 6 rows)

| Column | Meaning |
|---|---|
| `parcel_id` | DEMO-P1 … DEMO-P6 |
| `parcel_m2` | Parcel area in m² (10,000) |
| `parcel_acres` | Parcel area in acres (2.471053814671653) |
| `wetland_overlap_m2` / `wetland_overlap_pct` | Area / % of parcel intersecting `wetland_indicator` |
| `wetland_coverage_pct` | % of parcel covered by the wetland inventory's mapped extent (see below) |
| `flood_overlap_m2` / `flood_overlap_pct` | Area / % of parcel intersecting `flood_hazard` |
| `flood_coverage_pct` | % of parcel intersecting `flood_coverage` |
| `notes` | Plain-language screening note for the parcel |
| `data_class` | `SYNTHETIC - no real property is represented` |

### `wetland_indicator` (Polygon, 4 rows) / `flood_hazard` (Polygon, 3 rows) / `flood_coverage` (Polygon, 5 rows)

`feature_id` (WI-01…, FH-01…, FC-01…), `parcel_id` (the parcel the polygon
lies in), `area_m2`, `data_class` (same SYNTHETIC label).

### `source_register` (non-spatial attribute table, 4 rows)

| Column | Value (all rows unless noted) |
|---|---|
| `layer` | `parcels` / `wetland_indicator` / `flood_hazard` / `flood_coverage` |
| `dataset_id` | `SYNTH-PARCELS-2026`, `SYNTH-WETLAND-2026`, `SYNTH-FLOOD-HAZARD-2026`, `SYNTH-FLOOD-COVERAGE-2026` |
| `constraint_type` | `parcel boundary (synthetic fixture)`, `wetland inventory`, `flood hazard`, `flood hazard coverage extent` |
| `source_url` | `https://example.org/synthetic/<dataset>` (`parcels`, `wetland-inventory`, `flood-hazard`, `flood-coverage`) |
| `accessed_utc` | `2026-11-02T12:00:00Z` |
| `effective_date` | NULL — unknown |
| `horizontal_accuracy_m` | NULL — unknown |
| `native_resolution_m` | NULL — unknown |
| `boundary_basis` | `synthetic fixture; not a surveyed boundary` |
| `license_note` | `synthetic example data; no real property is represented` |

The NULLs are deliberate: a real source register records what is *not*
known about a dataset (effective date, accuracy, resolution) instead of
inventing it. The `example.org` URLs are placeholders marking the fixture
as synthetic; they are not real data sources.

## The numbers — and how they were derived

Every figure is **computed from the geometries** (shapely polygon
intersection), not typed in: `overlap = area(parcel ∩ constraint)`,
`overlap_pct = overlap / parcel_area × 100`,
`coverage_pct = area(parcel ∩ coverage extent) / parcel_area × 100`.
`verify_parcel_screening.py` recomputes all of them from the stored
GeoPackage geometries and compares them with the stored attributes.

### Fixture parcels (reproduced exactly from the live site fixture)

| Parcel | Wetland overlap | Wetland coverage | Flood overlap | Flood coverage | Reading |
|---|---|---|---|---|---|
| DEMO-P1 | 5,000 m² / 50% | 100% | 0 m² / 0% | 100% | Half the parcel is mapped wetland; flood hazard none mapped *and fully covered*, so "no flood overlap" is a mapped result, not a gap. |
| DEMO-P2 | 0 m² / 0% | 0% | 2,500 m² / 25% | 50% | Wetland status **unknown** for all 10,000 m² (no inventory coverage); flood hazard covers 25% of the parcel, with 5,000 m² of the parcel unmapped for flood. |

### Additional parcels (DEMO-P3…P6 — same method, varied cases)

| Parcel | Wetland overlap | Wetland coverage | Flood overlap | Flood coverage | Reading |
|---|---|---|---|---|---|
| DEMO-P3 | 5,000 m² / 50% | 100% | 0 m² / 0% | 0% | Wetland indicator covers the southern half; flood status **unknown** for the whole parcel. |
| DEMO-P4 | 2,500 m² / 25% | 50% | 2,500 m² / 25% | 100% | Partial coverage on both: wetland indicator is a quarter of the parcel inside the mapped northern half; flood hazard is a quarter (southern strip) inside full flood coverage. |
| DEMO-P5 | 0 m² / 0% | 0% | 0 m² / 0% | 50% | No wetland coverage (unknown); flood hazard none mapped inside the mapped eastern half. |
| DEMO-P6 | 10,000 m² / 100% | 100% | 2,500 m² / 25% | 100% | Fully mapped on both: wetland indicator covers the whole parcel; flood hazard covers a quarter. |

The point of the six cases: overlap without coverage is misleading. P1's
0% flood overlap is trustworthy (100% coverage); P3's 0% flood overlap is
not a finding at all (0% coverage). A screening report must always show
both numbers side by side, and state the unknown area
(`parcel_area − coverage`) explicitly.

### Wetland coverage — a note on derivation

The required layer list has a `flood_coverage` layer but no
`wetland_coverage` layer, so wetland coverage is carried as the
`wetland_coverage_pct` attribute, computed from the inventory's mapped
extent per parcel: full parcel (P1, P3, P6), northern half of P4
(500300,3200050)–(500400,3200100), and no extent at all (P2, P5). The
extents are listed in `build_parcel_screening.py`
(`WETLAND_COVERAGE_EXTENTS`) and the verification script checks the
wetland overlap figures against the stored `wetland_indicator` geometry;
the coverage extents are documented here rather than silently embedded.

## How to open in QGIS

1. **Layer → Add Layer → Add Vector Layer…** (or drag-and-drop the file
   onto the map canvas), select `parcel_screening.gpkg`.
2. QGIS lists five layers: `parcels`, `wetland_indicator`, `flood_hazard`,
   `flood_coverage`, and the non-spatial `source_register` table (open it
   via **Layer → Add Layer → Add Vector Layer…**, or right-click →
   **Open Attribute Table**).
3. The project CRS is EPSG:32617, so the layers draw in metres on the
   500000 / 3200000 grid with no reprojection. For a basemap, QGIS will
   reproject on the fly — the parcels sit on open ocean off West Africa
   in real-world coordinates, which is expected: the grid is a synthetic
   fixture, not a real place.
4. Suggested styling: `parcels` — hollow outline, labelled by
   `parcel_id`; `wetland_indicator` — blue-green fill; `flood_hazard` —
   blue fill; `flood_coverage` — pale blue outline only (it is an extent,
   not a hazard).
5. To reproduce the table: **Vector → Geoprocessing Tools → Intersection**
   (`parcels` × `wetland_indicator` / `flood_hazard` / `flood_coverage`),
   then **Field Calculator** `$area` on the results and compare with the
   `wetland_overlap_m2` / `flood_overlap_m2` attributes — they should
   agree exactly (see Verification below).

## GeoJSON note

`parcel_screening.geojson` carries the same six parcels with identical
attributes, in the same EPSG:32617 metre coordinates, so the web-map
demonstrator can reuse it without re-deriving anything. Most web maps
display WGS 84 (lon/lat): reproject the coordinates to EPSG:4326 at
display time (e.g. `ogr2ogr -t_srs EPSG:4326` or the map library's
reprojection) — do not relabel the metre coordinates as lon/lat.

## Rebuild / verify

```bash
cd ~/workspace/commercial/demonstrators/parcel-screening
python3 build_parcel_screening.py    # regenerates .gpkg + .geojson
python3 verify_parcel_screening.py   # read-back check; exit 0 = all green
```

Build tooling: Python 3.12, geopandas 1.2.0 / pyogrio 0.13.0 / shapely
2.2.0 (user-local `pip install --user`, no system-wide install). The
verification script re-reads the written files with geopandas (layers,
row counts, CRS) and sqlite3 (`source_register`), recomputes every
overlap/coverage figure from the stored geometries, checks the DEMO-P1 /
DEMO-P2 fixture numbers and bounds exactly, and confirms the GeoJSON
parcel attributes are identical to the GeoPackage's. Last run: all
checks passed (see `verify_parcel_screening.py` output — 6 parcels,
4 wetland-indicator, 3 flood-hazard, 5 flood-coverage rows, 4
source-register rows, all EPSG:32617).

## Limits of this demonstrator

- Synthetic fixture only. It shows the *method* (overlap + coverage,
  source register, reproducible derivation) — it is not evidence about
  any real parcel, wetland, or flood zone.
- No survey, engineering, or regulatory determination is made or implied.
- Coverage extents here are invented; with real data they would come from
  the source inventory's own extent/metadata, and the register's NULL
  accuracy/resolution/effective-date fields would be filled from that
  source — or left NULL and flagged, never guessed.
