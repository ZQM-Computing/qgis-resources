#!/usr/bin/env python3
"""Offline, synthetic-only field-label comparison for utility screening.

Reference labels are declarations, not verified field ground truth. Reported
metrics are descriptive test-fixture results, never validated field accuracy.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from synthetic_clearance_3d import analyze, _object_no_duplicates, _reject_constant

MAX_BYTES = 1024 * 1024
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _ratio(numerator: int, denominator: int):
    return round(numerator / denominator, 6) if denominator else None


def _strict_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("invalid segment identifier")
    return value


def evaluate(screening: dict, reference: dict) -> dict:
    """Compare one synthetic screening against a disjoint, declared label file."""
    if not isinstance(reference, dict) or type(reference.get("schema_version")) is not int or reference["schema_version"] != 1:
        raise ValueError("unsupported reference version")
    if reference.get("scope") != "synthetic-only" or reference.get("reference_status") != "unverified-fixture":
        raise ValueError("field-verified or unscoped references not supported")
    if reference.get("label_origin") != "independent-synthetic-labels":
        raise ValueError("labels must be separately declared test fixtures")
    reviewer = reference.get("label_set_id")
    if not isinstance(reviewer, str) or not ID.fullmatch(reviewer):
        raise ValueError("invalid label-set identifier")
    digest = reference.get("source_fixture_sha256")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ValueError("missing source fixture digest assertion")
    canonical = json.dumps(screening, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    if sha256(canonical).hexdigest() != digest:
        raise ValueError("reference label set does not match screened input")
    predicted = analyze(screening)
    entries = predicted["segments"]
    if not isinstance(entries, list) or not entries or len(entries) > 100:
        raise ValueError("invalid segment predictions")
    identifiers = [_strict_id(entry["segment_id"]) for entry in entries]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate predicted segments")
    provided = reference.get("segment_labels")
    if not isinstance(provided, list) or len(provided) != len(identifiers):
        raise ValueError("label count does not match screening")
    labels = {}
    for row in provided:
        if not isinstance(row, dict) or set(row) != {"segment_id", "inspection_needed"}:
            raise ValueError("unsupported label structure")
        ident = _strict_id(row["segment_id"])
        if ident in labels or type(row["inspection_needed"]) is not bool:
            raise ValueError("duplicate or nonboolean label")
        labels[ident] = row["inspection_needed"]
    if set(labels) != set(identifiers):
        raise ValueError("label and screening identifiers differ")
    counts = {"true_positive": 0, "false_positive": 0, "true_negative": 0, "false_negative": 0}
    errors = []
    for entry in entries:
        ident = entry["segment_id"]
        predicted_flag = entry["finding"] == "POTENTIAL_PROXIMITY_REVIEW"
        true_flag = labels[ident]
        if predicted_flag and true_flag:
            category = "true_positive"
        elif predicted_flag:
            category = "false_positive"
        elif true_flag:
            category = "false_negative"
        else:
            category = "true_negative"
        counts[category] += 1
        if category in ("false_negative", "false_positive"):
            errors.append({"segment_id": ident, "disagreement": category})
    tp, fp, tn, fn = (counts[key] for key in (
        "true_positive", "false_positive", "true_negative", "false_negative"))
    positive_count, negative_count = tp + fn, tn + fp
    # Do not suggest generalization from a tiny/artificial fixture.
    return {
        "schema_version": 1,
        "evaluation_scope": "synthetic-only",
        "label_set_id": reviewer,
        "source_fixture_canonical_sha256_verified": digest,
        "reference_authenticity_verified": False,
        "independent_field_truth_verified": False,
        "model_validated_for_operations": False,
        "decision": "NOT_VALIDATED",
        "sample_size": len(entries),
        "positive_reference_count": positive_count,
        "negative_reference_count": negative_count,
        "confusion_matrix": counts,
        "metrics": {
            "recall_sensitivity": _ratio(tp, positive_count),
            "specificity": _ratio(tn, negative_count),
            "precision": _ratio(tp, tp + fp),
            "false_negative_rate": _ratio(fn, positive_count),
            "false_positive_rate": _ratio(fp, negative_count),
        },
        "disagreements": errors,
        "limitations": "Toy labels only; results do not establish generalization, operational accuracy, compliance or wildfire risk.",
    }


def _read(path: Path):
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("input too large")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object_no_duplicates,
                      parse_constant=_reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screening", type=Path)
    parser.add_argument("reference_labels", type=Path)
    args = parser.parse_args(argv)
    try:
        report = evaluate(_read(args.screening), _read(args.reference_labels))
        print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
        return 0  # Evaluation completed; NEVER a validated product return code.
    except (OSError, TypeError, ValueError, UnicodeError, ImportError):
        print("utility-validation-failed: invalid synthetic evidence", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
