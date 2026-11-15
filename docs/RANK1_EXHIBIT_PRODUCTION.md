# Rank 1: QGIS environmental GIS exhibit production review notes

**Synthetic desktop GIS demonstration only. Not a field wetland delineation,
jurisdictional determination, Phase I environmental site assessment (ESA),
boundary survey, engineering opinion, permit approval or professional
certification.** This describes a review workflow and its linked synthetic
implementation, not evidence of client delivery. Real maps require current
source records, professional review and appropriate regulatory interpretation.

## Where this fits

ZQM Computing's Rank 1 buyer is an environmental or engineering consultancy
seeking outsourced map/figure production and GIS preparation. The primary
technical demonstrations are:

- [PostGIS Pattern 08](https://github.com/ZQM-Computing/postgis-cookbook/pull/47):
  synthetic parcel × wetland/flood indicators, source coverage, source/date
  register, projected-area arithmetic, QA and data-gap flags.
- [GeoPandas exhibit handoff](https://github.com/ZQM-Computing/geopandas-cookbook/pull/48):
  synthetic CSV matrix, GeoPackage, review image, source register and
  checksum/limitations artifacts.
- [GDAL prep](https://github.com/ZQM-Computing/gdal-cookbook/pull/43):
  synthetic source clip/reprojection before final figure production.

These links are documentation references, **not** proof that an automated,
tested, cross-repository pipeline or a complete permit exhibit exists.

## QGIS handoff and map-series workflow

The [parcel atlas implementation](../exhibit-production/README.md) provides
the executable downstream example, exact expressions, layout structure,
portable `.qgz`/`.qpt`, PDF and page manifest. The original review checklist
below still applies when adapting the layout or reviewing real source data.

1. **Input intake and provenance.** Record filename, delivery batch, owner/
   permitted use, dataset name and publisher, retrieval/effective date (or
   unknown), version/URL, geometry type, source CRS, metadata license,
   limitations and source coverage footprint. Keep all example inputs synthetic.
2. **Validate before layout.** Inspect all geometries for null, empty,
   invalid or duplicates; check parcel IDs, layer feature counts and mapping
   extent. Reconcile the GeoPandas `parcel_constraints.csv` with the
   GeoPackage `parcels`, `known_overlaps` and `source_coverage`
   layers; do not interpret an absent positive-geometry layer as
   "no environmental constraint".
3. **Choose CRS deliberately.** The GeoPandas synthetic fixture uses
   **EPSG:32617 (metres)**, with 4,046.8564224 m²/acre. The PostGIS
   example uses **EPSG:2236 (US survey feet)**, with 43,560 ft²/acre.
   Transform coordinates when combining layers; never merely assign a
   new CRS label or mix feet and metres.
4. **Map series by reviewed parcel ID.** Create one QGIS Print Layout
   page per synthetic parcel, with stable figure ID, title, legend,
   scale bar, source/dataset attribution, map date, project CRS,
   north arrow where applicable, and a visible **synthetic desktop
   screening only** disclaimer. Use a layout atlas only after checking
   selected parcel IDs and layout filters.
5. **Differentiate uncertainty visually.** Show explicit mapped indicators,
   documented source coverage, and areas with no available source
   coverage using separate symbology. The source table may report
   `partial_source_coverage` or `no_source_coverage` even if an
   overlay layer contains no geometry. Never display that as "clear".
6. **QA every figure.** Check layer/legend parity; titles, date and scale;
   source provenance; boundary slivers; missing input IDs; blank/extreme
   extents; unexpected visibility; source limitations and publication
   rights. Track all review findings and revisions.
7. **Export and inspect.** Export to a scoped destination (PDF/PNG as
   agreed) only after client review of draft layouts. Reopen outputs,
   verify expected page count and maps, and reconcile the file inventory
   with the source register and figure index. Do not overwrite an
   existing known-good deliverable without an approved revision process.

## Proposed figure register

| Field | Requirement |
| --- | --- |
| `figure_id` | Stable unique ID (e.g. SYN-FIG-001) |
| `parcel_id` | Reconciles to source screening matrix |
| `source_register_ref` | Dataset/publisher/retrieval date/version/URL |
| `input_crs / output_crs` | CRS and units recorded explicitly |
| `coverage_status` | Full, partial, absent or unknown |
| `data_gap_flag` | Reviewed, never suppressed |
| `revision` | Figure version, responsible reviewer, date |
| `limitations_notice` | Synthetic/desktop-only regulatory disclaimer |

## Acceptance before calling an exhibit production example runtime-proven

- [x] A QGIS-enabled test uses synthetic source GeoPackages and CSVs.
- [x] It proves per-parcel page counts, visible layers and source labels.
- [x] It verifies actual output files by reopening the PDF through Poppler
      and rendering QGIS map/layout images; both example pages were visually reviewed locally.
- [x] It rejects missing source registers, bad CRS and contradictory
      data gaps instead of silently producing reassuring maps.
- [ ] A qualified human confirms any real jurisdiction-specific
      interpretation; no cookbook claims permit or survey authority.

**Status:** This page remains the review checklist. The linked parcel-atlas
implementation was executed on Linux with QGIS 3.40.6 using the committed
GeoPandas synthetic handoff. Automated tests check the two-page PDF,
source/uncertainty labels, relocated project/template, visible gap hatching,
input rejection, output preservation and cleanup. This is headless runtime
evidence; it does not establish GUI usability on every desktop, source
authority, regulatory certification, or real client work. Exact-head CI and
representative-data review remain separate gates.
