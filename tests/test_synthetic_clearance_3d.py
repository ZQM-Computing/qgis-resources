"""Independent synthetic 3D separation and fail-closed uncertainty tests."""
from __future__ import annotations
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from synthetic_clearance_3d import analyze, main, _point_to_segment

def fixture():
    return json.loads((ROOT / "fixtures" / "utility-clearance-3d-synthetic.json").read_text(encoding="utf-8"))

class ClearanceTests(unittest.TestCase):
    def test_uncertainty_bounds_and_no_automatic_clearance(self):
        result = analyze(fixture())
        self.assertEqual(result["status"], "REVIEW")
        match = result["segments"][0]["candidates"][0]
        self.assertEqual(match["sample_id"], "sample-a")
        self.assertEqual(match["nominal_separation_m"], 3.0)
        self.assertEqual(match["conservative_lower_bound_m"], 2.0)
        self.assertEqual(match["conservative_upper_bound_m"], 4.0)
        self.assertEqual(result["segments"][1]["finding"], "SAMPLED_POINTS_OUTSIDE_THRESHOLD_NOT_CLEARANCE")
        self.assertFalse(result["field_clearance_verified"])
        self.assertFalse(result["cost_savings_estimated"])

    def test_point_to_segment_endpoint_clamping(self):
        self.assertEqual(_point_to_segment((2, 3, 0), (0, 0, 0), (1, 0, 0)), math.sqrt(10))
        self.assertEqual(_point_to_segment((0.5, 4, 0), (0, 0, 0), (1, 0, 0)), 4)

    def test_uncertainty_can_flag_outside_nominal_threshold(self):
        data = fixture()
        data["vegetation_samples"][0]["position"] = [500010, 3200005, 15]
        data["vegetation_samples"][0]["absolute_position_uncertainty_m"] = 2
        result = analyze(data)
        self.assertEqual(result["segments"][0]["candidates"][0]["nominal_separation_m"], 5)
        self.assertEqual(result["segments"][0]["candidates"][0]["conservative_lower_bound_m"], 2.5)

    def test_no_candidate_is_insufficient_evidence(self):
        data = fixture()
        data["review_threshold_m"] = 1
        self.assertEqual(analyze(data)["status"], "INSUFFICIENT_EVIDENCE")

    def test_missing_samples_fails_not_clear(self):
        data = fixture()
        data["vegetation_samples"] = []
        with self.assertRaises(ValueError):
            analyze(data)

    def test_missing_uncertainty_fails(self):
        data = fixture()
        del data["conductor_segments"][0]["absolute_position_uncertainty_m"]
        with self.assertRaises(ValueError):
            analyze(data)

    def test_invalid_date_and_crs_fail(self):
        for key, value in (("observation_date", "2026-02-30"),
                           ("horizontal_crs", "EPSG:4326"),
                           ("vertical_reference", "UNKNOWN")):
            with self.subTest(key=key):
                data = fixture()
                data[key] = value
                with self.assertRaises(ValueError):
                    analyze(data)

    def test_invalid_coordinates_and_uncertainty_fail(self):
        for key, value in (("position", [500010, 3200003, float("nan")]),
                           ("position", [500010, 3200003, True]),
                           ("position", [-80, 25, 2]),
                           ("absolute_position_uncertainty_m", -1),
                           ("absolute_position_uncertainty_m", True)):
            with self.subTest(key=key):
                data = fixture()
                data["vegetation_samples"][0][key] = value
                with self.assertRaises(ValueError):
                    analyze(data)

    def test_degenerate_segment_and_duplicate_ids_fail(self):
        data = fixture()
        data["conductor_segments"][0]["end"] = data["conductor_segments"][0]["start"]
        with self.assertRaises(ValueError):
            analyze(data)
        data = fixture()
        data["vegetation_samples"][1]["id"] = data["vegetation_samples"][0]["id"]
        with self.assertRaises(ValueError):
            analyze(data)

    def test_self_approval_is_rejected(self):
        data = fixture()
        data["work_order_authorized"] = True
        with self.assertRaises(ValueError):
            analyze(data)

    def test_deterministic_and_nonmutating(self):
        data = fixture()
        saved = deepcopy(data)
        self.assertEqual(analyze(data), analyze(data))
        self.assertEqual(data, saved)

    def test_cli_rejects_duplicate_json_and_nan(self):
        for raw in ('{"a": 1, "a": 2}', '{"a": NaN}'):
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "invalid.json"
                path.write_text(raw)
                self.assertEqual(main([str(path)]), 1)

if __name__ == "__main__":
    unittest.main()
