"""Unit and GDAL-backed assertions for synthetic projected utility-corridor screening."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from utility_corridor_screening import load, analyze


def sample():
    return json.loads((ROOT / "fixtures" / "utility-corridor-synthetic.json").read_text(encoding="utf-8"))


class CorridorTests(unittest.TestCase):
    def test_expected_horizontal_proximity_and_unknown_clearance(self):
        result = analyze(sample())
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["asset_results"][0]["asset_id"], "line-a")
        self.assertEqual(result["asset_results"][0]["candidates"], [
            {"vegetation_id": "near-polygon", "horizontal_distance_m": 10.0}])
        self.assertEqual(result["asset_results"][1]["finding"], "NO_NEARBY_MAPPED_GEOMETRY_NOT_CLEARANCE")
        self.assertFalse(result["conductor_clearance_3d_measured"])
        self.assertFalse(result["cost_savings_estimated"])
        self.assertFalse(result["work_order_authorized"])

    def test_no_nearby_polygon_is_not_clearance(self):
        data = sample()
        data["screening_distance_m"] = 5
        result = analyze(data)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(all(not x["candidates"] for x in result["asset_results"]))

    def test_polygon_intersection_distance_zero_flags(self):
        data = sample()
        data["vegetation"][0]["geometry"]["coordinates"] = [
            [[499990,3200400],[500010,3200400],[500010,3200500],[499990,3200500],[499990,3200400]]
        ]
        result = analyze(data)
        self.assertEqual(result["asset_results"][0]["candidates"][0]["horizontal_distance_m"], 0.0)

    def test_double_counting_does_not_affect_nearest_distance(self):
        data = sample()
        clone = deepcopy(data["vegetation"][0])
        clone["id"] = "another-near"
        data["vegetation"].append(clone)
        result = analyze(data)
        self.assertEqual(len(result["asset_results"][0]["candidates"]), 2)
        self.assertEqual(result["asset_results"][0]["candidates"][0]["horizontal_distance_m"], 10.0)

    def test_missing_vegetation_fails_not_all_clear(self):
        data = sample()
        data["vegetation"] = []
        with self.assertRaises(ValueError):
            analyze(data)

    def test_wrong_crs_fails_not_measured_in_degrees(self):
        data = sample()
        data["crs"] = "EPSG:4326"
        with self.assertRaises(ValueError):
            analyze(data)

    def test_self_crossing_polygon_rejected(self):
        data = sample()
        data["vegetation"][0]["geometry"]["coordinates"] = [
            [[500010,3200400],[500030,3200500],[500010,3200500],[500030,3200400],[500010,3200400]]
        ]
        with self.assertRaises(ValueError):
            analyze(data)

    def test_duplicate_ids_rejected(self):
        data = sample()
        data["assets"][1]["id"] = "line-a"
        with self.assertRaises(ValueError):
            analyze(data)

    def test_nonfinite_and_bad_threshold_rejected(self):
        for bad in (math.nan, math.inf, -3, 0, 101, True):
            with self.subTest(bad=bad):
                data = sample()
                data["screening_distance_m"] = bad
                with self.assertRaises(ValueError):
                    analyze(data)

    def test_geometry_boolean_and_bad_latlon_rejected(self):
        for bad in ([True, 3200000], [-80, 29]):
            data = sample()
            data["assets"][0]["geometry"]["coordinates"][0] = bad
            with self.assertRaises(ValueError):
                analyze(data)

    def test_missing_date_and_fake_approval_rejected(self):
        for field, value in (("observed_date", "2026-02-30"),
                             ("human_review", "approved"),
                             ("deployment_authorized", True)):
            data = sample()
            data[field] = value
            with self.assertRaises(ValueError):
                analyze(data)

    def test_deterministic_source_unmodified(self):
        data = sample()
        old = deepcopy(data)
        self.assertEqual(analyze(data), analyze(data))
        self.assertEqual(data, old)


if __name__ == "__main__":
    unittest.main()
