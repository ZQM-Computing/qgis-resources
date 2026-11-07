# Utility corridor proximity screening — synthetic P0

**Status:** review-only proof of concept. This is not a utility clearance inspection, vegetation growth model, wildfire risk assessment, engineering certificate, or cost-savings claim.

## What the prototype actually measures

The headless `scripts/utility_corridor_screening.py` uses GDAL/OGR to measure **horizontal 2D distances** between synthetic LineString utility assets and Polygon vegetation footprints in the declared **EPSG:32617 (UTM zone 17N)** plane. This CRS is deliberately restricted to a pilot region; it is not a globally applicable distance engine.

An example fixture in `fixtures/utility-corridor-synthetic.json` contains two fictional line assets and two fictional vegetation polygons. The first line is 10 projected metres from a vegetation polygon, under the arbitrary **25 m screening threshold**. This threshold is **not an approved engineering clearance or a right-of-way clearance rule**. It exists solely for functional testing.

Results distinguish `SCREEN_FOR_INSPECTION` from `NO_NEARBY_MAPPED_GEOMETRY_NOT_CLEARANCE`. Any candidate produces overall `REVIEW`; no candidates produce `INSUFFICIENT_EVIDENCE`, not an all-clear verdict. Dates are fixture assertions, not independently verified imagery dates.

## Reproducible run

With GDAL Python bindings (same interpreter as QGIS runtime):

```bash
/usr/bin/python3 -m unittest discover -s tests -p 'test_utility_corridor_screening.py' -v
/usr/bin/python3 scripts/utility_corridor_screening.py fixtures/utility-corridor-synthetic.json
```

The code is read-only, uses no network or cloud infrastructure, accepts only bounded synthetic JSON and never generates work orders. The full QGIS runtime workflow executes the GDAL test suite; general CI skips the GDAL-specific tests if those bindings are absent, while still compiling and checking other repository tests. Existing required security scans remain unchanged.

## Measurement and audit limits

- A simple OGR planar distance from a 2D synthetic centerline to polygon is not the shortest distance from a conductor to a 3D tree canopy. It does not account for height, sag, wind, lean, conductor temperature, elevation or measured vegetation growth.
- GIS source authenticity, geographic accuracy, survey methods, acquisition time and spatial completeness are **not established** by a valid JSON fixture or by a projected coordinate reference.
- The input is bounded: at most 100 assets, 1000 polygons, 1 MiB JSON, projected coordinate range and positive threshold at most 100 m. Invalid topology, unsupported CRS, incomplete arrays, duplicates, non-finite coordinates and unreviewed authorizations fail closed.
- No probability of wildfire, required trimming cycle, customer savings, monetary liability, legal right-of-way boundary, safety certification, regulated work order or utility capital decision is inferred.
- The actual on-the-ground priority requires a qualified utility vegetation-management reviewer, current asset surveys, relevant NERC FAC-003 applicability (where relevant) and local utility clearance practices.

## Product extraction sequence

1. Review synthetic algorithm correctness, units and failure modes against QGIS/GDAL runtime tests.
2. Validate data rights and provenance for a lawful utility/contractor pilot, with confidential data kept outside public fixtures.
3. Integrate surveyed 3D conductor/vegetation geometry when licensed; independently benchmark accuracy against field-confirmed observations.
4. Build inspection-priority recommendations with explicit uncertainty, false-positive/false-negative metrics and geographic limitations.
5. Calculate buyer-specific ROI only from measured baseline inspection hours, work orders, contractor expenses and verified outcomes. Test a **paid** pilot before buying imagery subscriptions.

This is a **separate application of the Spatial Risk-to-Capital architecture**, not a replacement for the land feasibility core (#40) or the EUDR preflight (#42). Keep the three domains in separate rule packs until shared contracts and source provenance are validated.
