#!/usr/bin/env python3
"""Synthetic 3D point-to-segment separation with explicit uncertainty.

Never represents surveyed conductor clearance, verified canopy coverage, regulatory
safety clearance, growth forecasting, wildfire risk or authorized field work.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path
import re
import sys

MAX_BYTES = 1024 * 1024
MAX_SEGMENTS = 100
MAX_SAMPLES = 2000
MAX_POSITION_ERROR_M = 100.0  # synthetic pilot bound; not a surveyed accuracy limit
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _object_no_duplicates(pairs):
    """Build a JSON object from key/value pairs, rejecting duplicate keys."""
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate input key")
        out[key] = value
    return out


def _reject_constant(value):
    """Reject nonfinite JSON constants during decoding."""
    raise ValueError("nonfinite JSON value")


def _day(value):
    """Parse a required ISO observation date or raise ValueError."""
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise ValueError("missing ISO observation date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observation date") from exc


def _distance(value, *, allow_zero=True):
    """Return a finite nonnegative measurement, optionally rejecting zero."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0
            or (not allow_zero and value == 0)):
        raise ValueError("invalid nonnegative finite measurement")
    return float(value)


def _point(value):
    """Return three finite coordinates within the synthetic metre bounds."""
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("expected three-dimensional position")
    x, y, z = value
    for number in value:
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValueError("nonfinite or invalid coordinate")
    if not (100000 <= x <= 900000 and 0 <= y <= 10000000 and -1000 <= z <= 10000):
        raise ValueError("outside restricted synthetic coordinate bounds")
    return tuple(float(n) for n in value)


def _id(record, seen):
    """Validate a record identifier and add it to the supplied uniqueness set."""
    if not isinstance(record, dict):
        raise ValueError("invalid record")
    ident = record.get("id")
    if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in seen:
        raise ValueError("duplicate or invalid identifier")
    seen.add(ident)
    return ident


def _point_to_segment(point, start, end):
    """Exact Euclidean 3D point-to-finite-segment distance, in assumed metres."""
    direction = tuple(b - a for a, b in zip(start, end))
    squared = sum(v * v for v in direction)
    if squared <= 1e-12:
        raise ValueError("zero-length segment")
    t = max(0.0, min(1.0, sum((p - a) * d for p, a, d in zip(point, start, direction)) / squared))
    closest = tuple(a + t * d for a, d in zip(start, direction))
    distance = math.sqrt(sum((p - q) ** 2 for p, q in zip(point, closest)))
    if not math.isfinite(distance):
        raise ValueError("nonfinite distance")
    return distance


def analyze(data):
    """Validate synthetic inputs and report conditional proximity candidates.

    Position errors are asserted additive bounds, not verified accuracy.
    Results never establish field clearance or authorize work orders.
    Invalid inputs raise ValueError; the input object is not modified."""
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("unsupported schema")
    if (data.get("scope") != "synthetic-only" or data.get("horizontal_crs") != "EPSG:32617"
            or data.get("vertical_reference") != "SYNTHETIC_SHARED_LOCAL_METRES"):
        raise ValueError("unsupported coordinate reference or source scope")
    if data.get("human_review") != "pending" or data.get("work_order_authorized", False) is not False:
        raise ValueError("unsupported approval")
    _day(data.get("observation_date"))
    threshold = _distance(data.get("review_threshold_m"), allow_zero=False)
    if threshold > 100:
        raise ValueError("threshold exceeds pilot maximum")
    segments = data.get("conductor_segments")
    vegetation = data.get("vegetation_samples")
    if not isinstance(segments, list) or not 1 <= len(segments) <= MAX_SEGMENTS:
        raise ValueError("missing or excessive conductor segments")
    if not isinstance(vegetation, list) or not 1 <= len(vegetation) <= MAX_SAMPLES:
        raise ValueError("missing or excessive sampled points")
    seen = set()
    parsed_lines = []
    for record in segments:
        ident = _id(record, seen)
        start, end = _point(record.get("start")), _point(record.get("end"))
        uncertainty = _distance(record.get("absolute_position_uncertainty_m"))
        if uncertainty > MAX_POSITION_ERROR_M:
            raise ValueError("segment position error exceeds pilot bound")
        if start == end:
            raise ValueError("conductor segment zero-length")
        parsed_lines.append((ident, start, end, uncertainty))
    seen = set()
    parsed_points = []
    for record in vegetation:
        ident = _id(record, seen)
        position = _point(record.get("position"))
        uncertainty = _distance(record.get("absolute_position_uncertainty_m"))
        if uncertainty > MAX_POSITION_ERROR_M:
            raise ValueError("sample position error exceeds pilot bound")
        parsed_points.append((ident, position, uncertainty))
    results = []
    for ident, start, end, line_uncertainty in parsed_lines:
        matches = []
        for sample_id, position, point_uncertainty in parsed_points:
            measured = _point_to_segment(position, start, end)
            conservative_error = line_uncertainty + point_uncertainty
            lower = max(0.0, measured - conservative_error)
            upper = measured + conservative_error
            if lower <= threshold:
                matches.append({
                    "flag_basis": "nominal-proximity" if measured <= threshold else "uncertainty-overlap",
                    "sample_id": sample_id,
                    "nominal_separation_m": round(measured, 4),
                    "conservative_lower_bound_m": round(lower, 4),
                    "conservative_upper_bound_m": round(upper, 4),
                })
        matches.sort(key=lambda m: (m["conservative_lower_bound_m"], m["sample_id"]))
        results.append({
            "segment_id": ident,
            "finding": "POTENTIAL_PROXIMITY_REVIEW" if matches else "SAMPLED_POINTS_OUTSIDE_THRESHOLD_NOT_CLEARANCE",
            "candidates": matches
        })
    results.sort(key=lambda r: r["segment_id"])
    return {
        "schema_version": 1,
        "status": "REVIEW" if any(r["candidates"] for r in results) else "INSUFFICIENT_EVIDENCE",
        "measurement": "synthetic 3D point-to-straight-segment Euclidean distance in assumed metres",
        "review_threshold_m": threshold,
        "position_error_assumptions_verified": False,
        "candidate_flag_semantics": "nominal proximity or conditional uncertainty overlap, never verified clearance",
        "segments": results,
        "sample_coverage_verified": False,
        "conductor_sag_and_motion_modeled": False,
        "absolute_geodetic_accuracy_verified": False,
        "field_clearance_verified": False,
        "work_order_authorized": False,
        "wildfire_probability_estimated": False,
        "cost_savings_estimated": False,
        "human_review_required": True,
        "limitations": "Bounds assume input absolute errors are valid and additive; they exclude model, temporal, interpolation, conductor sag and canopy sampling uncertainty. No nearby sample does not establish clearance."
    }


def main(argv=None):
    """Print a synthetic report; return 0 on completion or 1 on invalid input."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.fixture.read_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError("input too large")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_object_no_duplicates,
                          parse_constant=_reject_constant)
        result = analyze(data)
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError):
        print("synthetic-clearance-preflight-failed: invalid input", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
