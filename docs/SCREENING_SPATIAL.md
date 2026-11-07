# Synthetic polygon screening with GDAL/OGR (P0-A2)

**Status: review-only synthetic prototype.** Actual polygon union and clipped-area calculations are implemented, but no customer dataset, worldwide source adapter, certified regulatory opinion, published map, or production service is provided.

## Execution

    /usr/bin/python3 scripts/screening_spatial.py fixtures/screening-manifest.json
    /usr/bin/python3 scripts/validate_screening_spatial_runtime.py

The QGIS runtime workflow installs GDAL/OGR and executes the integration assertions against synthetic GeoJSON. The first command writes **only to standard output**; redirect the JSON if you wish to inspect it. Neither the manifest nor the referenced data files are modified.

## Measurement contract

- All accepted source geometry is explicitly declared EPSG:4326 and must have the same CRS in the GeoJSON metadata. Missing or mismatched CRS fails, never inferred.
- GeoJSON fixtures must be under the repository fixtures/ tree, with read-only opens. This pilot does not fetch external URL sources or process arbitrary local customer paths.
- Only valid, nonempty Polygon/MultiPolygon geometry is accepted. The input is bounded to 10,000 features per file, less than five degrees per geometry, latitude within -80 to 80 degrees, and longitude within -170 to 170 degrees. These are current pilot constraints, not global operating limits.
- Geometry is transformed with GIS-ordered coordinates into EPSG:6933 (WGS 84 / NSIDC EASE-Grid 2.0 Global, equal-area), measured in square metres, unioned per layer, and clipped against the dissolved area of interest. Double-counted overlaps must not inflate area.
- The synthetic study AOI is 0–2 longitude by 0–2 latitude; source 1 intersects the AOI at 1–2 longitude, 1–2 latitude. A second partly overlapping polygon lies wholly within the first AOI intersection. Expected result: approximately 12,304,814,950 square metres of synthetic intersection from 49,226,557,688 square metres of synthetic study area, or 24.996294 percent (measured projected area).
- The QGIS runtime suite now also computes an **independent analytic WGS84 ellipsoid surface-area integral** for the known rectangular synthetic AOI (0–2° longitude, 0–2° latitude) and intersected square (1–2° longitude, 1–2° latitude). The projected GDAL outputs must agree with this independent reference within `1e-8` relative tolerance. This specifically validates fixture measurement consistency; it is **not** a general geodesic algorithm for arbitrary parcel polygons, buffering, or survey accuracy.
- For a *verified* synthetic source with no mapped overlap, the result is `synthetic-no-mapped-overlap-not-a-clearance`, never `unconstrained`. For partial coverage, use `partial-source-measured-not-comprehensive`. For missing/unverified/unavailable or external unprocessed sources, measured values are null; no spatial absence inference may be made.
- All results state `input_geometry=synthetic-only`, `human_review=pending`, and `regulatory_determination=false`. Verified in the source manifest means an internal test-data coverage assertion, not verified legal, ecological, or jurisdictional completeness.

## Explicit exclusions and next gates

Regulatory buffers, setbacks, wetlands delineation, flood hazard determinations, parcel boundary certification, professional signoff, uncertainty calibration, geodesic area comparison, antimeridian coverage, and global CRS selection are **not implemented**. Source licensing and provenance metadata still require independent checking outside synthetic fixtures.

Next: (1) evidence-reviewed map package/report with explicit no-data layers and legends; (2) safely staged output artifacts and reproducible run manifest; (3) Florida/US public-data adapters and a non-US lawful-data pilot; (4) specialist review and measured pilot delivery cost. No customer publication or deployment without separate authorization.

Related: [metadata contract](SCREENING_MANIFEST.md), [QGIS contracts](WORKFLOW_CONTRACTS.md), [P0 issue](https://github.com/ZQM-Computing/qgis-resources/issues/39).
