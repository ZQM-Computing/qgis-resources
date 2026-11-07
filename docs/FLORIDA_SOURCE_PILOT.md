# Florida public-source inspection pilot (P0-A4)

**Status:** source-discovery and read-only bounded ingestion prototype, not commercial coverage verification or a usable parcel screening engine. The synthetic screening core from PR #40 is merged, but this source adapter remains **unapproved for live or commercial use** and does not modify any delivery approval state.

## Grounded official sources

- [USFWS NWI web mapping services](https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services) publish a REST endpoint for Wetlands. On November 7, 2026, its publicly exposed ArcGIS REST metadata identified layer 0 as `Wetlands`, polygon features, `OBJECTID`, `ATTRIBUTE`, `WETLAND_TYPE`, GeoJSON query support, pagination, and a maximum 500 returned records per request. The metadata also advertises `OBJECTID` as `esriFieldTypeOID`, `ATTRIBUTE` and `WETLAND_TYPE` as `esriFieldTypeString`, and `supportsOrderBy=true`; the adapter now verifies these types/capabilities before querying features. These are **service metadata observations**, not a successful live feature-download claim.
- [NWI state downloads](https://www.fws.gov/program/national-wetlands-inventory/download-state-wetlands-data) list an **October 2026 state-package posting** and include separate project-level metadata with imagery dates. The posting date is **not** evidence that a particular wetland polygon was mapped in October 2026. A real screening pipeline must associate its queried area with NWI project metadata, preserve imagery/interpretation dates and known mapping gaps, and reject unsubstantiated `current_edition` claims. The queried service layer and downloadable state package also must not be assumed to be identical without explicit comparison.
- [USFWS Wetlands Mapper](https://www.fws.gov/program/national-wetlands-inventory/wetlands-mapper) says the mapped inventory uses a biological wetland definition and does **not** establish the scope of regulatory jurisdiction, wetland absence or legally protected boundaries. [Download guidance](https://www.fws.gov/program/national-wetlands-inventory/data-download) recommends consulting source publication dates and cautions, and provides state/watershed downloads for analysis.
- [Florida Geospatial Open Data Portal](https://geodata.floridagio.gov/) advertises 2026 statewide parcel data with over 10.9 million records across Florida's 67 counties. The portal's general availability is **not** a verified specific-layer URL, parcel-boundary accuracy, survey, or license review for commercial redistribution.
- **Parcel-vintage reconciliation (November 7, 2026):** A previous search snapshot labeled the [statewide cadastral polygon layer](https://services9.arcgis.com/Gh9awoU677aKree0/ArcGIS/rest/services/Florida_Statewide_Cadastral/FeatureServer/0) as 2025, but the **current official layer** identifies a polygon layer named `CADASTRAL_DOR`, last edited October 23, 2026; [its official linked metadata](https://www.arcgis.com/sharing/rest/content/items/efa909d6b1c841d298b0a649e7f71cf2/info/metadata/metadata.xml?format=default&output=html) describes an **August 2026 polygon export**. The [separate 2026 centroid layer](https://services9.arcgis.com/Gh9awoU677aKree0/ArcGIS/rest/services/Florida_Statewide_Parcel_Centroid_Version/FeatureServer/0) is points, not parcels. The identified polygon endpoint is now a **metadata-supported 2026 candidate**, but no live parcel features, county-specific completeness or rights have been verified. Always record actual retrieved metadata, geometry type, `ASMNT_YR` and effective edition; never infer surveyed boundaries or silently mix vintage. For privacy and data minimization, a future parcel adapter should request only geometry and non-sensitive opaque identifiers, not `OWN_NAME`, owner addresses or other unnecessary tax-roll fields.
- [Florida DEP GIS](https://floridadep.gov/otis/enterprise-application-services/gis) provides an official open-data portal and mapping tools. The [DEP ArcGIS service catalog](https://ags.dep.state.fl.us/arcgis/rest/services/OpenData) lists potential source categories, but no environmental layer has yet passed a scope, edition, license and completeness review for this pilot.

The machine-readable [candidate-source register](../sources/florida-public-candidates.json) keeps `commercial_use_approved=false` and `licensing_review=pending` for every candidate. **Do not flip these fields solely because an endpoint is publicly accessible.**

## Use the read-only NWI adapter

Safe default (does not send any request and exits 2):

    python scripts/nwi_source_inspector.py --bbox -82.01 27.71 -82.00 27.72 --out /tmp/nwi-inspection.json

Explicitly opt in to a small public read-only request:

    python scripts/nwi_source_inspector.py --bbox -82.01 27.71 -82.00 27.72 --out /tmp/nwi-inspection.json --network

Sample coordinates define an arbitrary small test envelope and are **not a customer's parcel**. The adapter allows only official USFWS NWI layer 0 HTTPS endpoints, blocks HTTP redirects, bounds each response to 4 MiB, caps a Florida envelope at 0.02 degrees in each direction and limits returned features to 200. It first verifies layer capability/schema and obtains the server's count, then requests GeoJSON with stable `OBJECTID` pagination, reconciles counts and rejects truncated/invalid/duplicate records. Each returned ring must also have valid coordinate tuples, at least three distinct vertices, no immediately repeated vertices and nonzero signed planar ring area. Every provider feature must have a bounding envelope intersecting the requested box, including later pages; envelope intersection is NOT proof of actual polygon intersection. **These are elementary sanity checks, not full OGC topological validity**: self-intersections, invalid hole nesting and overlapping multipart components still require independent GDAL/OGR `IsValid()` assessment before spatial analysis or delivery. The Florida latitude/longitude guard is only a rectangular geographic envelope, not a point-in-Florida administrative boundary test. If the server returns too many features or is inaccessible, the request **fails closed**; it does not declare no constraint.

Source results carry `coverage_state=unverified`, `reuse_rights=unverified`, `human_review=pending`, and `regulatory_determination=false`, including when the query returns zero features. The result also records a SHA-256 hash of the **normalized, filtered GeoJSON**, ordered unique-object-ID checks, and the total validated vertex count. This is an internal transformation fingerprint, **not** a signature or a hash of the unmodified agency response. Because layer data may change between a count request and the individual feature pages, count/ID reconciliation **does not prove point-in-time snapshot consistency**. If the agency metadata, geometry type, CRS, page count, identifiers, mandatory attributes, or source endpoint differ from the expected contract, ingestion fails instead of silently accepting an incomplete dataset. The adapter filters source attributes to an allowlist, records the provider URL, retrieval time, bounding box and requested CRS, and atomically creates one non-overwriting JSON snapshot. Its output **does not** feed the customer report or assert legal rights. The CLI produces no network request unless `--network` is explicitly supplied.

Tests run with a mocked provider response, never a live public endpoint:

    python -m pytest -q tests/test_nwi_source_inspector.py

## Offline GDAL/OGR topology quarantine gate

The opt-in network inspector and the GDAL validation gate are deliberately separated. The inspector emits one **inspection-only** JSON snapshot without generating a customer screening result. A locally saved snapshot can be passed through the independent topology and source-integrity checker:

    /usr/bin/python3 scripts/nwi_topology_gate.py /path/to/nwi-inspection.json

The gate verifies the embedded normalized GeoJSON SHA-256 fingerprint (not a signature), expected NWI identity and source-status fields, bounded feature count, ordering and declared geographic CRS, and actual OGR/GEOS polygon validity. It exits nonzero on missing, malformed, tampered, self-intersecting, empty or nonpolygon geometries. It reads the file without modifying it, never requests network access, and emits only a machine-readable **quarantined-topology-reviewed-not-approved** summary.

The existing GitHub QGIS runtime workflow calls `scripts/validate_nwi_topology_runtime.py` with **mocked synthetic polygons only**. The test proves that a valid ring passes, a modified checksum fails, and a self-intersecting bow-tie fails OGR validity even if its unkeyed hash is recomputed. **No actual live NWI feature has passed this gate**; it also cannot prove source authenticity, spatial completeness, temporal freshness, commercial reuse rights, wetland regulatory jurisdiction or client readiness.

## Offline replay and analyst intake (merged from independent PR #47)

After acquiring a **quarantined**, unapproved local snapshot, the additional
offline gates can replay normalized JSON structure, ordered identifiers, exact
attributes, vertex counts, the query-envelope constraint, and the unkeyed
normalized-GeoJSON SHA-256 checksum:

    python scripts/nwi_snapshot_replay.py /path/to/nwi-inspection.json
    python scripts/nwi_analyst_handoff.py /path/to/nwi-inspection.json

The first command returns `INTERNAL_INTEGRITY_REPLAYED_NOT_APPROVED` only
for internally consistent input. The second returns a **metadata-only**
`BLOCKED_PENDING_INDEPENDENT_SOURCE_REVIEW` analyst handoff, with required
review gates for original agency acquisition, wetland-project imagery/vintage,
AOI-specific geographic coverage, data rights, study boundary and qualified
methodology review. Neither tool sends a network request, promotes a source
into a customer screening report, grants commercial reuse rights, or produces
a regulatory jurisdiction decision. The source checksum is **not** an agency
signature. A zero-feature source remains `coverage_state=unverified`.

The separate OGR topology quarantine gate remains required for actual
polygon validity; envelope overlap and normalized JSON replay are not
substitutes for full geometry validation.

## Live-query status (November 7, 2026)

A direct read-only request for a deliberately small non-client Florida test envelope was attempted from the execution environment. DNS resolution to the USFWS service failed; an external web retrieval of the dynamic query endpoint also did not return a usable response. **No feature response, count result, or agency query success is claimed; no live spatial output was produced.** Separately, publicly accessible ArcGIS layer metadata confirmed query support, the polygon layer identity, fields, feature paging, and GeoJSON formats.

Reproduction from an approved network egress host requires an explicit `--network` flag, the same tiny test envelope, and review of the returned data status before any use. Do **not** schedule bulk queries or infer missing wetlands from empty output. The CLI's default remains offline.

## Release gates not yet met

1. Confirm actual successful live feature retrieval, service output CRS and full paging for the selected envelope; record redacted request/response evidence, retrieval UTC and hashes.
2. Verify geographic coverage and gaps independently using official NWI project/update metadata. An empty result or a 200-feature limit is not proof of completeness.
3. Perform a written rights review for client reuse, redistribution and derivatives; public query access alone is not approval.
4. A 2026 polygon FeatureServer metadata candidate is identified; verify its **live** geometry, specific `ASMNT_YR` and county coverage, complete license/redistribution terms, boundary accuracy, privacy/data minimization and suitability before any parcel-level calculation.
5. Integrate bounded, reviewed snapshots with the actual QGIS/GDAL area engine, using separately validated CRS, validity, topology, measurement units and authoritative study-boundary provenance.
6. Run independent methodology and customer review and record engineering time, revision costs and willingness to pay before declaring a validated commercial product.

## No unauthorized transition to production

Nothing in this adapter initiates commercial orders, sends client emails, deploys services, accesses private customer files or changes the approved synthetic-only report pipeline. Humans retain authorization over publication, licensing decisions and client-facing claims.

Related: [product issue #39](https://github.com/ZQM-Computing/qgis-resources/issues/39), [synthetic PR #40](https://github.com/ZQM-Computing/qgis-resources/pull/40), [synthetic evidence bundle](SCREENING_REPORT.md).
