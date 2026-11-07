# Florida public-source inspection pilot (P0-A4)

**Status:** source-discovery and read-only bounded ingestion prototype, not commercial coverage verification or a usable parcel screening engine. This work is stacked on the synthetic screening PR #40 and does not modify the existing product's delivery approval state.

## Grounded official sources

- [USFWS NWI web mapping services](https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services) publish a REST endpoint for Wetlands. On November 7, 2026, its publicly exposed ArcGIS REST metadata identified layer 0 as `Wetlands`, polygon features, `OBJECTID`, `ATTRIBUTE`, `WETLAND_TYPE`, GeoJSON query support, pagination, and a maximum 500 returned records per request. These are **service metadata observations**, not a successful live feature-download claim.
- [USFWS Wetlands Mapper](https://www.fws.gov/program/national-wetlands-inventory/wetlands-mapper) says the mapped inventory uses a biological wetland definition and does **not** establish the scope of regulatory jurisdiction, wetland absence or legally protected boundaries. [Download guidance](https://www.fws.gov/program/national-wetlands-inventory/data-download) recommends consulting source publication dates and cautions, and provides state/watershed downloads for analysis.
- [Florida Geospatial Open Data Portal](https://geodata.floridagio.gov/) advertises 2026 statewide parcel data with over 10.9 million records across Florida's 67 counties. The portal's general availability is **not** a verified specific-layer URL, parcel-boundary accuracy, survey, or license review for commercial redistribution.
- [Florida DEP GIS](https://floridadep.gov/otis/enterprise-application-services/gis) provides an official open-data portal and mapping tools. The [DEP ArcGIS service catalog](https://ags.dep.state.fl.us/arcgis/rest/services/OpenData) lists potential source categories, but no environmental layer has yet passed a scope, edition, license and completeness review for this pilot.

The machine-readable [candidate-source register](../sources/florida-public-candidates.json) keeps `commercial_use_approved=false` and `licensing_review=pending` for every candidate. **Do not flip these fields solely because an endpoint is publicly accessible.**

## Use the read-only NWI adapter

Safe default (does not send any request and exits 2):

    python scripts/nwi_source_inspector.py --bbox -82.01 27.71 -82.00 27.72 --out /tmp/nwi-inspection.json

Explicitly opt in to a small public read-only request:

    python scripts/nwi_source_inspector.py --bbox -82.01 27.71 -82.00 27.72 --out /tmp/nwi-inspection.json --network

Sample coordinates define an arbitrary small test envelope and are **not a customer's parcel**. The adapter allows only official USFWS NWI layer 0 HTTPS endpoints, blocks HTTP redirects, bounds each response to 4 MiB, caps a Florida envelope at 0.02 degrees in each direction and limits returned features to 200. It first verifies layer capability/schema and obtains the server's count, then requests GeoJSON with stable `OBJECTID` pagination, reconciles counts and rejects truncated/invalid/duplicate records. If the server returns too many features or is inaccessible, the request **fails closed**; it does not declare no constraint.

Source results carry `coverage_state=unverified`, `reuse_rights=unverified`, `human_review=pending`, and `regulatory_determination=false`, including when the query returns zero features. The adapter filters source attributes to an allowlist, records the provider URL, retrieval time, bounding box and requested CRS, and atomically creates one non-overwriting JSON snapshot. Its output **does not** feed the customer report or assert legal rights. The CLI produces no network request unless `--network` is explicitly supplied.

Tests run with a mocked provider response, never a live public endpoint:

    python -m pytest -q tests/test_nwi_source_inspector.py

## Release gates not yet met

1. Confirm actual successful live feature retrieval, service output CRS and full paging for the selected envelope; record redacted request/response evidence, retrieval UTC and hashes.
2. Verify geographic coverage and gaps independently using official NWI project/update metadata. An empty result or a 200-feature limit is not proof of completeness.
3. Perform a written rights review for client reuse, redistribution and derivatives; public query access alone is not approval.
4. Identify and review the specific Florida 2026 parcel dataset feature service, fields, map vintage, boundary accuracy, rights and jurisdiction.
5. Integrate bounded, reviewed snapshots with the actual QGIS/GDAL area engine, using separately validated CRS, validity, topology, measurement units and authoritative study-boundary provenance.
6. Run independent methodology and customer review and record engineering time, revision costs and willingness to pay before declaring a validated commercial product.

## No unauthorized transition to production

Nothing in this adapter initiates commercial orders, sends client emails, deploys services, accesses private customer files or changes the approved synthetic-only report pipeline. Humans retain authorization over publication, licensing decisions and client-facing claims.

Related: [product issue #39](https://github.com/ZQM-Computing/qgis-resources/issues/39), [synthetic PR #40](https://github.com/ZQM-Computing/qgis-resources/pull/40), [synthetic evidence bundle](SCREENING_REPORT.md).
