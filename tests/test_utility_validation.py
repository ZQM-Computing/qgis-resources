"""Synthetic-only validation metrics and fail-closed reference binding."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from utility_validation import evaluate, main

def screening():
    """Load a fresh copy of the fictional screening geometry fixture."""
    return json.loads((ROOT / "fixtures" / "utility-clearance-3d-synthetic.json").read_text(encoding="utf-8"))

def labels():
    """Load a fresh copy of the separately declared synthetic label fixture."""
    return json.loads((ROOT / "fixtures" / "utility-validation-labels-synthetic.json").read_text(encoding="utf-8"))

def bind(data, reference):
    """Update reference metadata with the canonical screening digest for a test."""
    reference["source_fixture_sha256"] = sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return reference

class ValidationHarnessTests(unittest.TestCase):
    def test_fixture_digest_binds_and_comparison_not_field_validated(self):
        """Check fixture binding and expected counts without asserting field validity."""
        data, reference = screening(), labels()
        self.assertEqual(reference["source_fixture_sha256"], bind(data, deepcopy(reference))["source_fixture_sha256"])
        report = evaluate(data, reference)
        self.assertEqual(report["decision"], "NOT_VALIDATED")
        self.assertEqual(report["sample_size"], 2)
        self.assertEqual(report["confusion_matrix"], {
            "true_positive": 1, "false_positive": 0,
            "true_negative": 1, "false_negative": 0
        })
        self.assertEqual(report["metrics"]["recall_sensitivity"], 1.0)
        self.assertFalse(report["independent_field_truth_verified"])
        self.assertFalse(report["model_validated_for_operations"])

    def test_all_four_confusion_cells_and_rates(self):
        """Invert toy labels to check error counts and the corresponding rates."""
        data = screening()
        # Synthetic label inversion deliberately demonstrates both error modes.
        reference = labels()
        reference["segment_labels"][0]["inspection_needed"] = False
        reference["segment_labels"][1]["inspection_needed"] = True
        result = evaluate(data, reference)
        self.assertEqual(result["confusion_matrix"]["false_positive"], 1)
        self.assertEqual(result["confusion_matrix"]["false_negative"], 1)
        self.assertEqual(result["metrics"]["recall_sensitivity"], 0.0)
        self.assertEqual(result["metrics"]["precision"], 0.0)
        self.assertEqual(result["metrics"]["false_negative_rate"], 1.0)
        self.assertEqual(result["metrics"]["false_positive_rate"], 1.0)
        self.assertEqual(len(result["disagreements"]), 2)

    def test_undefined_denominators_return_null(self):
        """Check undefined rates for all-negative and all-positive label sets."""
        reference = labels()
        for label in reference["segment_labels"]:
            label["inspection_needed"] = False
        result = evaluate(screening(), reference)
        self.assertIsNone(result["metrics"]["recall_sensitivity"])
        self.assertIsNone(result["metrics"]["false_negative_rate"])
        self.assertEqual(result["metrics"]["precision"], 0.0)
        self.assertEqual(result["metrics"]["specificity"], 0.5)
        reference = labels()
        for label in reference["segment_labels"]:
            label["inspection_needed"] = True
        all_positive = evaluate(screening(), reference)
        self.assertIsNone(all_positive["metrics"]["specificity"])
        self.assertIsNone(all_positive["metrics"]["false_positive_rate"])

    def test_stale_input_digest_rejected(self):
        """Reject reference labels bound to different screening inputs."""
        data = screening()
        data["review_threshold_m"] = 5
        with self.assertRaises(ValueError):
            evaluate(data, labels())

    def test_duplicate_missing_and_incorrect_identifiers_rejected(self):
        """Reject duplicate, missing, and unknown reference segment identifiers."""
        for modification in ("duplicate", "missing", "unknown"):
            ref = labels()
            if modification == "duplicate":
                ref["segment_labels"][1]["segment_id"] = "line-1"
            elif modification == "missing":
                ref["segment_labels"].pop()
            else:
                ref["segment_labels"][1]["segment_id"] = "line-not-present"
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                evaluate(screening(), ref)

    def test_unverified_source_cannot_pretend_field_truth(self):
        """Reject unsupported scope, field-verification, and label-origin assertions."""
        for key, value in (("scope", "customer-data"),
                           ("reference_status", "field-verified"),
                           ("label_origin", "model-self-labels")):
            ref = labels()
            ref[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluate(screening(), ref)

    def test_nonboolean_truth_and_unknown_fields_rejected(self):
        """Reject nonboolean labels and extra fields within a label row."""
        ref = labels()
        ref["segment_labels"][0]["inspection_needed"] = "true"
        with self.assertRaises(ValueError):
            evaluate(screening(), ref)
        ref = labels()
        ref["segment_labels"][0]["reviewer_signoff"] = "approved"
        with self.assertRaises(ValueError):
            evaluate(screening(), ref)

    def test_malformed_screening_rejected(self):
        """Reject empty conductor geometry even with a matching reference digest."""
        d = screening()
        d["conductor_segments"] = []
        with self.assertRaises(ValueError):
            evaluate(d, bind(d, labels()))

    def test_deterministic_no_mutation(self):
        """Ensure evaluation is repeatable and preserves both input objects."""
        d, r = screening(), labels()
        before_d, before_r = deepcopy(d), deepcopy(r)
        self.assertEqual(evaluate(d,r), evaluate(d,r))
        self.assertEqual(d, before_d)
        self.assertEqual(r, before_r)

    def test_cli_on_synthetic_fixtures(self):
        """Check that the synthetic comparison completes with CLI exit code 0."""
        self.assertEqual(main([
            str(ROOT / "fixtures" / "utility-clearance-3d-synthetic.json"),
            str(ROOT / "fixtures" / "utility-validation-labels-synthetic.json")
        ]), 0)

if __name__ == "__main__":
    unittest.main()
