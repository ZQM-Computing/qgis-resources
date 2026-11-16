# Rank 1: environmental constraint parcel atlas

**Synthetic desktop/database demonstration only.** Not a field wetland
delineation, jurisdictional determination, Phase I ESA, boundary survey,
engineering opinion, permit approval or professional certification. This is
evidence of a reproducible GIS capability, not a completed client project.

This implementation turns the existing GeoPandas Rank 1 handoff into a
landscape Letter figure series: one parcel per PDF page, a detail map, an
overview with a linked extent rectangle, dynamic screening summaries,
source dates, a filtered legend, a metre scale bar and a grid-north arrow.
Coverage gaps are hatched **above** indicator fills, so one source's mapped
features cannot hide another source's unknown area.

## Buyer-facing scope and acceptance evidence

For a non-technical consulting reviewer, start with the
[synthetic Atlas handoff example](BUYER_HANDOFF_SAMPLE.md). It spells out the
fictional figure request, expected parcel findings, the generated output
inventory and an eight-point acceptance review. The
[client figure-set scope template](../docs/ENVIRONMENTAL_GIS_BRIEF_TEMPLATE.md)
records data rights, source coverage, map formats, reviewing professional,
QA, change requests and the factors needed for a written quote.

These are **templates and expected fixture outputs**, not a pre-rendered
download, proven client engagement, set price or delivery-time promise. The
following runtime commands and tests remain the source of implementation
evidence.

## Quickstart

Requires QGIS with Python bindings, DejaVu Sans fonts, and Poppler's
`pdfinfo`/`pdftotext`. Tested locally on Linux with **QGIS 3.40.6**, GDAL
3.10.3 and the included two-parcel synthetic fixture. The CI runtime job
installs its own QGIS package and must pass on each proposed revision.
Other desktop versions/platforms and representative client data need review.

Run from the repository root in a QGIS Python environment. On Linux:

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python3 exhibit-production/parcel_atlas.py \
  exhibit-production/fixtures/geopandas-handoff \
  /tmp/rank1-atlas-review --date 2026-11-14
```

The destination must be new and outside the source handoff directory, including
through symlink aliases. Overlapping paths are rejected before staging or
creating destination directories. Use a new revision directory for a rerun;
the script refuses overwrite. The explicit `--date` drives labels, filenames
and the manifest together. The PDF's embedded creation timestamp still
reflects export time; byte-identical PDF/project output is not promised.

Run actual rendering and failure tests:

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover \
  -s tests -p test_parcel_atlas_runtime.py -v
```

## Input contract and upstream handoff

Use the complete flat output of GeoPandas
[`exhibit_prep.py`](https://github.com/ZQM-Computing/geopandas-cookbook/blob/f91ca285cc89f77773776327c6c9547248695de7/examples/12-environmental-screening/exhibit_prep.py).
The [fixture provenance](fixtures/README.md) records the producer revision
and regeneration commands. The fixture is committed so the QGIS tests need
no network or GeoPandas installation.

| Input | Purpose |
| --- | --- |
| `exhibit_manifest.json` | Synthetic handoff v1, CRS, seven-file inventory, sizes and SHA-256 hashes |
| `parcel_screening.gpkg` | `parcels`, optional positive-area `known_overlaps` and `source_coverage` layers |
| `parcel_constraints.csv` | Long parcel × constraint matrix; values must match the JSON report |
| `parcel_screening.json` | Screening rows, validated source register and methodology |
| `source_register.json` | Exact source-register snapshot matching the report |
| `manifest.json`, `parcel_review_map.png`, `LIMITATIONS.txt` | Preserved original bundle evidence and limitations |

Supported constraint types are `wetland_inventory` and `flood_hazard`.
Every parcel needs exactly one row for each. IDs must reconcile to unique
`parcels.parcel_id` values. The long matrix is pivoted to per-parcel layout
attributes; the original rows and geometries remain unchanged.

All layers must already share the handoff's valid **projected metre CRS**.
The supplied fixture uses EPSG:32617. The script verifies polygon validity,
positive area, IDs, geometry containment, measured coverage/overlap areas,
percentages, and status consistency before export. An absent optional layer
is acceptable only when the matrix and geometry checks support zero emitted
positive-area geometry; absence never establishes a negative finding.

The upstream synthetic register has no publisher field and unknown effective
dates, horizontal accuracy and native resolution. These stay unknown; the
script does not invent them. Synthetic source URLs are provenance labels,
not live downloads. A real project needs an independently reviewed register
including publisher, license, effective date, retrieval date, accuracy,
coverage and limitations before adapting this example. Checksums verify
byte consistency, not authenticity, source accuracy or professional approval.

For PostGIS EPSG:2236 outputs, first transform actual coordinates to the
selected metre CRS and regenerate/reconcile the producer's area fields and
handoff. EPSG:2236 is NAD83 / Florida East in **US survey feet**. Merely
changing the CRS label or mixing square feet and square metres is invalid.
The current adapter does not import PostGIS tables directly.

## Outputs and expected results

| Output | Contents |
| --- | --- |
| `Env_Constraints_Parcel_Atlas.qgz` | Portable QGIS project, five styled layers, one enabled atlas layout |
| `Env_Constraints_Parcel_Atlas.qpt` | Actual QGIS-generated XML layout template with relative layer references |
| `atlas_data.gpkg` | Parcel attributes, two indicator layers and two derived coverage-gap layers |
| `EnvConstraints_Atlas.pdf` | Single two-page Letter landscape PDF for the supplied fixture |
| `delivery_manifest.csv` | Page, filename, parcel ID, flags/statuses, CRS, generation date, source-register snapshot/hash |
| `source_register.json`, `source_handoff/` | Unchanged provenance and complete original handoff |
| `atlas_run.json` | QGIS version, parameters, input-manifest hash, output inventory/checksums and limitations |

| Parcel | Wetland result | Flood result | Data gap |
| --- | --- | --- | --- |
| DEMO-P1 | Mapped overlap: 50%; coverage: 100% | No mapped intersection; coverage: 100% | No |
| DEMO-P2 | No source coverage; unknown | Known overlap: 25%; coverage: 50%; remainder unknown | Yes |

Known-overlap percentages use the **whole parcel** denominator. They do not
estimate unknown areas. A full-coverage no-mapped-intersection result is not
proof that a real constraint is absent. The exhibit uses a neutral background
and explicitly says no imagery basemap; synthetic coordinates do not imply
a real site or surveyed boundary.

The default includes every parcel. Optional `--findings-only` uses
`"has_indicator" = 1 OR "has_data_gap" = 1`, retaining gap-only parcels.
A filter that produces no pages is rejected. Negative-result parcels are
otherwise omitted only by that explicit option; disclose the omission in
the delivery scope. Review the requested parcel inventory before delivery.

## Configure or reuse the layout in QGIS

1. Open the generated `.qgz` with its companion `atlas_data.gpkg` in the same
   directory. Keep the full directory together when moving it.
2. Open **Project → Layouts → Env_Constraints_Parcel_Atlas**. The single
   physical layout page is Letter landscape, 279.4 × 215.9 mm. Confirm
   the client's paper size and typography before adapting it.
3. In the **Atlas** panel, enable **Generate an atlas**, use **Parcel
   outlines** as coverage, use `'Parcel ' || "parcel_id"` for page name,
   and sort ascending by `"parcel_id"`. Default filtering is off.
4. Select `main_map`. **Controlled by atlas** uses automatic scale with
   15% margin. A client-required fixed scale must be large enough to
   contain every parcel plus context; inspect for clipping page by page.
5. Select **`inset_map`**, open **Overviews**, and link **Main map extent**
   to **`main_map`**. The extent rectangle is configured on the map that
   displays it: the inset. The inset uses a fixed study-wide extent.
6. Both map items lock their layer sets/styles, and the legend is linked
   to the main map with map filtering enabled. Parcel labels identify
   neighboring context; the summaries refer to the titled parcel only.
7. Use **Atlas → Preview Atlas** and inspect every feature. The arrow
   means grid north with zero map rotation. If rotation changes, replace
   it with a map-linked north arrow and update the north reference.
8. Use **Atlas → Export Atlas as PDF**, with **Single file export when
   possible** enabled for a map book. Reconcile the reviewed export to
   the page manifest; GUI edits/exports do not automatically regenerate it.

The `.qpt` is a supported layout template, not a standalone project. Open
the matching `.qgz` first when importing it. With unrelated project layers,
reselect coverage, maps' layers and item links. Do not hand-author presumed
QGIS XML element schemas: let the installed QGIS version serialize them.
See the [item and XML structure notes](LAYOUT_STRUCTURE.md).

## Expressions

[expressions.json](expressions.json) is the exact reusable expression
catalog exercised by the renderer. The [expression guide](EXPRESSIONS.md)
explains fields, variables, label delimiters and filename rules.

## PDF export and delivery checks

- Use 300 dpi for rasterized content. Text/vector items retain their native
  representation when QGIS can do so. The exporter does **not** force every
  item to vector: some styles/effects need rasterization to preserve appearance.
- Geometry simplification is disabled. Any later file-size optimization
  needs spatial and visual review; never modify source boundaries to fit a PDF.
- This example exports ordinary PDF, without georeference or feature
  attributes. GeoPDF needs an explicit client request and a separate export/
  disclosure review, including layers and attributes it may expose.
- Before publishing the new output directory, Poppler reopens each page
  and verifies page count, parcel ID, date, scale, CRS, source IDs/retrieval
  dates, disclaimer and uncertainty wording. Failure removes the staged batch.
- Runtime tests also move the project, reopen its layers and XML template,
  render a page and check that coverage hatching remains visible over a
  different constraint's fill. They verify refusal/cleanup on invalid inputs,
  contradictory statuses, tampering, and existing output directories.

Before client delivery, inspect every rendered page for legibility,
source/register completeness, parcel selection, extent and scale, legend
parity, hatch visibility, publication rights and limitations. Keep the
methodology, original source register and page manifest with the maps.
No small synthetic test substitutes for professional review of real data.

## Theme and mixed series

The implemented pattern is **parcel coverage + one consistent layer set**.
For a theme series, create named map themes and bind each fixed-extent map
to its intended theme. A table/dummy coverage row per theme can drive a
data-defined theme property; it does not automatically change map visibility.
Use explicit theme names, page order, and export/manifest checks.

Atlas iterates **all physical layout pages for every coverage feature**.
Adding a summary page to this layout repeats it for every parcel; atlas
feature numbers also cease to equal physical PDF page numbers. Use a QGIS
Report with a header/detail structure, or separately assembled reviewed
summary/detail PDFs, for a summary printed only once. These advanced modes
are guidance, not implemented or tested by this parcel example.

## QGIS references

- [Map items: atlas control, layers and overviews](https://docs.qgis.org/3.40/en/docs/user_manual/print_composer/composer_items/composer_map.html)
- [Atlas configuration, expression labels and PDF export](https://docs.qgis.org/3.40/en/docs/user_manual/print_composer/create_output.html)
- [Cartography processing algorithms](https://docs.qgis.org/3.40/en/docs/user_manual/processing_algs/qgis/cartography.html)

The implementation targets the tested QGIS 3.40 API baseline. Consult your
installed version's manual for UI differences and current support status.
