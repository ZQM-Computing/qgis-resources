# Spatial Risk Engine: production release readiness and rollback

**Status (2026-11-07): internal synthetic sandbox candidate only. Customer-facing production release: BLOCKED.** Passing repository CI establishes that tests completed on one commit; it does **not** verify authoritative data, professional conclusions, client deliverability, or permissions.

## Deployment decision matrix

| Capability | Allowed at this stage | Required before expanding |
| --- | --- | --- |
| Source code merged into the public resource library | After exact-head CI, independent code review, and protected-branch checks | Review approval and change management |
| Read-only local synthetic CLI executed in an isolated QA environment | Yes, with synthetic fixtures and no customer files | Operator-level access control and documented test evidence |
| Local synthetic ZIP for internal engineer/analyst review | Yes; clearly watermarked and restricted to test use | Human verification of limitations |
| NWI snapshot inspection and metadata-only analyst handoff | Read-only opt-in in separate PR #47; not shipped by this PR | Service/schema/edition, data-rights, and provenance validation |
| Actual parcel/environmental constraint report delivered to a paying client | **No** | Verified lawful datasets, AOI-specific coverage, accurate boundary/CRS, methodology and qualified analyst approval |
| EUDR DDS or compliance decision | **No** | Independently reviewed legal rule pack and source validation; a different release authorization |
| Safety/utility clearance or financial liability estimation | **No** | Specialized field calibration, risk methodology and independent reviewers |
| Automated production deployment or external publishing | **No** | Approved destination, authentication, security/tenant isolation, recovery drills and release signoff |

## Release candidate capture

Record the exact commit SHA, PR review decisions, required-branch protection/ruleset results, all Actions job outcomes (CI, CodeQL, QGIS runtime, secret, supply-chain and general security scans), and any merge-base drift. A green result for an earlier SHA is not sufficient.

Execute only in a disposable test environment with synthetic fixture inputs:

```bash
python -m pytest -q
/usr/bin/python3 scripts/validate_screening_spatial_runtime.py
/usr/bin/python3 scripts/screening_manifest.py fixtures/screening-manifest.json
/usr/bin/python3 scripts/screening_report.py fixtures/screening-manifest.json --out /tmp/zqm-screening-review.zip
```

The two GDAL-enabled commands require the runtime that the QGIS workflow installs. Use a *new* disposable ZIP path per execution; the report CLI refuses to overwrite by default. Inspect `map.svg`, `report.json`, `sources.json`, `constraints.md`, the reported bundle SHA-256 and all source limitations. No synthetic success is an acceptable basis for actual property risk advice.

## External evidence gates

1. **Scope and licensing:** Confirm the exact landowner/customer authorized use, producer/provider agreement, attribution and distribution terms; archive dated source metadata and rights signoff outside public code.
2. **Temporal and geographic coverage:** Obtain authoritative project-level dataset vintage, imagery/interpretation dates and documented mapping gaps. An empty NWI query cannot establish absence.
3. **Geospatial correctness:** Validate actual AOI/parcel boundary against known authoritative sources, its date, horizontal and vertical CRS where relevant, topology, edge cases, measured area and any applicable location uncertainty.
4. **Professional/rule review:** Approve jurisdiction-specific language and review policy; distinguish environmental screening from wetlands delineation, a Phase I ESA, legal/regulatory determinations, surveying and engineering opinions.
5. **Security and privacy:** Threat model public uploads, zip and GeoJSON parsing, denial-of-service budgets, tenant separation, storage encryption, data retention, signed download links and audit access before introducing any SaaS or customer-data endpoint.
6. **Operations and recovery:** Define environment owner, deploy artifact digest, migration/rollback plan, encrypted backup restoration test, health checks, monitoring, incident response and secure secret rotation workflow. No credentials or trust roots changed by this PR.
7. **Commercial validation:** Record customer-accepted sample output, measured review time, error rates, rejection/appeal process and buyer-specific economics. Never promote savings hypotheses to measured ROI.

## Rollback and stop conditions

For the current **offline-only** component, rollback means disable the new CLI or restore the previous trusted repository commit in the controlled test environment; any previously generated synthetic ZIP must remain labeled non-client and must not be circulated as verified evidence.

For any future hosted release, before deployment create a rollback manifest linking the previous deploy artifact digest and configuration, define an operator-controlled traffic stop and restore procedure, and prove recovery in a non-production environment. Stop release on mismatched source hashes, undocumented licensing, unknown AOI coverage, uncontrolled write access, failed/queued checks, unresolved critical review findings or missing qualified signoff.

**No automatic promotion.** Code merge readiness and permission to publish commercial geospatial findings are distinct decisions. This document is the release acceptance register, not a claim those gates have been satisfied.

Related work: [Florida NWI inspector #47](https://github.com/ZQM-Computing/qgis-resources/pull/47), [EUDR evidence #46](https://github.com/ZQM-Computing/qgis-resources/pull/46), [utility corridor #43](https://github.com/ZQM-Computing/qgis-resources/pull/43), [utility 3D #44](https://github.com/ZQM-Computing/qgis-resources/pull/44).
