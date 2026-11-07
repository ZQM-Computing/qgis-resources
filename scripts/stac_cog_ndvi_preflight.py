#!/usr/bin/env python3
"""Bounded, opt-in STAC -> Sentinel-2 COG NDVI *exploratory* preflight.

Default: NO network and NO pixels. Network requires --allow-network.
Never buys imagery, issues underwriting decisions, or claims regulatory accuracy.
Signed asset URLs and credentials are never printed or persisted.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"
MAX_ITEMS = 4
MAX_PIXELS = 250_000
MAX_BBOX_DEGREES = 0.25
MAX_SEARCH_DAYS = 31
MAX_FIXTURE_BYTES = 512 * 1024
SUPPORTED_ASSETS = ("B04", "B08", "SCL")
# Planetary Computer Sentinel assets are served from Microsoft Azure Blob.
ASSET_HOST = "sentinel2l2a01.blob.core.windows.net"
ASSET_CONTAINER_PATH = "/sentinel2-l2/"
ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PreflightError(ValueError):
    pass


def check_bbox(values):
    if not isinstance(values, (list, tuple)) or len(values) != 4:
        raise PreflightError("bbox must contain west,south,east,north")
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) for v in values):
        raise PreflightError("bbox values must be finite numbers")
    west, south, east, north = [float(v) for v in values]
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise PreflightError("invalid geographic bbox or antimeridian crossing")
    if east - west > MAX_BBOX_DEGREES or north - south > MAX_BBOX_DEGREES:
        raise PreflightError("bbox exceeds bounded pilot area")
    return (west, south, east, north)


def check_dates(start, end):
    if not all(isinstance(v, str) and ISO_DAY.fullmatch(v) for v in (start, end)):
        raise PreflightError("date range must be YYYY-MM-DD")
    try:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as exc:
        raise PreflightError("invalid calendar date") from exc
    if a > b or (b - a).days > MAX_SEARCH_DAYS:
        raise PreflightError("date window exceeds bounded search period")
    return f"{a.isoformat()}/{b.isoformat()}"


def _safe_href(href):
    """Allow only expected Azure Blob HTTPS hosts, not arbitrary STAC URLs."""
    if not isinstance(href, str) or len(href) > 4096:
        return False
    if any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in href):
        return False
    try:
        u = urlsplit(href)
        host = u.hostname
        port = u.port
    except ValueError:
        return False
    return (u.scheme == "https" and isinstance(host, str)
            and host == ASSET_HOST and u.path.startswith(ASSET_CONTAINER_PATH)
            and u.username is None and u.password is None
            and port in (None, 443) and not u.fragment)


def validate_item(item):
    """Validate scene metadata without trusting or exposing signed hrefs."""
    if not isinstance(item, dict) or item.get("collection") != COLLECTION:
        raise PreflightError("unexpected collection")
    identifier = item.get("id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,150}", identifier):
        raise PreflightError("invalid item identifier")
    properties = item.get("properties")
    assets = item.get("assets")
    if not isinstance(properties, dict) or not isinstance(assets, dict):
        raise PreflightError("missing STAC properties or assets")
    cloud = properties.get("eo:cloud_cover")
    if isinstance(cloud, bool) or not isinstance(cloud, (float, int)) or not math.isfinite(cloud) or not 0 <= cloud <= 100:
        raise PreflightError("missing or invalid scene cloud coverage")
    dt = properties.get("datetime")
    if not isinstance(dt, str) or len(dt) > 40 or not dt.endswith("Z"):
        raise PreflightError("missing canonical UTC observation timestamp")
    try:
        timestamp = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreflightError("invalid scene timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise PreflightError("scene timestamp lacks UTC reference")
    bounds = item.get("bbox")
    if not isinstance(bounds, list) or len(bounds) != 4 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in bounds
    ):
        raise PreflightError("missing or invalid scene geographic bounds")
    w, south, e, north = bounds
    if not (-180 <= w < e <= 180 and -90 <= south < north <= 90):
        raise PreflightError("unsupported scene geographic envelope")
    for band in SUPPORTED_ASSETS:
        asset = assets.get(band)
        if not isinstance(asset, dict) or not _safe_href(asset.get("href")):
            raise PreflightError("missing or unsafe signed COG asset")
    return {
        "scene_id": identifier,
        "scene_datetime_utc": dt,
        "scene_cloud_cover_percent": float(cloud),
        "asset_keys_checked": list(SUPPORTED_ASSETS),
        "asset_urls_logged": False,
        "license_and_use_rights_verified": False,
        "scene_aoi_cloud_free_verified": False,
        "source_authenticity_verified": False,
    }


def select_item(items, maximum_cloud_percent=20, *, bbox=None, period=None):
    if not isinstance(items, list) or not 0 < len(items) <= MAX_ITEMS:
        raise PreflightError("no bounded search results")
    if isinstance(maximum_cloud_percent, bool) or not isinstance(maximum_cloud_percent, (int, float)) or not 0 <= maximum_cloud_percent <= 100:
        raise PreflightError("invalid scene cloud ceiling")
    candidates = []
    for item in items:
        metadata = validate_item(item)
        if bbox is not None:
            west, south, east, north = check_bbox(bbox)
            iw, isouth, ie, inorth = item["bbox"]
            # A rectangular summary requires full scene-envelope coverage;
            # an overlap-only search result would misstate AOI completeness.
            if iw > west or ie < east or isouth > south or inorth < north:
                continue
        if period is not None:
            start, end = period.split("/")
            if not start <= metadata["scene_datetime_utc"][:10] <= end:
                continue
        if metadata["scene_cloud_cover_percent"] <= maximum_cloud_percent:
            candidates.append((metadata["scene_cloud_cover_percent"], metadata["scene_datetime_utc"], metadata["scene_id"], item, metadata))
    if not candidates:
        raise PreflightError("no scene met metadata filter; coverage unverified")
    _, _, _, item, metadata = min(candidates, key=lambda x: x[:3])
    return item, metadata


def search_scene(bbox, period, cloud_limit):
    """One bounded STAC search, automatically signed; explicit network opt-in caller only."""
    from pystac_client import Client
    import planetary_computer
    catalog = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    search = catalog.search(
        collections=[COLLECTION], bbox=list(bbox), datetime=period,
        query={"eo:cloud_cover": {"lte": cloud_limit}}, max_items=MAX_ITEMS,
    )
    return [item.to_dict() for item in search.items()]


def _window_edge(value, *, upper):
    """Snap near-integer grid edges before conservative floor/ceil.

    Affine inverse transforms can return 9.00000000000034 for an exact
    pixel boundary. Without a tolerance, ceil expands the window one pixel.
    Nonaligned bounds are still conservatively expanded to cover the AOI.
    """
    if not math.isfinite(value):
        raise PreflightError("nonfinite raster window coordinate")
    nearest = round(value)
    if math.isclose(value, nearest, rel_tol=0.0, abs_tol=1e-7):
        return int(nearest)
    return math.ceil(value) if upper else math.floor(value)


def calculate_window_ndvi(item, bbox):
    """Read only one bounded Sentinel scene window via Rasterio/GDAL HTTP range I/O.

    This intentionally reports an *exploratory DN-ratio*, without claiming
    radiometric harmonization or scientific calibration; SCL is a scene mask,
    not field-verified canopy/deforestation evidence.
    """
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds, Window

    for key in SUPPORTED_ASSETS:
        if not _safe_href(item["assets"][key]["href"]):
            raise PreflightError("unexpected remote asset URL")
    nir_url = item["assets"]["B08"]["href"]
    red_url = item["assets"]["B04"]["href"]
    scl_url = item["assets"]["SCL"]["href"]

    # This restricts what our own application requests; GDAL may issue multiple
    # byte-range requests for tiles/overviews and may read auxiliary metadata.
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff"):
        with rasterio.open(nir_url) as nir, rasterio.open(red_url) as red, rasterio.open(scl_url) as scl:
            if not nir.crs or not red.crs or not scl.crs or nir.count != 1 or red.count != 1 or scl.count != 1:
                raise PreflightError("missing CRS or unexpected raster bands")
            left, bottom, right, top = transform_bounds("EPSG:4326", nir.crs, *bbox, densify_pts=21)
            raw = from_bounds(left, bottom, right, top, transform=nir.transform)
            col0, row0 = max(0, _window_edge(raw.col_off, upper=False)), max(0, _window_edge(raw.row_off, upper=False))
            col1, row1 = min(nir.width, _window_edge(raw.col_off + raw.width, upper=True)), min(nir.height, _window_edge(raw.row_off + raw.height, upper=True))
            width, height = col1 - col0, row1 - row0
            if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                raise PreflightError("empty or oversized raster window")
            if (raw.col_off < -1e-7 or raw.row_off < -1e-7
                    or raw.col_off + raw.width > nir.width + 1e-7
                    or raw.row_off + raw.height > nir.height + 1e-7):
                raise PreflightError("scene raster lacks full requested AOI coverage")
            window = Window(col0, row0, width, height)
            with WarpedVRT(red, crs=nir.crs, transform=nir.transform,
                           width=nir.width, height=nir.height,
                           resampling=Resampling.bilinear) as red_aligned:
                with WarpedVRT(scl, crs=nir.crs, transform=nir.transform,
                               width=nir.width, height=nir.height,
                               resampling=Resampling.nearest) as scl_aligned:
                    n = nir.read(1, window=window, masked=True).astype("float32")
                    r = red_aligned.read(1, window=window, masked=True).astype("float32")
                    c = scl_aligned.read(1, window=window, masked=True)
            # SCL 4: vegetation, 5: not vegetated, 6: water. Cloud/shadow/
            # cirrus, snow and unclassified pixels are excluded.
            allowed = np.isin(np.asarray(c), [4, 5, 6])
            valid = allowed & (~np.ma.getmaskarray(n)) & (~np.ma.getmaskarray(r)) & (~np.ma.getmaskarray(c))
            valid &= (np.asarray(n) > 0) & (np.asarray(r) > 0)
            valid &= np.isfinite(n) & np.isfinite(r)
            denom = np.asarray(n) + np.asarray(r)
            valid &= denom > 0
            count = int(valid.sum())
            if not count:
                raise PreflightError("no usable clear pixels; optical analysis unavailable")
            ndvi = (np.asarray(n)[valid] - np.asarray(r)[valid]) / denom[valid]
            return {
                "status": "EXPLORATORY_REVIEW_ONLY",
                "method": "Sentinel-2 B08/B04 digital-number ratio with SCL 4/5/6 mask",
                "mean_ndvi_dn_ratio": round(float(np.mean(ndvi)), 6),
                "valid_pixel_count": count,
                "read_window_pixel_count": int(width * height),
                "valid_fraction_of_window": round(count / (width * height), 6),
                "aoi_polygon_mask_applied": False,
                "radiometric_offset_and_scale_verified": False,
                "imagery_reuse_rights_verified": False,
                "cloud_free_aoi_verified": False,
                "raster_full_bbox_coverage_checked": True,
                "radiometric_correction_required": True,
                "deforestation_determined": False,
                "underwriting_liability_estimated": False,
                "human_review_required": True,
                "asset_urls_logged": False,
            }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PreflightError("duplicate STAC JSON key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("W", "S", "E", "N"))
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--cloud-limit", type=float, default=20)
    parser.add_argument("--fixture", type=Path, help="Local signed STAC test object, NO remote reads permitted")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--budget-plan", type=Path, help="Required for live remote access; declared cost assumptions only")
    parser.add_argument("--stream-window", action="store_true", help="Only when --allow-network, max 250k pixels")
    args = parser.parse_args(argv)
    try:
        bbox = check_bbox(args.bbox)
        period = check_dates(args.start, args.end)
        if args.fixture is not None and args.allow_network:
            raise PreflightError("fixture and network mode are mutually exclusive")
        if args.allow_network and args.budget_plan is None:
            raise PreflightError("live requests require explicit local budget plan")
        if args.stream_window and not args.allow_network:
            raise PreflightError("streaming requires explicit network opt-in")
        if args.fixture is not None:
            with args.fixture.open("rb") as handle:
                raw = handle.read(MAX_FIXTURE_BYTES + 1)
            if len(raw) > MAX_FIXTURE_BYTES:
                raise PreflightError("oversized local STAC fixture")
            item = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(PreflightError("nonfinite JSON")))
            items = [item]
        elif args.allow_network:
            from stac_cost_budget import _pairs_unique, calculate, MAX_FILE_BYTES
            with args.budget_plan.open("rb") as handle:
                budget_raw = handle.read(MAX_FILE_BYTES + 1)
            if len(budget_raw) > MAX_FILE_BYTES:
                raise PreflightError("budget plan exceeds file size limit")
            budget = calculate(json.loads(budget_raw.decode("utf-8"), object_pairs_hook=_pairs_unique,
                                          parse_constant=lambda _: (_ for _ in ()).throw(PreflightError("nonfinite budget"))))
            if budget["decision"] != "WITHIN_DECLARED_BUDGET_ONLY" or budget["remote_requests"] < 1:
                raise PreflightError("declared remote budget insufficient")
            items = search_scene(bbox, period, args.cloud_limit)
        else:
            raise PreflightError("network disabled by default; provide --fixture")
        selected, metadata = select_item(items, args.cloud_limit, bbox=bbox, period=period)
        output = {
            "status": "METADATA_PREFLIGHT_ONLY",
            "source": STAC_URL,
            "collection": COLLECTION,
            "bbox": list(bbox),
            "period": period,
            "scene": metadata,
            "commercial_delivery_authorized": False,
            "purchased_imagery": False,
            "human_review_required": True,
        }
        if args.allow_network:
            output["declared_budget_review"] = budget
        if args.stream_window:
            output["pixel_window"] = calculate_window_ndvi(selected, bbox)
        print(json.dumps(output, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, ImportError, RuntimeError, UnicodeError):
        print("stac-cog-preflight-blocked: invalid request, metadata or remote source", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
