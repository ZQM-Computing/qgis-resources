#!/usr/bin/env python3
"""Utility field-evidence acceptance *packet* gate (offline, metadata-only).

Checks structural completeness of independently supplied evidence references.
Never authenticates documents, observes assets, calibrates a model, or approves
clearance, maintenance, regulatory decisions, or production use.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 1024 * 1024
SHA = re.compile(r"^[a-f0-9]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FIELDS = (
    "horizontal_datum", "vertical_datum", "field_observation_method",
    "conductor_sag_review", "canopy_sampling_review", "temporal_alignment_review",
    "source_rights_review",
)


def _pairs_unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _no_nonfinite(value):
    raise ValueError("nonfinite numeric constant")


def _date(value):
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _reference(value):
    """Require a hash-identified evidence record, not a bare self-attestation."""
    return (
        isinstance(value, dict)
        and set(value) == {"document_id", "sha256", "reviewed", "reviewed_on"}
        and isinstance(value.get("document_id"), str)
        and IDENT.fullmatch(value["document_id"]) is not None
        and isinstance(value.get("sha256"), str)
        and SHA.fullmatch(value["sha256"]) is not None
        and value.get("reviewed") is True
        and _date(value.get("reviewed_on"))
    )


def assess(packet):
    """Generate a review checklist; cannot authorize use regardless of input."""
    if not isinstance(packet, dict):
        raise ValueError("expected packet object")
    if type(packet.get("schema_version")) is not int or packet["schema_version"] != 1:
        raise ValueError("unsupported schema version")
    if packet.get("scope") != "field-evidence-packet-proposal":
        raise ValueError("unsupported scope")
    if packet.get("release_approved") is not False:
        raise ValueError("approval cannot be asserted or omitted")
    blockers = []
    def block(code):
        if code not in blockers:
            blockers.append(code)
    project = packet.get("project_id")
    if not isinstance(project, str) or not IDENT.fullmatch(project):
        block("invalid-project-id")
    refs = packet.get("evidence")
    if not isinstance(refs, dict):
        refs = {}
    for name in FIELDS:
        if not _reference(refs.get(name)):
            block("evidence-required:" + name)
    if set(refs) - set(FIELDS):
        block("unrecognized-evidence-field")
    evaluation = packet.get("evaluation")
    if not isinstance(evaluation, dict):
        evaluation = {}
    for key in ("model_commit_sha", "source_dataset_sha256", "label_dataset_sha256"):
        value = evaluation.get(key)
        if not isinstance(value, str) or not SHA.fullmatch(value):
            block("immutable-reference-required:" + key)
    train = evaluation.get("development_segment_ids")
    holdout = evaluation.get("holdout_segment_ids")
    for key, items in (("development", train), ("holdout", holdout)):
        if not isinstance(items, list) or not items or len(items) > 100000:
            block("invalid-" + key + "-inventory")
        elif len(set(map(str, items))) != len(items) or not all(
            isinstance(v, str) and IDENT.fullmatch(v) for v in items
        ):
            block("invalid-" + key + "-inventory")
    if isinstance(train, list) and isinstance(holdout, list):
        if any(not isinstance(v, str) for v in train + holdout):
            block("invalid-segment-id-type")
        else:
            if set(train) & set(holdout):
                block("development-holdout-overlap")
    labels = evaluation.get("independent_reference_review")
    if not _reference(labels):
        block("independent-reference-review-required")
    if evaluation.get("blind_holdout_unlocked_only_after_model_freeze") is not True:
        block("blind-holdout-and-model-freeze-not-documented")
    if evaluation.get("prespecified_safety_thresholds_reviewed") is not True:
        block("qualified-safety-threshold-review-required")
    if evaluation.get("field_calibration_completed") is not True:
        block("field-calibration-evidence-required")
    if evaluation.get("subgroup_error_analysis_completed") is not True:
        block("subgroup-error-analysis-required")
    if evaluation.get("false_negative_review_completed") is not True:
        block("missed-hazard-review-required")
    if packet.get("authorized_reviewer_role") != "qualified-independent-utility-reviewer":
        block("qualified-independent-reviewer-role-required")
    # Structural completeness is not independent evidence authenticity.
    return {
        "schema_version": 1,
        "project_id": project if isinstance(project, str) and IDENT.fullmatch(project) else None,
        "status": "BLOCKED" if blockers else "PACKET_COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION",
        "blockers": sorted(blockers),
        "evidence_authenticity_verified": False,
        "field_accuracy_established": False,
        "operational_use_approved": False,
        "work_order_authorized": False,
        "human_approval_required": True,
        "note": "Metadata completeness only. Signed evidence, independent validation, field safety review, and authorized release remain outside this tool."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.packet.read_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError("packet too large")
        packet = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_unique,
                            parse_constant=_no_nonfinite)
        result = assess(packet)
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 0 if not result["blockers"] else 1
    except (OSError, TypeError, ValueError, UnicodeError):
        print("field-evidence-packet-invalid", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
