# Synthetic GIS figure-set handoff — buyer-readable example

**Status: reproducible example specification; not a client deliverable or
a pre-generated PDF download.** Every property, source and scenario is
synthetic. The [parcel Atlas workflow](README.md) has tests and a
runtime recipe, but this page is not evidence of a signed order, client review
or successful execution on a new machine. Its purpose is to make the
scope and acceptance requirements understandable without running QGIS.

## Illustrative request

A fictional environmental consulting team requests **one landscape
US Letter figure per parcel** for a two-parcel desktop screening exhibit.
They will interpret the source limitations, review the maps and control
any real regulatory submission. The figure set uses only the repository's
two-parcel synthetic fixture, not agency data or client locations.

| Scope item | Illustrative agreed value |
| --- | --- |
| Purpose | Preliminary screening exhibit practice, not parcel clearance |
| Study IDs | DEMO-P1 and DEMO-P2 (synthetic, 10,000 m² each) |
| Output | Single two-page PDF and associated QGIS project/QA manifest |
| Layout | US Letter landscape; detail map, extent inset, sources, legend, scale |
| Source themes | `wetland_inventory` and `flood_hazard` in the fixture |
| CRS/units | EPSG:32617, projected metres; no real-world location claim |
| Source evidence | Fixture source register; simulated access time; unknown real accuracy and effective dates |
| Review | Inspect each page, reconcile parcel IDs and map findings; document exceptions |
| Commercial terms | None. The sample is not an estimate, fixed price or delivery promise |

The coverage and overlap percentages here derive from committed
[fixture results](fixtures/geopandas-handoff/parcel_screening.json).
See the [fixture provenance](fixtures/README.md) and
[complete input contract](README.md#input-contract-and-upstream-handoff).

## Expected result by parcel

| Parcel | Wetland indicator | Flood indicator | Required map annotation |
| --- | --- | --- | --- |
| DEMO-P1 | 50% known mapped overlap, 100% source coverage | 0% known mapped overlap, 100% source coverage | No mapped flood intersection **within this complete synthetic coverage** |
| DEMO-P2 | Coverage absent: **unknown**, not clear | 25% known overlap; 50% of parcel covered | Both wetland unknown and flood partial coverage visibly flagged |

The percentages use each whole parcel as the denominator. Unknown area is
not assumed negative and cannot be inferred as an observed boundary or
actual environmental condition.

## Reproduce the demonstration

From a clean checkout with QGIS bindings, fonts and Poppler available,
follow the exact [Quickstart](README.md#quickstart):

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python3 exhibit-production/parcel_atlas.py \
  exhibit-production/fixtures/geopandas-handoff \
  /tmp/rank1-atlas-review --date 2026-11-14
```

Use a **new, unused output directory** outside the source fixture. The
`--date` above is an example rendering label, not a real data-retrieval date.
No QGIS installation or execution is implied by simply reading this page.

Expected outputs include `EnvConstraints_Atlas.pdf`,
`Env_Constraints_Parcel_Atlas.qgz`, the matching `.qpt`,
`atlas_data.gpkg`, `delivery_manifest.csv`, `source_register.json`,
`source_handoff/` and `atlas_run.json`.
The [technical output inventory](README.md#outputs-and-expected-results)
lists their intended contents and validation requirements.

## What a reviewer actually checks

1. **Page and figure register:** exactly two PDF pages and two unique parcel
   IDs. The PDF parcel order agrees with `delivery_manifest.csv`.
2. **Source transparency:** both themes appear in the source register;
   its unknown effective dates/accuracy are not fabricated.
3. **CRS and area:** units and geometry are EPSG:32617/metres, not assumed
   Florida State Plane feet. Area fields and known-overlap percentages
   reconcile to the fixture.
4. **Partial or absent coverage:** DEMO-P2 retains wetland "no source
   coverage" and flood "partial source coverage"; unknown stays visible
   even where a mapped indicator fill appears.
5. **File integrity:** generated files open; the project works when moved
   with its companion data; `atlas_run.json` matches output checksums.
6. **Presentation:** legible source dates, uncertainty flags, selected
   parcel ID, scale bar, extent, legend, north reference and disclaimers.
7. **Exceptions:** if any source/figure check fails, stop delivery and
   record the discrepancy for remediation, rather than overriding QA.
8. **Approval boundary:** the consulting reviewer controls interpretation
   and any professional or regulatory signoff.

The existing [QGIS runtime tests](../tests/test_parcel_atlas_runtime.py)
assert the relevant mechanical outputs and critical failure paths. Visual
inspection and professional review remain required for actual deliveries.

## Example disposition (synthetic illustration)

- **Input:** two parcel IDs, four parcel-constraint rows, two source themes.
- **Expected:** a two-page Atlas; DEMO-P1 has known wetland overlap;
  DEMO-P2 includes unknown wetland source coverage and partial flood coverage.
- **Known limitations:** fictional coordinates/sources; no licensing or
  authority to represent real wetlands/flood zones; no field verification.
- **Buyer approval:** not sought; no actual project acceptance recorded.
- **Pricing or turnaround:** not established by this example.

Adapt the
[client figure-set brief and acceptance worksheet](../docs/ENVIRONMENTAL_GIS_BRIEF_TEMPLATE.md)
for a real discussion. Do not substitute this synthetic example for a
certified survey, field delineation, jurisdictional determination, Phase I
ESA, engineering opinion, permit decision or client project record.
