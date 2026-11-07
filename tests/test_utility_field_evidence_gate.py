"""Field-evidence packet tests. All references are fictitious and unauthenticated."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from utility_field_evidence_gate import assess, main, FIELDS


def sample():
    return json.loads((ROOT / "fixtures/utility-field-evidence-packet-synthetic.json").read_text(encoding="utf-8"))


def fake_review(name):
    return {
        "document_id": "fictional-" + name,
        "sha256": "a" * 64,
        "reviewed": True,
        "reviewed_on": "2026-11-07",
    }


def complete_structure():
    data = sample()
    data["evidence"] = {name: fake_review(name) for name in FIELDS}
    data["evaluation"].update({
        "model_commit_sha": "a" * 64,
        "source_dataset_sha256": "b" * 64,
        "label_dataset_sha256": "c" * 64,
        "independent_reference_review": fake_review("ground-truth"),
        "blind_holdout_unlocked_only_after_model_freeze": True,
        "prespecified_safety_thresholds_reviewed": True,
        "field_calibration_completed": True,
        "subgroup_error_analysis_completed": True,
        "false_negative_review_completed": True
    })
    data["authorized_reviewer_role"] = "qualified-independent-utility-reviewer"
    return data


class PacketTests(unittest.TestCase):
    def test_incomplete_fixture_blocks_and_no_approval(self):
        result = assess(sample())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["operational_use_approved"])
        self.assertFalse(result["field_accuracy_established"])
        self.assertIn("evidence-required:vertical_datum", result["blockers"])

    def test_complete_assertions_still_cannot_establish_truth_or_operational_approval(self):
        result = assess(complete_structure())
        self.assertEqual(result["status"], "PACKET_COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION")
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["evidence_authenticity_verified"])
        self.assertFalse(result["work_order_authorized"])

    def test_missing_each_source_check_fails(self):
        for name in FIELDS:
            data = complete_structure()
            del data["evidence"][name]
            with self.subTest(name=name):
                self.assertIn("evidence-required:" + name, assess(data)["blockers"])

    def test_forged_or_missing_release_approval_rejected(self):
        for value in (True, None, "false", 0):
            data = complete_structure()
            data["release_approved"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess(data)
        data = complete_structure()
        del data["release_approved"]
        with self.assertRaises(ValueError):
            assess(data)

    def test_overlapping_holdout_is_blocked(self):
        data = complete_structure()
        data["evaluation"]["holdout_segment_ids"] = ["synthetic-line-1"]
        self.assertIn("development-holdout-overlap", assess(data)["blockers"])

    def test_duplicate_and_malformed_segment_ids_blocked(self):
        for ids in (["a", "a"], ["a", 12], [], [None]):
            data = complete_structure()
            data["evaluation"]["holdout_segment_ids"] = ids
            with self.subTest(ids=ids):
                self.assertTrue(assess(data)["blockers"])

    def test_missing_frozen_model_or_label_digest_blocks(self):
        for key in ("model_commit_sha", "label_dataset_sha256"):
            data = complete_structure()
            data["evaluation"][key] = "latest"
            self.assertIn("immutable-reference-required:" + key, assess(data)["blockers"])

    def test_impossible_dates_and_missing_review_rejected(self):
        data = complete_structure()
        data["evidence"]["horizontal_datum"]["reviewed_on"] = "2026-02-30"
        data["evaluation"]["independent_reference_review"]["reviewed"] = False
        result = assess(data)
        self.assertIn("evidence-required:horizontal_datum", result["blockers"])
        self.assertIn("independent-reference-review-required", result["blockers"])

    def test_safety_threshold_and_false_negative_review_block_if_unverified(self):
        data = complete_structure()
        data["evaluation"]["prespecified_safety_thresholds_reviewed"] = False
        data["evaluation"]["false_negative_review_completed"] = False
        self.assertIn("qualified-safety-threshold-review-required", assess(data)["blockers"])
        self.assertIn("missed-hazard-review-required", assess(data)["blockers"])

    def test_deterministic_and_does_not_modify_input(self):
        data = complete_structure()
        original = deepcopy(data)
        self.assertEqual(assess(data), assess(data))
        self.assertEqual(data, original)

    def test_cli_returns_blocking_status(self):
        self.assertEqual(main([str(ROOT / "fixtures/utility-field-evidence-packet-synthetic.json")]), 1)

    def test_cli_duplicate_key_and_nonfinite_refused(self):
        for content in ('{"x":1,"x":2}', '{"x":NaN}'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "packet.json"
                path.write_text(content)
                self.assertEqual(main([str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
