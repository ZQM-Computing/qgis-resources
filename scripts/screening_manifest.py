#!/usr/bin/env python3
"""Read-only, dependency-free metadata contract for preliminary GIS screening.

Validating a manifest does not verify remote sources, spatial correctness,
licenses, professional conclusions, or client-delivery authorization.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import PurePosixPath, Path
import re
from typing import Any
from urllib.parse import urlsplit

MAX_MANIFEST_BYTES = 1024 * 1024
COVERAGE_STATES = frozenset({"verified", "partial", "missing", "unavailable", "unverified"})
ORIGINS = frozenset({"synthetic", "external"})
RIGHTS_STATES = frozenset({"approved", "restricted", "unverified"})
TIERS = frozenset({"preliminary", "quantified", "specialist-reviewed"})
BOUNDARY_BASES = frozenset({"synthetic-not-surveyed", "public-source-not-surveyed", "customer-supplied-unverified"})
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _nonempty(value: Any) -> bool:
    """Return whether a metadata value is a nonblank string."""
    return isinstance(value, str) and bool(value.strip())


def _date(value: Any) -> bool:
    """Accept only canonical ISO calendar dates without time components."""
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _utc_time(value: Any) -> bool:
    """Require an ISO timestamp with an explicit zero UTC offset."""
    if not _nonempty(value) or "T" not in value:
        return False
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return instant.tzinfo is not None and instant.utcoffset() == timedelta(0)


def _source_reference(origin: str, value: Any) -> bool:
    """Check fixture confinement syntax or credential-free HTTPS source syntax."""
    if not _nonempty(value):
        return False
    if origin == "synthetic":
        if "\\" in value or "://" in value or value.startswith("/"):
            return False
        path = PurePosixPath(value)
        return len(path.parts) > 1 and path.parts[0] == "fixtures" and ".." not in path.parts
    if any(ch.isspace() or ch == "\\\\" or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        parts = urlsplit(value)
        port = parts.port
        hostname = parts.hostname
    except ValueError:
        return False
    return (
        parts.scheme == "https" and bool(hostname)
        and parts.username is None and parts.password is None
        and port in (None, 443)
        and not parts.fragment
        and hostname not in {"localhost"}
        and not hostname.endswith((".localhost", ".local"))
        and "." in hostname
    )


def assess_source_state(source: dict[str, Any]) -> str:
    """Never interpret a metadata coverage claim as a spatial finding."""
    state = source.get("coverage_state")
    if state == "verified":
        return "coverage-claimed-analysis-not-performed"
    if state == "partial":
        return "partial-coverage-no-absence-inference"
    return "not-assessable"


def validate_manifest(payload: Any) -> list[str]:
    """Return stable, non-sensitive field-level errors; never mutate input."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["manifest: expected JSON object"]
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        errors.append("schema_version: expected integer 1")
    if not _nonempty(payload.get("project_id")) or not ID_PATTERN.fullmatch(payload["project_id"]):
        errors.append("project_id: expected safe opaque identifier")
    jurisdiction = payload.get("jurisdiction")
    if not isinstance(jurisdiction, dict):
        errors.append("jurisdiction: expected object")
    else:
        country = jurisdiction.get("country_code")
        if not isinstance(country, str) or re.fullmatch(r"[A-Z]{2}", country) is None:
            errors.append("jurisdiction.country_code: expected two uppercase letters")
        for field in ("region", "authority"):
            if not _nonempty(jurisdiction.get(field)):
                errors.append(f"jurisdiction.{field}: required")
    study = payload.get("study_area")
    if not isinstance(study, dict):
        errors.append("study_area: expected object")
    else:
        if not _source_reference("synthetic", study.get("reference")):
            errors.append("study_area.reference: expected fixtures/ path for synthetic pilot")
        if not _nonempty(study.get("crs")):
            errors.append("study_area.crs: required; never infer a CRS")
        if not isinstance(study.get("boundary_basis"), str) or study["boundary_basis"] not in BOUNDARY_BASES:
            errors.append("study_area.boundary_basis: invalid")
    if not isinstance(payload.get("service_tier"), str) or payload["service_tier"] not in TIERS:
        errors.append("service_tier: invalid")
    if payload.get("delivery_status") != "draft":
        errors.append("delivery_status: contract pilot must remain draft")
    if payload.get("human_review") != "pending":
        errors.append("human_review: contract pilot cannot assert approval")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        return errors + ["sources: expected nonempty list"]
    seen: set[str] = set()
    for idx, source in enumerate(sources):
        label = f"sources[{idx}]"
        if not isinstance(source, dict):
            errors.append(f"{label}: expected object")
            continue
        source_id = source.get("id")
        if not _nonempty(source_id) or not ID_PATTERN.fullmatch(source_id):
            errors.append(f"{label}.id: expected safe opaque identifier")
        elif source_id in seen:
            errors.append(f"{label}.id: duplicate identifier")
        else:
            seen.add(source_id)
        origin = source.get("origin")
        state = source.get("coverage_state")
        rights = source.get("reuse_rights")
        if not isinstance(origin, str) or origin not in ORIGINS:
            errors.append(f"{label}.origin: invalid")
        if not isinstance(state, str) or state not in COVERAGE_STATES:
            errors.append(f"{label}.coverage_state: invalid")
        if not isinstance(rights, str) or rights not in RIGHTS_STATES:
            errors.append(f"{label}.reuse_rights: invalid")
        for field in ("title", "authority", "limitations"):
            if not _nonempty(source.get(field)):
                errors.append(f"{label}.{field}: required")
        available = isinstance(state, str) and state in {"verified", "partial"}
        reference = source.get("source_ref")
        if available:
            if not isinstance(origin, str) or origin not in ORIGINS or not _source_reference(origin, reference):
                errors.append(f"{label}.source_ref: required valid origin-specific reference")
            if rights != "approved":
                errors.append(f"{label}.reuse_rights: usable coverage requires approved reuse rights")
            if not _nonempty(source.get("license")):
                errors.append(f"{label}.license: required for usable coverage")
            if not _nonempty(source.get("crs")):
                errors.append(f"{label}.crs: required for usable coverage")
            if not _utc_time(source.get("retrieved_at_utc")):
                errors.append(f"{label}.retrieved_at_utc: UTC timestamp required")
        else:
            if reference is not None or source.get("crs") is not None:
                errors.append(f"{label}: missing/unavailable/unverified coverage cannot assert source geometry")
        effective = source.get("effective_date")
        if effective is not None and not _date(effective):
            errors.append(f"{label}.effective_date: expected YYYY-MM-DD or null")
        retrieved = source.get("retrieved_at_utc")
        if retrieved is not None and not _utc_time(retrieved):
            if not available:
                errors.append(f"{label}.retrieved_at_utc: invalid UTC timestamp")
    return errors


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting duplicate keys at every nesting level."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def load_manifest(path: Path) -> Any:
    """Read at most one MiB without modifying the manifest or its sources."""
    with path.open("rb") as handle:
        content = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(content) > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest exceeds size limit")
    return json.loads(
        content.decode("utf-8"),
        object_pairs_hook=_reject_duplicates,
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("Non-finite JSON value")),
    )


def main(argv: list[str] | None = None) -> int:
    """Validate local metadata and return documented load or validation exit codes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Local manifest JSON (read-only)")
    args = parser.parse_args(argv)
    try:
        payload = load_manifest(args.manifest)
    except (OSError, UnicodeError, ValueError) as exc:
        # Do not print raw exception messages; file paths can identify clients.
        print("manifest-load-error: " + type(exc).__name__)
        return 2
    errors = validate_manifest(payload)
    for error in errors:
        print(error)
    if errors:
        return 1
    print("Manifest metadata contract valid; no spatial, source-rights or delivery approval was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
