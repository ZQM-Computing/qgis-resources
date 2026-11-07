# EUDR geolocation evidence preflight — synthetic P0 adapter

**Status: pre-production, synthetic metadata only. Not a due diligence statement (DDS), conformity certificate, EUDR risk assessment, satellite monitor or TRACES integration.**

This adapter is a separately reviewable child of [the synthetic parcel screening core](https://github.com/ZQM-Computing/qgis-resources/pull/40). It is stacked on that PR's validated commit, not on production `main`. Keep the parent PR and adapter independent; do not claim this adapter is available to customers.

## Regulatory basis and precise limitations (reviewed 2026-11-07)

- The [European Commission's EUDR overview](https://environment.ec.europa.eu/topics/forests/deforestation/eu-deforestation-regulation-eudr_en) lists **December 30, 2026** for medium/large operators, **June 30, 2027** for most micro/small operators, and special transitional provisions. Rules were amended in December 2025 and 2026; legal counsel must establish current company/product scope.
- The [European Commission's current FAQ](https://environment.ec.europa.eu/document/download/744919a7-8650-4850-89ad-a597268cd69e_en?filename=FAQ-UPDATE-5th-Iteration+FINAL.pdf) explains that plots over four hectares used to produce relevant commodities other than cattle require polygon geolocation. Small plots and cattle establishments may permit points, subject to full context. The adapter checks **declared** plot area only; it does not calculate or verify hectares and cannot certify precision.
- The [regulation's Article 9 evidence requirements](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1115) include production geography and production period. A full determination also requires relevant product classification, legal production evidence, deforestation information, traceability and the applicable operator's due-diligence obligations.
- The EUDR Information System is a specific TRACES-based system. **No authentication, DDS submission, regulatory exchange, or automated filing is implemented here.**

## Scope and interface

Local-only CLI: `python scripts/eudr_evidence_preflight.py INPUT.json`. Input must be UTF-8 JSON at most 1 MiB without duplicate keys or nonfinite numbers; bounded to 200 plot records.

The synthetic batch includes `schema_version: 1`, opaque batch ID, one commodity from `cattle, cocoa, coffee, oil_palm, rubber, soya, wood`, production country (two-letter code) and production period, `crs: EPSG:4326`, product-scope review state, and plot records. A plot has opaque ID, declared area, Point/Polygon/MultiPolygon GeoJSON geometry, producer linkage flag and source reference, acquisition date, asserted source SHA-256 and rights-review status.

The tool checks coordinate ranges and GeoJSON ring closure *structurally*, not topology, surveyed accuracy, 6-decimal representation, correct coordinate reference, hectares, vegetation change, legal/commodity provenance, EU operator status or product classification. A syntactically plausible polygon always produces `polygon-topology-area-and-accuracy-unverified` pending an independent spatial review. Supplier/plot linkage self-assertions remain untrusted.

The returned deterministic, redacted exception packet contains only opaque IDs and exception codes. `BLOCKED` means known gaps or unresolved checks; `REVIEW_REQUIRED` (reserved for later independently verified evidence) is **not** legal clearance. No `GO`, `NO-GO` or financial liability values are generated. Every output has `human_review_required=true`, `deforestation_assessed=false`, `compliance_determined=false`, `dds_generated=false`, `traces_submitted=false`.

## Test plan

```bash
python -m pytest -q tests/test_eudr_evidence_preflight.py
python -m pytest -q
```

Tests cover non-cattle area/polygon flags, cattle establishment-chain uncertainty, source integrity, duplicate plot identifiers, missing production link, malformed and nonfinite geometry, fabricated compliance claims, output redaction, oversized files and deterministic output. All samples are fictional; no customer, supplier or personal data belong in fixtures.

## Follow-on gated increments

1. Add a GDAL/OGR consumer adapter to the screened polygon core with independent CRS, topology, *computed* geodesic/appropriate projection area and six-decimal coordinate representation checks where applicable. A source hash proves identity of bytes, not their authenticity.
2. Verify a lawful public dataset and license against a human-reviewed supplier scenario, with robust role/product scope and jurisdictional regulation versioning.
3. Add a versioned rule pack only after legal applicability and EU Information System schema have been independently verified, supported by consumer-driven fixtures. No DDS or TRACES side effects in this phase.
4. Build satellite deforestation evidence as an independent, accuracy-calibrated module; no claim of real-time monitoring without measured temporal data freshness.
5. Validate actual buyer demand and paid scope before investing in hosted bulk upload or subscription. Isolated local processing is the default; audit data privacy and tenant boundaries before handling customer supply-chain logs.

**Marketing:** permissible development label is *EUDR geolocation evidence preflight prototype*. Do not advertise EUDR compliance certification, verified geolocation, DDS automation, border clearance, real-time SAR monitoring or fines prevented.
