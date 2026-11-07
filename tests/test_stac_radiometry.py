"""Offline Sentinel L2A reflectance-correction metadata and math tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stac_radiometry as radio


def fixture():
    return json.loads((ROOT / "fixtures" / "stac-radiometry-synthetic.json").read_text())


class RadiometryTests(unittest.TestCase):
    def test_known_post_baseline_formula_and_unverified_metadata(self):
        record = fixture()
        self.assertEqual(radio.validate_radiometry(record, record["scene_id"]), record)
        n, r = radio.correct_dn_arrays(6000.0, 2000.0, record)
        self.assertAlmostEqual(n, 0.5)
        self.assertAlmostEqual(r, 0.1)
        self.assertAlmostEqual((n-r)/(n+r), 2/3)
        self.assertFalse(record["provider_metadata_authenticity_verified"])

    def test_scene_mismatch_and_untrusted_approval_block(self):
        d = fixture()
        with self.assertRaises(radio.RadiometryError):
            radio.validate_radiometry(d, "other-scene")
        for invalid in (True, "false", None, 0):
            d = fixture()
            d["provider_metadata_authenticity_verified"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(radio.RadiometryError):
                radio.validate_radiometry(d, d["scene_id"])

    def test_invalid_offsets_quantification_and_processing_baseline(self):
        for name, value in (
            ("boa_quantification_value", 0),
            ("boa_quantification_value", True),
            ("boa_quantification_value", float("nan")),
            ("boa_add_offset_b04", "negative-one-thousand"),
            ("boa_add_offset_b08", 10),
            ("processing_baseline", "03.00"),
            ("processing_baseline", "unknown"),
            ("product_metadata_sha256", "unverified"),
            ("product_metadata_acquired_on", "2026-02-30"),
        ):
            d = fixture()
            d[name] = value
            with self.subTest(name=name), self.assertRaises(radio.RadiometryError):
                radio.validate_radiometry(d, d["scene_id"])

    def test_no_silent_unrecognized_metadata_properties(self):
        d = fixture()
        d["source_authenticated"] = True
        with self.assertRaises(radio.RadiometryError):
            radio.validate_radiometry(d, d["scene_id"])

    def test_rejects_duplicate_json_or_nonfinite_values(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
            with TemporaryDirectory() as directory:
                path = Path(directory) / "bad.json"
                path.write_text(raw)
                with self.assertRaises(radio.RadiometryError):
                    radio.load_radiometry(path, "synthetic-sentinel-scene-01")

    def test_pure_nonmutating_metadata_validation(self):
        d = fixture()
        before = deepcopy(d)
        self.assertEqual(radio.validate_radiometry(d, d["scene_id"]), d)
        self.assertEqual(d, before)


if __name__ == "__main__":
    unittest.main()
