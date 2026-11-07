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
4. Require B04, B08 and SCL asset references with allowlisted Azure Blob HTTPS host syntax and no credential-bearing URL in output. Cloud signing is read-only; always treat signed URL query tokens as secrets.
5. Only with `--stream-window --allow-network`, open the signed COG assets through Rasterio/GDAL, project the bounded geographic rectangle to the NIR grid, and clip its window to raster extent. Reject windows with zero valid pixels or more than **250,000 raster pixels**.
6. Resample B04 bilinearly and SCL nearest to the B08 grid. Count pixels with SCL 4/5/6 and valid nonzero B04/B08 values. Compute a preliminary **digital-number band ratio** `(B08-B04)/(B08+B04)` for the rectangular window. It does **not** apply a client polygon mask, harmonization, radiometric offsets or atmospheric/BRDF uncertainty review; do not market this as an accuracy-calibrated NDVI.
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
  --allow-network --stream-window
```

Install packages in a separate controlled environment. Re-evaluate API versions and credentials. Live tests should be executed only after confirming provider access, terms and rate limits. GDAL's HTTP range reads can issue multiple requests including auxiliary/overview reads; **a pixel-count cap does not guarantee an equivalent network-byte cap**.

## Backlog hardening: AOI coverage, radiometry and budget preflight

The preflight now **requires the scene bounding envelope to fully cover the requested AOI bounding box**, and separately refuses partial raster-window coverage before computing a summary. This is a *necessary* spatial coverage condition, not a guarantee of cloud-free or gap-free pixels. Multi-scene mosaicking and antimeridian handling remain explicitly unsupported.

**Radiometric science blocker:** Sentinel-2 L2A processing baseline 04.00 introduced `BOA_ADD_OFFSET`, and simply dividing raw B08/B04 digital numbers can bias the reported vegetation index. Planetary Computer's `sentinel-2-l2a` assets may not expose this offset in STAC `raster:bands` or GeoTIFF headers; authoritative product metadata must be retrieved and validated before calculating calibrated surface reflectance. This prototype deliberately returns `mean_ndvi_dn_ratio` and `radiometric_offset_and_scale_verified=false`. It must not be sold as calibrated NDVI or reliable deforestation evidence.

References: [Copernicus Sentinel-2 L2A Data Quality Report](https://sentiwiki.copernicus.eu/__attachments/1692737/OMPC.CS.DQR.002.12-2025-Sentinel-2-MSI-L2A-DQR-January2026.pdf?inst-v=57724d91-952e-43dd-b156-b6e5f1d03465) and [Planetary Computer ingestion notes](https://sentinel-hub.github.io/titiler-openeo/planetary-computer/).

An additional **offline cost gate** is provided:

    python scripts/stac_cost_budget.py fixtures/stac-cost-budget-synthetic.json

It accepts explicitly declared estimates of number of requests, remote bytes, compute seconds and analyst minutes, as well as user-provided per-unit USD rates and a budget ceiling. The fixed policy caps requests at 100, transfer estimates at 2 GB, compute at 3,600 seconds, review time at 240 minutes, and approved budget ceilings at $10,000. Each cost is rounded upward to the nearest cent. Exceeding the ceiling is blocked. **Rates are purely hypothetical in the fixture; the tool does not monitor provider bills, enforce an actual egress quota, authorize API access, buy imagery or permit client delivery.** Production must use measured billing, authenticated budgets and a separate enforcement control plane.

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
