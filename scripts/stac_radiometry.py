"""Bounded Sentinel-2 L2A radiometry metadata contract.

Corrected reflectance arithmetic is only a candidate calculation: this module
cannot authenticate product XML, verify band data processing baselines or grant
the right to use a commercial or regulatory report.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re

MAX_BYTES = 16384
SHA256 = re.compile(r"^[a-f0-9]{64}$")
SCENE = re.compile(r"^[A-Za-z0-9._-]{1,150}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RadiometryError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RadiometryError("duplicate radiometry JSON key")
        result[key] = value
    return result


def _bad_constant(value):
    raise RadiometryError("nonfinite radiometry value")


def _finite_number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate_radiometry(record, scene_id):
    """Strict metadata assertions for known L2A post-baseline-04.00 DN formula."""
    if not isinstance(record, dict) or set(record) != {
        "schema_version", "scope", "scene_id", "product_metadata_sha256",
        "product_metadata_acquired_on", "processing_baseline",
        "boa_quantification_value", "boa_add_offset_b04", "boa_add_offset_b08",
        "provider_metadata_authenticity_verified",
    }:
        raise RadiometryError("invalid radiometry contract")
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise RadiometryError("unsupported radiometry schema")
    if record["scope"] != "metadata-unverified-synthetic-or-review":
        raise RadiometryError("unsupported source verification state")
    if (not isinstance(scene_id, str) or not SCENE.fullmatch(scene_id)
            or record["scene_id"] != scene_id):
        raise RadiometryError("radiometry belongs to a different scene")
    sha = record["product_metadata_sha256"]
    if not isinstance(sha, str) or not SHA256.fullmatch(sha):
        raise RadiometryError("invalid metadata digest assertion")
    acquired = record["product_metadata_acquired_on"]
    if not isinstance(acquired, str) or not DATE.fullmatch(acquired):
        raise RadiometryError("missing metadata acquisition date")
    try:
        date.fromisoformat(acquired)
    except ValueError as exc:
        raise RadiometryError("invalid acquisition date") from exc
    if record["provider_metadata_authenticity_verified"] is not False:
        raise RadiometryError("metadata authenticity cannot be self-approved")
    baseline = record["processing_baseline"]
    if not isinstance(baseline, str) or not re.fullmatch(r"\d{2}\.\d{2}", baseline):
        raise RadiometryError("invalid processing baseline")
    if float(baseline) < 4:
        raise RadiometryError("unsupported pre-offset product baseline")
    q = record["boa_quantification_value"]
    offsets = (record["boa_add_offset_b04"], record["boa_add_offset_b08"])
    if not _finite_number(q, 1000, 100000):
        raise RadiometryError("invalid reflectance quantification value")
    if not all(_finite_number(value, -20000, 0) for value in offsets):
        raise RadiometryError("invalid offset bounds")
    return record


def load_radiometry(path, scene_id):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RadiometryError("radiometry file too large")
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                            parse_constant=_bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RadiometryError("invalid radiometry JSON") from exc
    return validate_radiometry(record, scene_id)


def correct_dn_arrays(nir_dn, red_dn, record):
    """Convert non-nodata DNs to surface-reflectance candidates.

    Caller provides SCL, masks and nodata checks. Supports NumPy arrays,
    including negatives (dark surface reflectance can be negative).
    """
    q = float(record["boa_quantification_value"])
    nir = (nir_dn + float(record["boa_add_offset_b08"])) / q
    red = (red_dn + float(record["boa_add_offset_b04"])) / q
    return nir, red
