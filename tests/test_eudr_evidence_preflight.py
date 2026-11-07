"""Dependency-free EUDR preflight contract tests; synthetic evidence only."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("eudr_preflight", ROOT / "scripts/eudr_evidence_preflight.py")
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def sample():
    return {
        "schema_version": 1,
        "batch_id": "synthetic-coffee-001",
        "commodity": "coffee",
        "product_scope": "human-review-pending",
        "country_of_production": "BR",
        "production_date_or_range": "2026-03-01/2026-04-01",
        "crs": "EPSG:4326",
        "plots": [{
            "plot_id": "test-plot-1",
            "declared_area_ha": 5,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-52.1, -12.1], [-52.0, -12.1], [-52.0, -12.0], [-52.1, -12.1]]
            },
            "source": {
                "sha256": "a" * 64,
                "reference": "https://example.org/synthetic-plot.geojson",
                "acquired_date": "2026-11-01",
                "rights_status": "independently-reviewed"
            },
            "producer_plot_linkage_verified": True
        }]
    }


class PreflightTests(unittest.TestCase):
    def test_synthetic_valid_metadata_requires_review_not_clearance(self):
        result = preflight.assess(sample())
        self.assertEqual(result["status"], "BLOCKED")  # geometric topology/area not verified
        self.assertTrue(result["human_review_required"])
        self.assertFalse(result["compliance_determined"])
        self.assertFalse(result["traces_submitted"])
        self.assertIn("polygon-topology-area-and-accuracy-unverified", result["exceptions"])

    def test_large_non_cattle_point_rejected(self):
        d = sample()
        d["plots"][0]["geometry"] = {"type": "Point", "coordinates": [-52.1, -12.1]}
        self.assertIn("polygon-required-for-declared-area", preflight.assess(d)["exceptions"])

    def test_point_with_unknown_area_cannot_be_cleared(self):
        d = sample()
        d["plots"][0]["declared_area_ha"] = None
        d["plots"][0]["geometry"] = {"type": "Point", "coordinates": [-52.1, -12.1]}
        self.assertIn("unverified-plot-area", preflight.assess(d)["exceptions"])

    def test_missing_supplier_linkage_is_flagged(self):
        d = sample()
        d["plots"][0]["producer_plot_linkage_verified"] = False
        self.assertIn("supplier-to-plot-linkage-unverified", preflight.assess(d)["exceptions"])

    def test_cattle_chain_not_inferred_from_point(self):
        d = sample()
        d["commodity"] = "cattle"
        d["plots"][0]["geometry"] = {"type": "Point", "coordinates": [-52.1, -12.1]}
        self.assertIn("cattle-establishment-chain-not-verified", preflight.assess(d)["exceptions"])

    def test_duplicates_and_missing_source_hash(self):
        d = sample()
        d["plots"].append(deepcopy(d["plots"][0]))
        d["plots"][1]["source"]["sha256"] = ""
        issues = preflight.assess(d)["exceptions"]
        self.assertIn("invalid-or-duplicate-plot-id", issues)
        self.assertIn("missing-immutable-source-digest", issues)

    def test_compliance_claim_is_flagged(self):
        d = sample()
        d["dds_submitted"] = True
        self.assertIn("unverified-compliance-claim", preflight.assess(d)["exceptions"])

    def test_malicious_and_invalid_geometry_rejected(self):
        for geom in (
            {"type": "Point", "coordinates": [float("nan"), 0]},
            {"type": "Point", "coordinates": [200, 0]},
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]},
            {"type": "GeometryCollection", "geometries": []},
        ):
            with self.subTest(geom=str(geom)):
                d = sample()
                d["plots"][0]["geometry"] = geom
                self.assertIn("invalid-geojson-geometry-structure", preflight.assess(d)["exceptions"])

    def test_deterministic_nonmutating_and_redacted(self):
        d = sample()
        copy = deepcopy(d)
        first = preflight.assess(d)
        self.assertEqual(first, preflight.assess(d))
        self.assertEqual(d, copy)
        self.assertNotIn("https://example.org", json.dumps(first))
        self.assertNotIn("production_date_or_range", first)

    def test_duplicate_json_keys_and_nonfinite_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "test.json"
            for text in ('{"x":1,"x":2}', '{"a": NaN}'):
                p.write_text(text)
                with self.assertRaises(ValueError):
                    preflight.load(p)

    def test_oversized_input_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "big.json"
            p.write_bytes(b"x" * (preflight.MAX_INPUT_BYTES + 1))
            with self.assertRaises(ValueError):
                preflight.load(p)


if __name__ == "__main__":
    unittest.main()
