"""Bounded COG HTTP range diagnostic; *not* a GDAL egress limiter.

Each explicitly requested read checks strict HTTP 206 partial-content semantics.
It never follows redirects, authenticates source identity, or measures
subsequent Rasterio/GDAL requests. Signed URLs are never included in output.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request

from stac_cog_ndvi_preflight import _safe_href

PROBE_BYTES = 4096
MAX_PROBE_BYTES = 4096
CONTENT_RANGE = re.compile(r"^bytes 0-(\d+)/(\d+)$")


class RangeProbeError(ValueError):
    pass


class _DenyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RangeProbeError("COG redirect blocked")


def _open_request(request, *, timeout):
    # Disable environment-driven HTTP proxies as an implicit remote hop.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _DenyRedirects(),
    )
    return opener.open(request, timeout=timeout)


def probe_range(url, *, transport=None):
    """Read exactly first 4096 bytes and verify response boundaries.

    Transport dependency is injectable to test protocol behavior offline.
    A successful probe must NOT be interpreted as a bound on GDAL traffic.
    """
    if not _safe_href(url):
        raise RangeProbeError("URL outside approved Sentinel-2 asset origin")
    request = urllib.request.Request(
        url, headers={"Range": "bytes=0-4095", "Accept-Encoding": "identity"},
        method="GET",
    )
    opener = transport or _open_request
    try:
        with opener(request, timeout=8) as response:
            status = response.getcode()
            if status != 206:
                raise RangeProbeError("server did not honor bounded partial-content request")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise RangeProbeError("compressed HTTP range response unsupported")
            value = response.headers.get("Content-Range", "")
            matched = CONTENT_RANGE.fullmatch(value.strip())
            if not matched:
                raise RangeProbeError("malformed or unbounded Content-Range")
            last, total = (int(matched.group(1)), int(matched.group(2)))
            if last != PROBE_BYTES - 1 or total < PROBE_BYTES:
                raise RangeProbeError("unexpected Content-Range extent")
            length = response.headers.get("Content-Length")
            if length is None or not length.isascii() or not length.isdecimal() or int(length) != PROBE_BYTES:
                raise RangeProbeError("missing or wrong Content-Length")
            data = response.read(MAX_PROBE_BYTES + 1)
            if len(data) != PROBE_BYTES:
                raise RangeProbeError("short or overflowing range response")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        # Exceptions from signed URLs may include credentials; don't repeat.
        raise RangeProbeError("remote range probe failed") from None
    if data[:4] not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        raise RangeProbeError("unexpected TIFF/BigTIFF header signature")
    return {
        "status": "BOUNDED_RANGE_DIAGNOSTIC_ONLY",
        "request_count_observed_by_probe": 1,
        "payload_bytes_observed_by_probe": len(data),
        "range_supported_on_tested_asset": True,
        "redirects_accepted": False,
        "asset_url_in_output": False,
        "full_gdal_request_and_egress_metering_established": False,
        "origin_authenticity_verified": False,
        "commercial_delivery_authorized": False,
    }


def probe_scene_assets(item, *, transport=None):
    """Probe all three Sentinel-2 bands, failing closed on partial success.

    The returned byte count covers these probes only, never STAC discovery
    or GDAL requests. Do not return per-asset URL or signed token data.
    """
    if not isinstance(item, dict) or not isinstance(item.get("assets"), dict):
        raise RangeProbeError("scene missing required COG assets")
    outcomes = {}
    for band in ("B04", "B08", "SCL"):
        asset = item["assets"].get(band)
        if not isinstance(asset, dict):
            raise RangeProbeError("scene missing COG band")
        outcome = probe_range(asset.get("href"), transport=transport)
        outcomes[band] = {
            "range_supported": outcome["range_supported_on_tested_asset"],
            "payload_bytes": outcome["payload_bytes_observed_by_probe"],
        }
    return {
        "status": "THREE_BAND_BOUNDED_RANGE_DIAGNOSTIC_ONLY",
        "band_order": ["B04", "B08", "SCL"],
        "bands": outcomes,
        "probe_request_count": 3,
        "probe_payload_bytes": sum(x["payload_bytes"] for x in outcomes.values()),
        "redirects_accepted": False,
        "asset_urls_logged": False,
        "full_stac_and_gdal_request_metering_established": False,
        "total_cloud_egress_or_cost_measured": False,
        "commercial_delivery_authorized": False,
    }
