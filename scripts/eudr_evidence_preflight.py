#!/usr/bin/env python3
"""EUDR plot-evidence preflight: local-only, fail-closed, never a legal verdict.

This is not a DDS generator, TRACES client, deforestation analysis, or a
substitute for an independent risk assessment under the applicable regulation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys

MAX_INPUT_BYTES = 1024 * 1024
MAX_PLOTS = 200
MAX_VERTICES = 10000
COMMODITIES = frozenset({"cattle", "cocoa", "coffee", "oil_palm", "rubber", "soya", "wood"})
HEX_SHA256 = re.compile(r"^[a-f0-9]{64}$")
OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _pairs_unique(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _reject_nonfinite(value):
    raise ValueError("nonfinite JSON constant")


def _coordinates(coords, *, close=False):
    """Structural coordinate checks only; NOT a topology or accuracy assessment."""
    if not isinstance(coords, list) or not coords or len(coords) > MAX_VERTICES:
        return False
    for pos in coords:
        if not isinstance(pos, list) or len(pos) != 2:
            return False
        x, y = pos
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in (x, y)):
            return False
        if not (-180 <= x <= 180 and -90 <= y <= 90):
            return False
    return (not close) or (len(coords) >= 4 and coords[0] == coords[-1])


def _validate_geometry(geometry):
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        return False
    kind, coords = geometry["type"], geometry["coordinates"]
    if kind == "Point":
        return _coordinates([coords])
    if kind == "Polygon":
        return (isinstance(coords, list) and 0 < len(coords) <= 100
                and all(_coordinates(ring, close=True) for ring in coords))
    if kind == "MultiPolygon":
        return (isinstance(coords, list) and 0 < len(coords) <= 100
                and all(isinstance(poly, list) and 0 < len(poly) <= 100
                        and all(_coordinates(ring, close=True) for ring in poly)
                        for poly in coords))
    return False


def assess(record):
    """Return a redacted, stable exception packet without declaring compliance."""
    if not isinstance(record, dict):
        raise ValueError("expected JSON object")
    issues = []
    def issue(code):
        if code not in issues:
            issues.append(code)

    if record.get("schema_version") != 1:
        issue("unsupported-schema-version")
    batch = record.get("batch_id")
    if not isinstance(batch, str) or not OPAQUE_ID.fullmatch(batch):
        issue("invalid-batch-id")
    commodity = record.get("commodity")
    if commodity not in COMMODITIES:
        issue("unsupported-or-unverified-commodity")
    product_scope = record.get("product_scope")
    if product_scope != "human-review-pending":
        issue("product-scope-not-reviewed")
    production = record.get("production_date_or_range")
    if not isinstance(production, str) or not production.strip() or len(production) > 80:
        issue("missing-production-period")
    country = record.get("country_of_production")
    if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country):
        issue("invalid-production-country")
    if record.get("crs") != "EPSG:4326":
        issue("unsupported-or-missing-coordinate-system")
    plots = record.get("plots")
    if not isinstance(plots, list) or not plots or len(plots) > MAX_PLOTS:
        issue("invalid-plot-count")
        plots = []
    seen = set()
    output_plots = []
    for index, plot in enumerate(plots):
        flags = []
        def add(code):
            if code not in flags:
                flags.append(code)
        if not isinstance(plot, dict):
            issue("invalid-plot-record")
            continue
        ident = plot.get("plot_id")
        if not isinstance(ident, str) or not OPAQUE_ID.fullmatch(ident) or ident in seen:
            add("invalid-or-duplicate-plot-id")
        else:
            seen.add(ident)
        geom = plot.get("geometry")
        if not _validate_geometry(geom):
            add("invalid-geojson-geometry-structure")
        area_ha = plot.get("declared_area_ha")
        valid_area = (area_ha is not None and not isinstance(area_ha, bool)
                      and isinstance(area_ha, (int, float))
                      and math.isfinite(area_ha) and area_ha > 0)
        if not valid_area:
            add("unverified-plot-area")
        # Above four hectares, non-cattle EUDR plot geometry generally requires polygons.
        if valid_area and area_ha > 4 and commodity != "cattle" and isinstance(geom, dict) and geom.get("type") not in ("Polygon", "MultiPolygon"):
            add("polygon-required-for-declared-area")
        if commodity == "cattle":
            add("cattle-establishment-chain-not-verified")
        if isinstance(geom, dict) and geom.get("type") in ("Polygon", "MultiPolygon"):
            add("polygon-topology-area-and-accuracy-unverified")
        elif isinstance(geom, dict) and geom.get("type") == "Point":
            add("point-precision-and-accuracy-unverified")
        source = plot.get("source")
        if not isinstance(source, dict):
            add("missing-source-provenance")
        else:
            digest = source.get("sha256")
            ref = source.get("reference")
            acquired = source.get("acquired_date")
            if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
                add("missing-immutable-source-digest")
            if not isinstance(ref, str) or not ref.startswith("https://") or len(ref) > 500 or "@" in ref:
                add("unverified-or-unsafe-source-reference")
            if not isinstance(acquired, str) or not ISO_DATE.fullmatch(acquired):
                add("missing-source-acquisition-date")
            if source.get("rights_status") != "independently-reviewed":
                add("source-rights-review-required")
        if plot.get("producer_plot_linkage_verified") is not True:
            add("supplier-to-plot-linkage-unverified")
        output_plots.append({"plot_id": ident if isinstance(ident, str) and OPAQUE_ID.fullmatch(ident) else "invalid-" + str(index),
                             "exceptions": sorted(flags)})
        issues.extend(flag for flag in flags if flag not in issues)
    # Explicitly refuse to turn self-declared metadata into a compliance decision.
    for field in ("deforestation_free", "legally_produced", "dds_submitted", "compliant"):
        if record.get(field) is True:
            issue("unverified-compliance-claim")
    return {
        "schema_version": 1,
        "batch_id": batch if isinstance(batch, str) and OPAQUE_ID.fullmatch(batch) else None,
        "commodity": commodity if commodity in COMMODITIES else None,
        "status": "BLOCKED" if issues else "REVIEW_REQUIRED",
        "exceptions": sorted(issues),
        "plots": output_plots,
        "human_review_required": True,
        "deforestation_assessed": False,
        "compliance_determined": False,
        "dds_generated": False,
        "traces_submitted": False,
        "note": "Structural metadata validation only. Geolocation accuracy, source authenticity, production, deforestation, legality, and operator obligations require independent assessment."
    }


def load(path: Path):
    data = path.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds limit")
    return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs_unique,
                      parse_constant=_reject_nonfinite)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        record = load(args.input)
        result = assess(record)
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 0 if result["status"] == "REVIEW_REQUIRED" else 1
    except (OSError, UnicodeError, ValueError, TypeError):
        print("eudr-preflight-failed: invalid input", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
