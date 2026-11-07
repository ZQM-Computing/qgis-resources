# Synthetic screening evidence bundle (P0-A3)

**Status:** reproducible local synthetic pilot for technical review. Not customer-ready and not a source of real parcel or environmental determinations.

## Run

From the repository root, using the GDAL-enabled Python interpreter supplied by the QGIS runtime environment:

    /usr/bin/python3 scripts/screening_report.py fixtures/screening-manifest.json --out /tmp/zqm-screening-review.zip

Run again only with explicit permission to replace the existing file:

    /usr/bin/python3 scripts/screening_report.py fixtures/screening-manifest.json --out /tmp/zqm-screening-review.zip --overwrite

**Output:** one ZIP archive with `map.svg`, `report.json`, `sources.json` and `constraints.md`. The archive uses fixed metadata for reproducibility, includes a SHA-256 digest in CLI output, and is validated before publication. Existing ZIPs cannot be overwritten by default. Publication creates the final filename atomically; the no-overwrite mode requires same-filesystem hard-link support and fails closed when unsupported.

## Contents and evidence

| File | What it records | What it does not prove |
| --- | --- | --- |
| `map.svg` | Projected synthetic AOI outline, clipped mapped intersections, legend and explicit missing-data status | Real-world basemap accuracy, parcel location, survey geometry or environmental conditions |
| `report.json` | Analysis method, CRS/units, measured projected area, constraint matrix and pending-review state | Regulatory determination or independently verified dataset completeness |
| `sources.json` | Source IDs, authorities, reference paths, source-fixture SHA256 hashes, claimed dates, coverage, rights and limitations | Remote source authority, real licenses, or actual regulatory effective dates |
| `constraints.md` | Human-readable finding matrix, source references, exclusions and escalation requirements | Professionally certified advice or approval to deliver to a customer |

Both the map and measurements use EPSG:6933 equal-area projected coordinates. The map is a **schematic only**; it has no regulatory setbacks, survey-grade parcel boundary, flood-zone verification or source-completeness guarantee. The report measures only artificial synthetic polygons. Duplicate mapped polygons are dissolved before calculating intersection area; unavailable and unprocessed external layers retain null measured area rather than a misleading zero.

## Operational safeguards

- Input geometry must pass the existing fail-closed, local-only, bounded, nonempty and explicit-CRS OGR validation.
- The package is built entirely in memory before publication; one archive is staged and atomically published. The source manifest and GeoJSON fixtures are opened read-only and never rewritten.
- Before publishing any ZIP, the validator checks exact member names, disallows encrypted/unsupported entries, caps each uncompressed member at 16 MiB and the total at 32 MiB, and streams member data to verify decompression/CRC without materializing expanded content in memory. A potentially compressed ZIP bomb is rejected before destination creation.
- Existing output is preserved if analysis, rendering, ZIP validation or staging fails. Default publication refuses an existing output. `--overwrite` is an explicit separate opt-in and replaces only a regular file.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e99222947cd378b62946807a193ba32df227cae18f88b6b66c67879bf4473e72 -->

- Reports include manifest-provided metadata and source references verbatim. URL validation rejects embedded username/password fields, but query parameters are accepted and are not redacted during packaging. Before generating or sharing a ZIP, operators must remove secrets from all manifest metadata, including tokens in external source references. Inspect the bundle before sharing; outputs are not guaranteed to be credential-free. A source hash is included for reproducibility, but hash provenance alone does not establish source credibility.

<!-- /coderabbit-ai-generated:v1 -->
- SVG is constructed from bounded projected polygon paths with escaped text; it does not embed scripts, remote images, interactive controls, downloaded assets or external links.
- Exact-head GitHub Actions must run Python unit tests and the actual GDAL/OGR runtime assertions, including reruns, archive checks, rendered SVG parsing, no-overwrite and failed-input preservation.

## Exit and remaining work

P0-A3 establishes a **synthetic evidence package**, not a commercially validated geospatial product. Remaining: (1) review packaging and accuracy of the graphical report; (2) use real lawful, up-to-date public data first in Florida/US and then a documented non-US pilot; (3) source rights and completeness verification; (4) independent reviewer acceptance; (5) unit economics and market validation. Production deployment, external publication and customer data require separately approved controls.

Release and rollback gates: [screening production-readiness register](SCREENING_PRODUCTION_READINESS.md). The synthetic report is internal-review-only; a green CI run is not customer-delivery authorization.

Related: [P0 pilot issue #39](https://github.com/ZQM-Computing/qgis-resources/issues/39), [synthetic spatial analysis](SCREENING_SPATIAL.md), [source manifest](SCREENING_MANIFEST.md), [workflow contracts](WORKFLOW_CONTRACTS.md).
