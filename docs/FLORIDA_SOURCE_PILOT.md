# Florida public-source inspection pilot (P0-A4)

**Status:** source-discovery and read-only bounded ingestion prototype, not commercial coverage verification or a usable parcel screening engine. This independent source-inspection adapter targets `main` directly and does not require the synthetic screening code in PR #40 or modify any product delivery approval state.

## Grounded official sources

- [USFWS NWI web mapping services](https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services) publish a REST endpoint for Wetlands. On November 7, 2026, its publicly exposed ArcGIS REST metadata identified layer 0 as `Wetlands`, polygon features, `OBJECTID`, `ATTRIBUTE`, `WETLAND_TYPE`, GeoJSON query support, pagination, and a maximum 500 returned records per request. These are **service metadata observations**, not a successful live feature-download claim.
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

Sample coordinates define an arbitrary small test envelope and are **not a customer's parcel**. The adapter allows only official USFWS NWI layer 0 HTTPS endpoints, blocks HTTP redirects, bounds each response to 4 MiB, caps a Florida envelope at 0.02 degrees in each direction and limits returned features to 200. It first verifies layer capability/schema and obtains the server's count, then requests GeoJSON with stable `OBJECTID` pagination, reconciles counts and rejects truncated/invalid/duplicate records. It also rejects provider polygon bounding envelopes wholly outside the requested query box, including on later pages; this is only a necessary consistency check, **not** proof of true polygon intersection, dataset coverage or correct source geometry. If the server returns too many features or is inaccessible, the request **fails closed**; it does not declare no constraint.

Source results carry `coverage_state=unverified`, `reuse_rights=unverified`, `human_review=pending`, and `regulatory_determination=false`, including when the query returns zero features. The result also records a SHA-256 hash of the **normalized, filtered GeoJSON**, ordered unique-object-ID checks, and the total validated vertex count. This is an internal transformation fingerprint, **not** a signature or a hash of the unmodified agency response. Because layer data may change between a count request and the individual feature pages, count/ID reconciliation **does not prove point-in-time snapshot consistency**. If the agency metadata, geometry type, CRS, page count, identifiers, mandatory attributes, or source endpoint differ from the expected contract, ingestion fails instead of silently accepting an incomplete dataset. The adapter filters source attributes to an allowlist, records the provider URL, retrieval time, bounding box and requested CRS, and atomically creates one non-overwriting JSON snapshot. Its output **does not** feed the customer report or assert legal rights. The CLI produces no network request unless `--network` is explicitly supplied.

Tests run with a mocked provider response, never a live public endpoint:

    python -m pytest -q tests/test_nwi_source_inspector.py

## Offline integrity replay — not authenticity or approval

An inspected NWI snapshot can be checked again without network access using:

    python scripts/nwi_snapshot_replay.py /path/to/nwi-inspection.json

The `scripts/nwi_snapshot_replay.py` checker enforces normalized GeoJSON structure, exact ordered feature IDs, strict filtered attributes, layer and CRS identity, feature/vertex counts, bbox-envelope consistency and the source snapshot's normalized-GeoJSON SHA-256 digest. This detects accidental corruption and many internal mismatches between inspection and downstream processing. Source hashes can be regenerated by anyone editing the snapshot, however, and therefore **are not authenticated signatures**. No remote source is fetched during replay.

A successful command returns `INTERNAL_INTEGRITY_REPLAYED_NOT_APPROVED`, with `snapshot_authenticity_verified=false`, `agency_temporal_consistency_verified=false`, `geographic_completeness_verified=false`, `reuse_rights_verified=false`, `regulatory_jurisdiction_determined=false`, and `commercial_delivery_authorized=false`. A zero-feature snapshot retains all those false states.

The replay result must never be wired directly to a paid screening report or permission to use restricted data. To reach a client deliverable, independently verify original source acquisition and metadata, wetland-project mapping dates, actual local coverage, source rights and appropriate professional review. Tests use fabricated provider responses and do not demonstrate a live agency download.

## Analyst source-candidate handoff (non-approving)

After local integrity replay, a separate offline handoff can generate a **metadata-only, blocked analyst intake**:

    python scripts/nwi_analyst_handoff.py /path/to/nwi-inspection.json

The handoff replays the full normalized snapshot and emits the source identity, requested bounding envelope, normalized feature digest/count, a stable `source-candidate-review-handoff` type, and six explicitly unresolved review gates. **It does not output source polygons, a screening manifest, a parcel analysis, a regulatory finding or a customer deliverable.** This keeps its data contract separate from the synthetic Site Feasibility Passport in PR #40.

The result always has `status=BLOCKED_PENDING_INDEPENDENT_SOURCE_REVIEW`, `commercial_delivery_authorized=false`, `source_authenticity_verified=false`, `aoi_coverage_verified=false` and `human_review_required=true`. A zero-feature snapshot cannot be interpreted as absence of wetlands. Successful CLI exit means only that a blocked intake could be assembled from internally consistent data.

Independent approval requires authenticating the original agency acquisition, associating NWI project mapping dates and imagery vintages with the AOI, confirming coverage and known omissions, documenting reuse and redistribution rights, verifying parcel/study boundaries and coordinate references, and obtaining qualified analyst acceptance. **None of these checks is automated or asserted complete here.** Fingerprints are not cryptographic signatures from the issuing agency.

The handoff is local, read-only and has no network flag, outbound submission, report-publishing action or commercial approval control.

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

Related: [product issue #39](https://github.com/ZQM-Computing/qgis-resources/issues/39), [synthetic PR #40](https://github.com/ZQM-Computing/qgis-resources/pull/40), [synthetic evidence bundle under review in PR #40](https://github.com/ZQM-Computing/qgis-resources/pull/40).
