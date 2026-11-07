#!/usr/bin/env python3
"""Bounded, opt-in inspection of the USFWS NWI ArcGIS wetlands layer.

This module does NOT validate completeness, legal reuse, parcel boundaries,
wetland jurisdiction, source edition, or suitability for client delivery.
Network is disabled unless the CLI explicitly receives --network.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import (
    HTTPRedirectHandler, Request, build_opener,
)

LAYER_URL = (
    "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/"
    "services/Wetlands/MapServer/0"
)
QUERY_URL = LAYER_URL + "/query"
PAGE_SIZE = 100
MAX_FEATURES = 200
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_VERTICES = 30000
MAX_OUTPUT_BYTES = 12 * 1024 * 1024


class SourceInspectionError(ValueError):
    """Unverified or incomplete source acquisition must fail closed."""


class _DenyRedirects(HTTPRedirectHandler):
    def redirect_request(self, request: Any, fp: Any, code: Any, msg: Any,
                         headers: Any, newurl: Any) -> None:
        raise SourceInspectionError("External redirect rejected")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceInspectionError("Duplicate JSON key")
        result[key] = value
    return result


def _decode_json(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(
                SourceInspectionError("Non-finite JSON rejected")
            ),
        )
    except (UnicodeError, ValueError) as exc:
        raise SourceInspectionError("Invalid JSON source payload") from exc
    if not isinstance(data, dict) or "error" in data:
        raise SourceInspectionError("Source request failed or malformed")
    return data


def _http_json(url: str) -> dict[str, Any]:
    """Fetch only an allowlisted HTTPS ArcGIS endpoint, with bounded body."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "fwspublicservices.wim.usgs.gov"
        or parsed.path not in (
            urlsplit(LAYER_URL).path,
            urlsplit(QUERY_URL).path,
        )
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise SourceInspectionError("Source endpoint not allowlisted")
    request = Request(url, headers={
        "Accept": "application/json,application/geo+json",
        "User-Agent": "zqm-computing-source-inspection/0.1",
    }, method="GET")
    opener = build_opener(_DenyRedirects())
    try:
        with opener.open(request, timeout=12) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise SourceInspectionError("Remote source unreachable or rejected") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise SourceInspectionError("Remote response exceeds safety limit")
    return _decode_json(body)


def _bbox(values: list[float] | tuple[float, ...]) -> tuple[float, float, float, float]:
    if len(values) != 4 or any(
        isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x)
        for x in values
    ):
        raise SourceInspectionError("Expected four finite bounding-box coordinates")
    x0, y0, x1, y1 = (float(v) for v in values)
    if not (
        -88.2 <= x0 < x1 <= -79.0
        and 24.0 <= y0 < y1 <= 31.2
        and x1 - x0 <= .02
        and y1 - y0 <= .02
    ):
        raise SourceInspectionError("Bounding box outside bounded Florida pilot")
    return x0, y0, x1, y1


def _url(params: dict[str, str], *, metadata: bool = False) -> str:
    base = LAYER_URL if metadata else QUERY_URL
    return base + "?" + urlencode(params)


def _query_filters(box: tuple[float, ...]) -> dict[str, str]:
    return {
        "geometry": ",".join(format(x, ".8f") for x in box),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
    }


def _verify_layer(layer: dict[str, Any]) -> None:
    if type(layer.get("id")) is not int or layer["id"] != 0 or layer.get("geometryType") != "esriGeometryPolygon":
        raise SourceInspectionError("NWI layer identity or geometry changed")
    if layer.get("name") != "Wetlands":
        raise SourceInspectionError("NWI layer name changed")
    if "Query" not in {item.strip() for item in str(layer.get("capabilities", "")).split(",")}:
        raise SourceInspectionError("NWI layer lacks query capability")
    if "geojson" not in {item.strip().casefold() for item in str(layer.get("supportedQueryFormats", "")).split(",")}:
        raise SourceInspectionError("NWI layer lacks GeoJSON support")
    fields = {
        x.get("name") for x in layer.get("fields", []) if isinstance(x, dict)
    }
    if not {"OBJECTID", "ATTRIBUTE", "WETLAND_TYPE"} <= fields:
        raise SourceInspectionError("NWI fields are incompatible")
    max_records = layer.get("maxRecordCount")
    if type(max_records) is not int or max_records < PAGE_SIZE:
        raise SourceInspectionError("NWI page size exceeds service limits")
    advanced = layer.get("advancedQueryCapabilities")
    if not isinstance(advanced, dict) or advanced.get("supportsPagination") is not True:
        raise SourceInspectionError("NWI pagination support not confirmed")


def _validate_coords(geometry: Any) -> int:
    if not isinstance(geometry, dict):
        raise SourceInspectionError("Missing geometry")
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Polygon":
        polygons = [coordinates]
    elif kind == "MultiPolygon":
        polygons = coordinates
    else:
        raise SourceInspectionError("Non-polygon NWI feature")
    if not isinstance(polygons, list) or not polygons:
        raise SourceInspectionError("Missing polygons")
    total = 0
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise SourceInspectionError("Missing polygon rings")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise SourceInspectionError("Invalid polygon ring")
            if ring[0] != ring[-1]:
                raise SourceInspectionError("Unclosed polygon ring")
            for pair in ring:
                if not isinstance(pair, list) or len(pair) not in (2, 3):
                    raise SourceInspectionError("Invalid coordinate tuple")
                x, y = pair[:2]
                if any(
                    isinstance(n, bool) or not isinstance(n, (int, float))
                    or not math.isfinite(n)
                    for n in pair
                ) or not (-180 <= x <= 180 and -90 <= y <= 90):
                    raise SourceInspectionError("Invalid geographic coordinates")
                total += 1
                if total > MAX_VERTICES:
                    raise SourceInspectionError("Polygon vertex budget exceeded")
    return total


def collect(
    bbox: list[float] | tuple[float, ...],
    fetch: Callable[[str], dict[str, Any]],
    *,
    obtained_at: str | None = None,
) -> dict[str, Any]:
    """Return one bounded source snapshot and a NON-APPROVED provenance record.

    Only the injected fetch callback can access the network; no file writes.
    """
    box = _bbox(bbox)
    _verify_layer(fetch(_url({"f": "json"}, metadata=True)))
    common = _query_filters(box)
    count_payload = fetch(_url({**common, "returnCountOnly": "true", "f": "json"}))
    count = count_payload.get("count")
    if type(count) is not int or count < 0 or count > MAX_FEATURES:
        raise SourceInspectionError("Unconfirmed or oversized NWI result count")
    if obtained_at is None:
        obtained_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not isinstance(obtained_at, str) or not obtained_at.endswith("Z"):
        raise SourceInspectionError("Expected explicit UTC retrieval time")
    seen: set[int] = set()
    last_oid: int | None = None
    vertices_seen = 0
    rows: list[dict[str, Any]] = []
    for offset in range(0, count, PAGE_SIZE):
        requested = min(PAGE_SIZE, count - offset)
        query = {
            **common, "f": "geojson", "outSR": "4326",
            "outFields": "OBJECTID,ATTRIBUTE,WETLAND_TYPE",
            "returnGeometry": "true", "returnZ": "false", "returnM": "false",
            "orderByFields": "OBJECTID ASC",
            "resultOffset": str(offset), "resultRecordCount": str(requested),
        }
        page = fetch(_url(query))
        page_features = page.get("features")
        if (
            page.get("type") != "FeatureCollection"
            or not isinstance(page_features, list)
            or len(page_features) != requested
            or page.get("exceededTransferLimit") not in (None, False)
        ):
            raise SourceInspectionError("NWI page incomplete or truncated")
        crs = page.get("crs")
        # GeoJSON normally omits CRS (WGS84 longitude/latitude by RFC 7946).
        # An explicit contradictory CRS must not pass an EPSG:4326 request.
        if crs is not None:
            if not isinstance(crs, dict) or crs.get("type") != "name" or not isinstance(crs.get("properties"), dict) or crs["properties"].get("name") not in ("EPSG:4326", "OGC:CRS84", "urn:ogc:def:crs:OGC:1.3:CRS84"):
                raise SourceInspectionError("Unexpected GeoJSON coordinate reference system")
        for feature in page_features:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise SourceInspectionError("Invalid NWI feature payload")
            props = feature.get("properties")
            if not isinstance(props, dict):
                raise SourceInspectionError("NWI feature lacks attributes")
            oid = props.get("OBJECTID")
            if type(oid) is not int or oid in seen or (last_oid is not None and oid <= last_oid):
                raise SourceInspectionError("Missing/duplicate/out-of-order NWI feature identifier")
            last_oid = oid
            seen.add(oid)
            for field in ("ATTRIBUTE", "WETLAND_TYPE"):
                if not isinstance(props.get(field), str) or not props[field].strip():
                    raise SourceInspectionError("Missing or invalid NWI wetland attributes")
            vertices_seen += _validate_coords(feature.get("geometry"))
            if vertices_seen > MAX_VERTICES:
                raise SourceInspectionError("Total NWI polygon vertex budget exceeded")
            rows.append({
                "type": "Feature",
                "id": oid,
                "properties": {
                    "OBJECTID": oid,
                    "ATTRIBUTE": props.get("ATTRIBUTE"),
                    "WETLAND_TYPE": props.get("WETLAND_TYPE"),
                },
                "geometry": feature["geometry"],
            })
    if len(rows) != count:
        raise SourceInspectionError("NWI pagination reconciliation failed")
    normalized = {
        "type": "FeatureCollection",
        "features": rows,
    }
    normalized_sha256 = sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "status": "inspection-only-not-screened",
        "coverage_state": "unverified",
        "reuse_rights": "unverified",
        "human_review": "pending",
        "regulatory_determination": False,
        "source": {
            "name": "USFWS National Wetlands Inventory",
            "service": LAYER_URL,
            "layer_id": 0,
            "request_bbox_epsg4326": list(box),
            "requested_output_crs": "EPSG:4326",
            "retrieved_at_utc": obtained_at,
            "features_reconciled": count,
            "normalized_geojson_sha256": normalized_sha256,
            "feature_pagination_integrity": "count-and-ordered-unique-ids-checked; point-in-time-snapshot-unverified",
            "feature_vertices_checked": vertices_seen,
            "limitations": (
                "Query result is not proof of mapping completeness, legal jurisdiction, "
                "absence of wetlands, reuse rights, current edition or professional clearance."
            ),
        },
        "feature_collection": normalized,
    }


def publish_snapshot(out: Path, snapshot: dict[str, Any]) -> str:
    """Write one JSON snapshot atomically without replacing existing outputs."""
    if out.suffix.casefold() != ".json" or out.is_symlink():
        raise SourceInspectionError("Output must be a non-symlink JSON file")
    if not out.parent.is_dir() or out.parent.is_symlink() or out.exists():
        raise SourceInspectionError("Output parent invalid or destination exists")
    raw = (json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False)
           + "\n").encode("utf-8")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise SourceInspectionError("Snapshot exceeds publication size limit")
    fd, staged = tempfile.mkstemp(prefix=".nwi-inspect-", dir=out.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        # Atomic create-only publication: independent of check/creation timing.
        os.link(staged, out)
        return sha256(raw).hexdigest()
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", nargs=4, type=float, required=True,
                        metavar=("W", "S", "E", "N"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--network", action="store_true",
                        help="Explicitly permit public USFWS endpoint GETs")
    args = parser.parse_args(argv)
    if not args.network:
        print("No network request made. This command requires explicit --network.")
        return 2
    try:
        snapshot = collect(args.bbox, _http_json)
        digest = publish_snapshot(args.out, snapshot)
    except (ValueError, OSError, RuntimeError):
        print("NWI inspection failed closed: source not verified or output unavailable")
        return 1
    print("Inspection-only NWI snapshot written. SHA256=" + digest)
    print("Not legally screened, commercially cleared, or delivered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
