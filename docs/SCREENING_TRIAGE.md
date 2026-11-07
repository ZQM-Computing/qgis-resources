# Screening triage v0.1 — risk signals are not underwriting conclusions

The existing P0 parcel-screening pilot produces synthetic projected-area measurements and a deterministic evidence ZIP. This increment adds `scripts/screening_triage.py`: a **pure, bounded, deterministic assessment of the measurement ledger**, embedded as `screening_triage` in `report.json`.

## Contract

- `REVIEW` means measured synthetic mapped overlap is present (including overlap in a partially covered source); it is a **screening flag**, not a legal GO/NO-GO result.
- `INSUFFICIENT_EVIDENCE` applies when no synthetic mapped overlap was measured. Even fully mapped no-overlap **never means clearance** because data cannot establish jurisdictional, onsite or professional completeness.
- `priority` distinguishes mapped constraints, coverage gaps, both, or a no-regulatory-clearance result. The sources are explicit, ordered identifiers.
- A missing/unavailable/unfetched source must report **null** overlap and joins the coverage-gap list. Zero belongs only to valid measured zero overlap.
- Every result requires human review and has `regulatory_determination=false`, `financial_liability_estimate=null`, and `scope=synthetic-test-only`.
- Reject unexpected source findings, duplicate IDs, invalid coverage, incompatible finding/coverage combinations, nonfinite or out-of-bounds areas, incorrect geometry authority, and fabricated approval.
- No automatic permit decision, environmental delineation, insurance underwriting, professional signoff, customer delivery, external data source retrieval or production deployment.

## Run and validate

```bash
python -m pytest -q tests/test_screening_triage.py
# GDAL/OGR installed as in the QGIS runtime workflow:
/usr/bin/python3 scripts/validate_screening_spatial_runtime.py
/usr/bin/python3 scripts/screening_report.py fixtures/screening-manifest.json --out /tmp/zqm-screening-review.zip
```

The test fixtures remain artificial. The sample has a unioned mapped wetland intersection of approximately 25% of the test AOI *and* an unavailable flood source. Its expected triage is `REVIEW` with both mapped overlap and missing evidence listed.

## Next measured, independently reviewed increment

P0-A4 should verify a lawful public-source Florida/US study area and a separately licensed non-US case, without claims of parcel precision where the underlying data are missing. Compare area projections and geodesic area estimates, check data currency, verify rights and resolution, document known false-positive/false-negative modes, and obtain a qualified reviewer acceptance record. Only then calibrate domain-specific decision rules and economic scenarios against verified real outcomes; a scenario model must never be mislabeled as actual financial liability.

This keeps the eventual cross-vertical Spatial Risk-to-Capital architecture modular: spatial measurement → source completeness → rule pack → optional calibrated cost model → reviewed decision.
