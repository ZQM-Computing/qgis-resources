# Preliminary screening manifest contract (P0-A1)

**Status: draft synthetic contract pilot — not a parcel-screening engine or client-ready product.**

This dependency-free component validates source metadata needed before any spatial overlay, confidence statement, or client deliverable. It does not download data, inspect remote URLs, verify licenses, validate geometry topology, calculate area, certify regulatory results, or authorize delivery. Global country/region fields express an interface shape, not worldwide data availability.

## Run

From repository root with Python 3.11+:

    python scripts/screening_manifest.py fixtures/screening-manifest.json
    python -m pytest -q tests/test_screening_manifest.py

Exit 0 means the local **metadata syntax and policy contract** passed; exit 1 means a metadata validation error; exit 2 means the manifest could not be safely read. This is not source coverage, spatial QA or legal approval. This reader is read-only and refuses oversized, duplicate-key and non-finite-JSON manifests.

## Interface

- Geographic scope: project ID, country, region, authority, declared study-area CRS, and explicit synthetic/non-survey boundary basis. The present P0-A1 contract intentionally uses a local synthetic study-area fixture; support for independently verified customer/public boundaries belongs in the next implementation increment.
- Source ledger: ID, title, origin, authority, source reference, asserted coverage state, reuse-rights review, license, date/UTC retrieval timestamp, CRS, and limitations.
- Coverage states: verified, partial, missing, unavailable, unverified. **Verified is the producer's metadata assertion**, not independently validated data completeness. Partial/missing/unavailable/unverified cannot become a no-constraints finding.
- Metadata with asserted usable coverage must declare approved reuse rights, a reference, license, CRS and UTC retrieval timestamp. Actual use rights must still be checked independently. External source references require HTTPS with no embedded credentials; local synthetic fixtures must remain within fixtures/.
- Service tiers: preliminary, quantified, specialist-reviewed. This pilot always requires draft status and pending human review; it deliberately has no approval API.
- The sample geometries use degrees in EPSG:4326; do **not** compute planar area in degrees. Subsequent implementation must select an appropriate equal-area CRS or geodesic method and dissolve overlapping footprints before percent-area reporting.

## Approved product architecture and delivery controls

1. Start with a headless Python processing core; add a CLI and QGIS runtime adapter, and subsequently an authenticated web/API adapter with consistent versioned contracts.
2. Validate Florida and US data-source adapters before a non-US demonstration; never promise uniform global authoritative parcel coverage.
3. Open-source general interoperable code and reproducible examples while separating customer-specific paid delivery, operational support and confidential configurations.
4. Do not copy private client datasets into fixtures. Prefer local-first execution, tenant isolation when hosted, encrypted stores, retention/deletion controls, and **no training models on customer data without explicit authorization**.
5. The Three Chiefs may collect evidence, prioritize and execute authorized low-risk work; client pricing/commitments, specialist attestations and production/security boundaries remain subject to designated human review.
6. Commercial product validation still requires real spatial runtime evidence, source licensing/coverage verification, report review, measured effort/cost and a paying pilot or comparably strong independent buyer validation.

## Follow-on gates

See [QGIS product roadmap](PRODUCT_ROADMAP.md), [workflow contracts](WORKFLOW_CONTRACTS.md), [dataset QA](DATASET_QA.md), and [pilot implementation issue #39](https://github.com/ZQM-Computing/qgis-resources/issues/39). P0-A2 must test known synthetic intersection/no-intersection and overlap handling, unknown CRS, empty/invalid geometry, deterministic reruns and safe outputs in actual QGIS/GDAL. Passing these metadata checks is not completion of P0-A2.
