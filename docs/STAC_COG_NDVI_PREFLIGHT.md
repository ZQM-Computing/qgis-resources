<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e6bf4da934c400fa07f57e8bfb2bb473eb19ba651d2a86e2645cf1bbddeb9397 -->

# STAC → COG windowed NDVI preflight (P0, opt-in)

**Status:** engineering prototype for bounded exploratory imagery screening, not operational asset monitoring, definitive land-cover change, EUDR due diligence, utility clearance or financial underwriting. **Default: no network. Paid imagery purchases: impossible by design.**

## Provider, public API, rights and corrections

- The Microsoft Planetary Computer STAC API is `https://planetarycomputer.microsoft.com/api/stac/v1`, *not* `https://microsoft.com`. The official `pystac-client` documentation uses a `planetary_computer.sign_inplace` modifier for signed cloud asset links: <https://pystac-client.readthedocs.io/en/latest/usage.html>.
- The `sentinel-2-l2a` collection exposes optical bands `B04` (red), `B08` (near infrared) and `SCL` (scene classification). Asset signing and request quotas depend on the provider: <https://github.com/microsoft/planetary-computer-sdk-for-python>.
- STAC responses are **metadata**, not a guarantee that an advertised image is a Cloud-Optimized GeoTIFF, accessible, licensed for the use case, complete or accurately georeferenced.
- A provider's general public availability is not a review of product-specific redistribution, commercial use or storage terms. Verify collection/item-level license, notices, usage limits and any commercial agreement before using pixels in customer evidence. Nothing here buys commercial imagery.
- USGS Landsat, Copernicus Data Space, NASA Earthdata and commercial constellations require separate authenticated adapters and independently verified asset conventions; they are *not* silently substituted into this Sentinel-2 implementation. A missing optical scene returns unavailable evidence, **not** an uncalibrated automatic SAR inference.

## Workflow and explicit limits

1. Restrict a geographic query to EPSG:4326 west/south/east/north, each span **at most 0.25°**; refuse antimeridian crossings, invalid and nonfinite coordinates. Time range at most **31 days**.
2. Without `--allow-network`, require `--fixture` and perform metadata validation only. The local file is fictional. Never read pixels from a test fixture or arbitrary URLs supplied by users.
3. With `--allow-network`, search the *fixed* Planetary Computer STAC endpoint, collection `sentinel-2-l2a`, max **4 returned items**, ordered locally by scene-level reported cloud cover (maximum 20% by default). **Scene-level cloud percent is not AOI-level usability.**
4. Require B04, B08 and SCL asset references restricted to `https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/`, the documented storage account and container for the Planetary Computer Sentinel-2 L2A collection. Other Azure Blob accounts/containers are rejected, and no credential-bearing URL is included in output. Cloud signing is read-only; always treat signed URL query tokens as secrets.
5. Only with `--stream-window --allow-network`, open the signed COG assets through Rasterio/GDAL, project the bounded geographic rectangle to the NIR grid, and clip its window to raster extent. Reject windows with zero valid pixels or more than **250,000 raster pixels**. This raster cap is independent of the 0.25° query-span limit: at B08’s 10 m resolution, a 0.25° square generally exceeds the streaming cap. Choose a smaller bbox; the AOI example below uses 0.04° per side (about 190,000 window pixels at that location). Projection and grid alignment determine the actual window size.
6. Resample B04 bilinearly and SCL nearest to the B08 grid. Count pixels with SCL 4/5/6 and valid nonzero B04/B08 values. Compute a preliminary **digital-number band ratio** `(B08-B04)/(B08+B04)` for the rectangular window. With an optional validated `--aoi-geojson` Polygon/MultiPolygon, it additionally uses a GDAL-reprojected pixel-center polygon mask, excluding pixels outside the supplied boundary. Without that argument it remains a rectangular window summary. **Neither mode** applies calibrated reflectance/radiometric offsets, atmospheric/BRDF uncertainty review or verified survey boundaries; do not market its digital-number ratio as calibrated NDVI.
7. Report only scene ID/time, metadata cloud cover, valid pixel count, preview ratio, explicit unverified states and reviewer requirement. Do not write signed URLs, persistent imagery or customer boundaries to disk.

### Offline example (no network)

```bash
python scripts/stac_cog_ndvi_preflight.py \
  --bbox -46.63 -23.55 -46.60 -23.53 \
  --start 2026-10-01 --end 2026-10-31 \
  --fixture fixtures/stac-sentinel-synthetic-item.json
```

The fixture uses invented Azure-style URLs and fabricated metadata. It proves only local schema checks.

### Explicit opt-in live query (not run or validated here)

```bash
python -m pip install pystac-client planetary-computer rasterio numpy
python scripts/stac_cog_ndvi_preflight.py \
  --bbox -46.63 -23.55 -46.60 -23.53 \
  --start 2026-10-01 --end 2026-10-31 \
  --allow-network --stream-window \
  --budget-plan fixtures/stac-cost-budget-synthetic.json
```

Install packages in a separate controlled environment. Re-evaluate API versions and credentials. Live tests should be executed only after confirming provider access, terms and rate limits. GDAL's HTTP range reads can issue multiple requests including auxiliary/overview reads; **a pixel-count cap does not guarantee an equivalent network-byte cap**.

## Polygon AOI masking — bounded, local-only input

`--aoi-geojson fixtures/stac-aoi-synthetic.geojson` accepts **only** a GeoJSON `Polygon` or `MultiPolygon` geometry in longitude/latitude (EPSG:4326). The AOI must remain within the requested `--bbox`. Input is limited to 128 KiB, at most 2,000 vertices and 20 polygon parts/rings per nesting level. Structural validation rejects nonfinite coordinates, unsupported dimensions, malformed rings and dateline crossing. Shapely/GEOS additionally checks polygon topology; invalid input is rejected rather than silently repaired.

The Rasterio path transforms the polygon to the NIR raster grid, creates a pixel-center inclusion mask and combines it with the B04/B08 nodata and SCL mask. Output adds `aoi_pixel_count`, `valid_fraction_of_aoi` and `aoi_polygon_mask_applied`. If no pixel centers fall inside the polygon or none remains usable, the request fails closed. The pixel-window cap still applies **before** masking, so tiny polygons inside huge windows cannot evade compute limits.

The AOI is never printed in results, and local fixture mode never reads pixels or initiates network requests. Polygon topology validity is **not** evidence of surveyed ownership, regulatory boundary accuracy, positional accuracy, or legal usage rights. Edge pixels are chosen by pixel-center semantics (`all_touched=False`); independent area-weighted/perimeter accuracy evaluation remains a backlog item.

For an authorized live exploratory read, include the polygon and the required local cost budget:

```bash
python scripts/stac_cog_ndvi_preflight.py \
  --bbox -46.68 -23.56 -46.64 -23.52 \
  --start 2026-10-01 --end 2026-10-31 \
  --aoi-geojson fixtures/stac-aoi-synthetic.geojson \
  --budget-plan fixtures/stac-cost-budget-synthetic.json \
  --allow-network --stream-window
```

The fixture geometry is **fictional**, and this command is provided only as an opt-in engineering example; live provider reads, licensing and costs have not been independently validated. The local synthetic runtime tests generate their own GeoTIFFs and do not connect to the provider.

## Optional bounded COG HTTP Range diagnostic (not a GDAL traffic cap)

The optional `--probe-range` flag performs **three explicit read-only GET requests**, one each against the selected Sentinel-2 B04, B08 and SCL COG assets, using `Range: bytes=0-4095`, `Accept-Encoding: identity`, an eight-second timeout and strict provider-host allowlisting. It refuses HTTP redirects, full-body `200` responses, missing/malformed `Content-Range`, unexpected `Content-Length`, compressed replies, oversized/short responses and invalid TIFF/BigTIFF file signatures. Its report contains **only** the three-band diagnostic request counts and received payload bytes, never the signed asset URL or its credential-bearing query string.

This step is independently opt-in and requires **both** `--allow-network` and a local `--budget-plan` declaring at least four requests (one discovery allowance plus three probes) and at least 12,288 estimated range bytes. A request without the minimum budget is blocked before STAC discovery. The probe is a *diagnostic only*: Rasterio/GDAL may subsequently perform additional HEAD, GET, overview, range, retry, proxy or auxiliary requests, and no actual egress-billing counter or global HTTP traffic limiter has been implemented. Running the probe **does not grant permission** for a hosted production worker or any imagery purchase.

The dedicated workflow tests HTTP status, exact ranges, length validation, truncated or oversized responses, redirect refusal, URL secret redaction, and opt-in budget enforcement using mocked responses. It does not contact the provider or certify live HTTP behavior.

The command for an explicitly authorized engineering test is:

```bash
python scripts/stac_cog_ndvi_preflight.py \
  --bbox -46.63 -23.55 -46.60 -23.53 \
  --start 2026-10-01 --end 2026-10-31 \
  --budget-plan fixtures/stac-cost-budget-synthetic.json \
  --allow-network --probe-range
```

A trusted live provider source, legal rights, redirect-enforced GDAL configuration, complete transfer metering, request accounting and externally enforced spending limits are **still required** before production.

## Local original-product XML integrity gate

Optional corrected candidate calculations now require **both** `--radiometry-json` and `--product-metadata-xml`. The XML is a bounded local file (2 MiB maximum). The parser refuses DTD/entity declarations and extraneous processing instructions, limits element count and requires exactly one processing baseline and BOA quantification value; B04 (band ID 3) and B08 (band ID 7) offset entries must each occur exactly once. The file's actual SHA-256 must match the pinned digest in the radiometry JSON, and processing baseline, quantification and the two offsets must match the declared arithmetic parameters. Missing, inconsistent or malformed records are blocked **before corrected COG pixel reads**.

Example using **fictional, unauthenticated** metadata (fixture mode never reads remote pixels):

```bash
python scripts/stac_cog_ndvi_preflight.py \
  --bbox -46.63 -23.55 -46.60 -23.53 \
  --start 2026-10-01 --end 2026-10-31 \
  --fixture fixtures/stac-sentinel-synthetic-item.json \
  --radiometry-json fixtures/stac-radiometry-synthetic.json \
  --product-metadata-xml fixtures/stac-product-metadata-synthetic.xml
```

The output records local fingerprint and parameter consistency but **does not authenticate original Copernicus/Planetary Computer provenance**, establish that the XML is linked to the same tile's cloud assets, or approve any scientific/regulatory claim. A matching file hash only establishes that a referenced local file has the expected bytes; anyone controlling both the file and digest can manufacture a matching pair. Independently verified provider origin, per-item lineage and source-use rights are still release blockers.

## Optional Sentinel-2 BOA reflectance correction — review-only

Copernicus Sentinel-2 L2A documentation specifies the post-processing-baseline 04.00 conversion: `L2A_SR = (DN + BOA_ADD_OFFSET) / QUANTIFICATION_VALUE`, with `DN=0` reserved as nodata. The `BOA_ADD_OFFSET` is declared in original product/datastrip metadata; Sentinel-2 product processing history must be checked per scene. See the [Copernicus L2A quality report](https://sentiwiki.copernicus.eu/__attachments/1692737/OMPC.CS.DQR.002.12-2025-Sentinel-2-MSI-L2A-DQR-January2026.pdf).

The optional `--radiometry-json` argument accepts a bounded local record declaring the exact scene ID, original product metadata SHA-256, acquisition date, post-04.00 processing baseline, band-specific B04/B08 offsets and reflectance quantification value. The example `fixtures/stac-radiometry-synthetic.json` is **fabricated and unauthenticated**. It cannot certify the correctness of actual cloud asset pixels or original product metadata.

When correction metadata are supplied, the program **validates the scene ID before opening any raster asset**, then requires both B04/B08 datasets to be unscaled, zero-offset, single-band raw `uint16` samples. Any scale/offset already advertised by the raster causes a fail-closed rejection to avoid accidental double application; this does not independently authenticate a source's interpretation of its own pixels. The exploratory output preserves `mean_ndvi_dn_ratio` and, when metadata are supplied, adds a separate `radiometric_candidate` with `mean_ndvi_reflectance_candidate`. Negative or zero corrected reflectance inputs are conservatively excluded from this candidate, and the count is disclosed. When all candidate pixels are excluded, the candidate mean is `null`. The result always sets `product_metadata_authenticity_verified=false`, `processing_baseline_crosschecked_to_original_product=false` and `customer_ready_ndvi=false`. It never asserts calibrated operational NDVI.

The metadata fixture demonstrates that a synthetic DN pair B08=6000 and B04=2000 produces a raw ratio 0.5 but a corrected reflectance-ratio candidate about 0.666667 with each offset at -1000 and quantification 10000. These are **synthetic arithmetic expectations**, not real-scene accuracy metrics.

Before publishing actual corrected NDVI, independently acquire and authenticate the source product metadata, bind it to the actual scene COGs, check per-band offsets and rescaling already applied by the imagery host (to prevent double-correction), and validate raster nodata/masks, scene consistency, SCL classification and scientific uncertainties. Until then, corrected values remain **review-only**, never underwriting evidence.

## Backlog hardening: AOI coverage, radiometry and budget preflight

The preflight now **requires the scene bounding envelope to fully cover the requested AOI bounding box**, and separately refuses partial raster-window coverage before computing a summary. This is a *necessary* spatial coverage condition, not a guarantee of cloud-free or gap-free pixels. Multi-scene mosaicking and antimeridian handling remain explicitly unsupported.

**Radiometric science blocker:** Sentinel-2 L2A processing baseline 04.00 introduced `BOA_ADD_OFFSET`, and simply dividing raw B08/B04 digital numbers can bias the reported vegetation index. Planetary Computer's `sentinel-2-l2a` assets may not expose this offset in STAC `raster:bands` or GeoTIFF headers; authoritative product metadata must be retrieved and validated before calculating calibrated surface reflectance. This prototype deliberately returns `mean_ndvi_dn_ratio` and `radiometric_offset_and_scale_verified=false`. It must not be sold as calibrated NDVI or reliable deforestation evidence.

References: [Copernicus Sentinel-2 L2A Data Quality Report](https://sentiwiki.copernicus.eu/__attachments/1692737/OMPC.CS.DQR.002.12-2025-Sentinel-2-MSI-L2A-DQR-January2026.pdf?inst-v=57724d91-952e-43dd-b156-b6e5f1d03465) and [Planetary Computer ingestion notes](https://sentinel-hub.github.io/titiler-openeo/planetary-computer/).

An additional **offline cost gate** is provided:

```bash
python scripts/stac_cost_budget.py fixtures/stac-cost-budget-synthetic.json
```

Live requests now require `--budget-plan` before a remote STAC search is even attempted; blocked or zero-request plans fail before network access. This is not a live billing counter, and network bytes or charges can exceed declared estimates. It accepts explicitly declared estimates of number of requests, remote bytes, compute seconds and analyst minutes, as well as user-provided per-unit USD rates and a budget ceiling. The fixed policy caps requests at 100, transfer estimates at 2 GB, compute at 3,600 seconds, review time at 240 minutes, and approved budget ceilings at $10,000. Each cost is rounded upward to the nearest cent. Exceeding the ceiling is blocked. **Rates are purely hypothetical in the fixture; the tool does not monitor provider bills, enforce an actual egress quota, authorize API access, buy imagery or permit client delivery.** Production must use measured billing, authenticated budgets and a separate enforcement control plane.

## Zero-fixed-cost rollout and optimization

Keep a single versioned, read-only acquisition policy above the existing land, utility and EUDR evidence applications. **Do not add Snowflake, BigQuery or an image warehouse** before customer volume and actual cost justify them.

| Optimization lever | Control | Measurement |
| --- | --- | --- |
| Metadata first | Limit area, dates, items, scene cloud and asset set; do not stream on no-match | Queries, selected scenes, candidate rejection rate |
| Tile/window budget | Hard cap output pixels; one scene and minimum necessary bands | Requested pixels, valid pixels, actual range requests and bytes |
| Cache identity | Cache approved scene metadata using provider, collection, item ID, STAC version, AOI hash, timeframe and method version; **exclude signed URLs** | Cache hit rate and metadata retrieval time |
| Short-lived signing | Sign asset URLs on demand with short-lived provider tokens; never persist token-bearing URLs | Signature refreshes, 401/403 retries |
| Early skip and escalation | Missing/contaminated scene → `INSUFFICIENT_EVIDENCE`, manual SAR or commercial imagery review | Missingness rate and analyst escalations |
| Controlled concurrency | Start with one concurrent remote job, fixed monthly request/egress budgets, 429 backoff and retry ceilings | Provider charges, egress bytes, timeouts |
| Commercial escalation | Require a **separate** signed buyer approval and price ceiling for sub-meter tasking | Approved purchases and per-order imagery cost |
| Audit retention | Retain source IDs, version, reviewed rights and numerical summaries, not whole rasters or signed URLs | Data footprint and retention period |

### Per-case cost model

Track actual billed amounts rather than assume cloud-hosted data implies zero cost:

```text
cost_per_case =
  provider_search_and_request_cost
  + remote_egress_bytes × billed_egress_price
  + image/tasking_license_cost
  + processing_seconds × effective_compute_rate
  + retained_bytes × storage_rate × retention_period
  + analyst_review_minutes × loaded_labor_rate
```

Review each component separately. **Do not advertise savings, legal compliance, seamless global coverage, centimeter-scale accuracy or continuous monitoring** without documented baseline and independent real-data validation.

## Release gates

- Offline tests and exact-head CI/security must pass.
- Add instrumented mock Range HTTP tests, a calibrated radiometric/SCL processing test, an actual point-in-polygon crop, and a provider-authenticated low-volume integration test before presenting quantified NDVI externally.
- Confirm data-rights and commercial terms for every provider and collection, not just the STAC service as a whole.
- Verify cloud/shadow masking, per-AOI coverage, atmospheric/radiometric offsets, scene temporal changes and independent field observations. Follow with an independently reviewed uncertainty budget.
- Add actual byte-metering, request quotas, secure token handling, deduplication and remote-host redirect controls before a hosted worker.
- Preserve human review; output cannot authorize EUDR DDS, environmental regulatory determinations, utility inspection orders, insurance underwriting or paid imagery tasking.

This standalone prototype does not alter existing production services, credentials, trust roots, Stripe, DNS or customer data.


<!-- /coderabbit-ai-generated:v1 -->