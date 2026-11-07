"""Offline STAC + COG metadata selection and fail-closed test contract."""
from __future__ import annotations
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stac_cog_ndvi_preflight as preflight


def sample():
    return json.loads((ROOT / "fixtures/stac-sentinel-synthetic-item.json").read_text(encoding="utf-8"))


class StacCogTests(unittest.TestCase):
    def test_valid_metadata_is_not_clearance(self):
        item = sample()
        result = preflight.validate_item(item)
        self.assertEqual(result["asset_keys_checked"], ["B04", "B08", "SCL"])
        self.assertFalse(result["source_authenticity_verified"])
        self.assertFalse(result["license_and_use_rights_verified"])
        self.assertNotIn("https://", json.dumps(result))

    def test_bbox_rejects_unbounded_nan_crossing(self):
        for coords in (
            [-46, -23, -45, -22],
            [-46, -23, -46.1, -22.9],
            [179.9, 0, -179.9, .01],
            [float("nan"), 0, 1, 1],
            [True, 0, 1, 1],
            [-200, 0, -199, 1],
        ):
            with self.subTest(coords=coords), self.assertRaises(preflight.PreflightError):
                preflight.check_bbox(coords)
        self.assertEqual(preflight.check_bbox([-46.63, -23.55, -46.60, -23.53]),
                         (-46.63, -23.55, -46.6, -23.53))

    def test_date_limits_and_calendar(self):
        self.assertEqual(preflight.check_dates("2026-10-01", "2026-10-31"),
                         "2026-10-01/2026-10-31")
        for start, end in (("2026-02-30", "2026-03-01"),
                           ("2026-09-01", "2026-11-01"),
                           ("2026-11-01", "2026-10-01"),
                           ("tomorrow", "2026-11-01")):
            with self.subTest(start=start, end=end), self.assertRaises(preflight.PreflightError):
                preflight.check_dates(start, end)

    def test_url_security_blocks_non_blob_hosts_and_embedded_credentials(self):
        for href in (
            "https://localhost/B08.tif",
            "https://example.org/B08.tif",
            "https://blob.core.windows.net/B08.tif",
            "http://example.blob.core.windows.net/B08.tif",
            "https://bad.blob.core.windows.net:8443/B08.tif",
            "https://user:password@bad.blob.core.windows.net/B08.tif",
            "https://bad.blob.core.windows.net/B08.tif#fragment",
            "https://bad.blob.core.windows.net/B08.tif\\secrets",
            "https://bad.blob.core.windows.net/B08.tif\nanother",
            "https://[broken-ipv6/B08.tif",
        ):
            with self.subTest(href=href):
                self.assertFalse(preflight._safe_href(href))
        self.assertTrue(preflight._safe_href(
            "https://test.blob.core.windows.net/container/B08.tif?sig=redacted"
        ))

    def test_required_asset_or_cloud_metadata_missing(self):
        for key in ("B04", "B08", "SCL"):
            d = sample()
            del d["assets"][key]
            with self.subTest(key=key), self.assertRaises(preflight.PreflightError):
                preflight.validate_item(d)
        d = sample()
        d["properties"]["eo:cloud_cover"] = float("nan")
        with self.assertRaises(preflight.PreflightError):
            preflight.validate_item(d)

    def test_scene_must_intersect_request_and_match_time_window(self):
        data = sample()
        _, metadata = preflight.select_item(
            [data], bbox=[-46.63, -23.55, -46.60, -23.53],
            period="2026-10-01/2026-10-31")
        self.assertEqual(metadata["scene_id"], data["id"])
        for change in ("wrong_bbox", "wrong_date", "impossible_date"):
            item = sample()
            if change == "wrong_bbox":
                item["bbox"] = [5, 5, 6, 6]
            elif change == "wrong_date":
                item["properties"]["datetime"] = "2026-08-12T10:30:00Z"
            else:
                item["properties"]["datetime"] = "2026-18-95T10:30:00Z"
            with self.subTest(change=change), self.assertRaises(preflight.PreflightError):
                preflight.select_item(
                    [item], bbox=[-46.63, -23.55, -46.60, -23.53],
                    period="2026-10-01/2026-10-31")

    def test_scene_selection_deterministic_and_bounded(self):
        a, b = sample(), sample()
        b["id"] = "synthetic-sentinel-scene-02"
        b["properties"]["eo:cloud_cover"] = 3
        chosen, meta = preflight.select_item([a, b])
        self.assertEqual(chosen["id"], b["id"])
        self.assertEqual(meta["scene_cloud_cover_percent"], 3)
        with self.assertRaises(preflight.PreflightError):
            preflight.select_item([])
        with self.assertRaises(preflight.PreflightError):
            preflight.select_item([a] * (preflight.MAX_ITEMS + 1))
        with self.assertRaises(preflight.PreflightError):
            preflight.select_item([a], maximum_cloud_percent=1)

    def test_defaults_are_network_disabled(self):
        args = ["--bbox", "-46.63", "-23.55", "-46.6", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31"]
        self.assertEqual(preflight.main(args), 2)
        self.assertEqual(preflight.main(args + ["--stream-window",
                                               "--fixture", str(ROOT / "fixtures/stac-sentinel-synthetic-item.json")]), 2)
        self.assertEqual(preflight.main(args + ["--allow-network", "--fixture",
                                               str(ROOT / "fixtures/stac-sentinel-synthetic-item.json")]), 2)
        self.assertEqual(preflight.main(args + ["--fixture",
                                               str(ROOT / "fixtures/stac-sentinel-synthetic-item.json")]), 0)

    def test_input_not_mutated_or_urls_reported(self):
        data = sample()
        before = deepcopy(data)
        result = preflight.validate_item(data)
        self.assertEqual(data, before)
        self.assertNotIn("example.blob.core.windows.net", json.dumps(result))

    def test_local_fixture_duplicate_key_nonfinite_rejected(self):
        from tempfile import TemporaryDirectory
        args = ["--bbox", "-46.63", "-23.55", "-46.6", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31"]
        for invalid in ('{"id":"a","id":"b"}', '{"properties":{"eo:cloud_cover":NaN}}'):
            with TemporaryDirectory() as d:
                path = Path(d) / "invalid.json"
                path.write_text(invalid, encoding="utf-8")
                self.assertEqual(preflight.main(args + ["--fixture", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
