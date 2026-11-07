"""Offline STAC + COG metadata selection and fail-closed test contract."""
from __future__ import annotations
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stac_cog_ndvi_preflight as preflight


def sample():
    """Load a fresh fictional Sentinel-2 item for offline assertions."""
    return json.loads((ROOT / "fixtures/stac-sentinel-synthetic-item.json").read_text(encoding="utf-8"))


class StacCogTests(unittest.TestCase):
    def test_valid_metadata_is_not_clearance(self):
        """Verify valid metadata is not clearance."""
        item = sample()
        result = preflight.validate_item(item)
        self.assertEqual(result["asset_keys_checked"], ["B04", "B08", "SCL"])
        self.assertFalse(result["source_authenticity_verified"])
        self.assertFalse(result["license_and_use_rights_verified"])
        self.assertNotIn("https://", json.dumps(result))

    def test_bbox_rejects_unbounded_nan_crossing(self):
        """Verify bbox rejects unbounded nan crossing."""
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
        """Verify date limits and calendar."""
        self.assertEqual(preflight.check_dates("2026-10-01", "2026-10-31"),
                         "2026-10-01/2026-10-31")
        for start, end in (("2026-02-30", "2026-03-01"),
                           ("2026-09-01", "2026-11-01"),
                           ("2026-11-01", "2026-10-01"),
                           ("tomorrow", "2026-11-01")):
            with self.subTest(start=start, end=end), self.assertRaises(preflight.PreflightError):
                preflight.check_dates(start, end)

    def test_url_security_blocks_non_blob_hosts_and_embedded_credentials(self):
        """Verify url security blocks non blob hosts and embedded credentials."""
        for href in (
            "https://localhost/B08.tif",
            "https://attacker.blob.core.windows.net/sentinel2-l2/B08.tif",
            "https://sentinel2l2a01.blob.core.windows.net/unrelated/B08.tif",
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
            "https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/test/B08.tif?sig=redacted"
        ))

    def test_raster_grid_edges_snap_only_very_near_integer(self):
        """Verify raster grid edges snap only very near integer."""
        self.assertEqual(preflight._window_edge(9.00000000000034, upper=True), 9)
        self.assertEqual(preflight._window_edge(1.00000000000051, upper=False), 1)
        self.assertEqual(preflight._window_edge(9.01, upper=True), 10)
        self.assertEqual(preflight._window_edge(0.99, upper=False), 0)
        with self.assertRaises(preflight.PreflightError):
            preflight._window_edge(float("nan"), upper=False)

    def test_required_asset_or_cloud_metadata_missing(self):
        """Verify required asset or cloud metadata missing."""
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
        """Verify scene must intersect request and match time window."""
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

    def test_partial_scene_envelope_cannot_claim_full_query_coverage(self):
        """Verify partial scene envelope cannot claim full query coverage."""
        item = sample()
        item["bbox"] = [-46.62, -23.55, -46.60, -23.53]
        with self.assertRaises(preflight.PreflightError):
            preflight.select_item(
                [item], bbox=[-46.63, -23.55, -46.60, -23.53],
                period="2026-10-01/2026-10-31",
            )
        item["bbox"] = [-46.64, -23.56, -46.59, -23.52]
        chosen, meta = preflight.select_item(
            [item], bbox=[-46.63, -23.55, -46.60, -23.53],
            period="2026-10-01/2026-10-31",
        )
        self.assertEqual(chosen["id"], item["id"])

    def test_scene_selection_deterministic_and_bounded(self):
        """Verify scene selection deterministic and bounded."""
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
        """Verify defaults are network disabled."""
        args = ["--bbox", "-46.63", "-23.55", "-46.6", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31"]
        self.assertEqual(preflight.main(args), 2)
        self.assertEqual(preflight.main(args + ["--stream-window",
                                               "--fixture", str(ROOT / "fixtures/stac-sentinel-synthetic-item.json")]), 2)
        self.assertEqual(preflight.main(args + ["--allow-network", "--fixture",
                                               str(ROOT / "fixtures/stac-sentinel-synthetic-item.json")]), 2)
        self.assertEqual(preflight.main(args + ["--fixture",
                                               str(ROOT / "fixtures/stac-sentinel-synthetic-item.json")]), 0)

    def test_network_opt_in_must_have_budget_and_stays_mocked(self):
        """Verify network opt in must have budget and stays mocked."""
        args = ["--bbox", "-46.63", "-23.55", "-46.60", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31",
                "--allow-network"]
        with patch.object(preflight, "search_scene", side_effect=AssertionError("no network allowed")):
            self.assertEqual(preflight.main(args), 2)
        with TemporaryDirectory() as folder:
            budget = json.loads((ROOT / "fixtures" / "stac-cost-budget-synthetic.json").read_text())
            path = Path(folder) / "budget.json"
            budget["approved_spend_ceiling_usd"] = "0"
            path.write_text(json.dumps(budget), encoding="utf-8")
            with patch.object(preflight, "search_scene", side_effect=AssertionError("budget should block network")):
                self.assertEqual(preflight.main(args + ["--budget-plan", str(path)]), 2)
            budget["approved_spend_ceiling_usd"] = "21.20"
            path.write_text(json.dumps(budget), encoding="utf-8")
            with patch.object(preflight, "search_scene", return_value=[sample()]) as mocked:
                self.assertEqual(preflight.main(args + ["--budget-plan", str(path)]), 0)
                mocked.assert_called_once()
            budget["request_count"] = 0
            path.write_text(json.dumps(budget), encoding="utf-8")
            with patch.object(preflight, "search_scene", side_effect=AssertionError("zero requests")):
                self.assertEqual(preflight.main(args + ["--budget-plan", str(path)]), 2)

    def test_invalid_cloud_limit_blocks_before_search(self):
        """Verify invalid cloud limit blocks before search."""
        args = ["--bbox", "-46.63", "-23.55", "-46.60", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31",
                "--allow-network", "--budget-plan",
                str(ROOT / "fixtures/stac-cost-budget-synthetic.json")]
        for value in ("nan", "inf", "-inf", "-5", "150"):
            with self.subTest(value=value), patch.object(preflight, "search_scene") as search:
                self.assertEqual(preflight.main(args + ["--cloud-limit=" + value]), 2)
                search.assert_not_called()
                with self.assertRaises(preflight.PreflightError):
                    preflight.select_item([sample()], float(value))
        for value in (0, 100):
            self.assertEqual(preflight.check_cloud_limit(value), value)
        for value in (True, "20", None):
            with self.assertRaises(preflight.PreflightError):
                preflight.check_cloud_limit(value)

    def test_stac_library_failures_are_redacted(self):
        """Verify stac library failures are redacted."""
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        class ProviderError(Exception):
            pass

        args = ["--bbox", "-46.63", "-23.55", "-46.60", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31",
                "--allow-network", "--budget-plan",
                str(ROOT / "fixtures/stac-cost-budget-synthetic.json")]
        for phase in ("open", "search", "items", "conversion"):
            client = MagicMock()
            catalog = client.open.return_value
            search = catalog.search.return_value
            item = MagicMock()
            search.items.return_value = [item]
            target = {"open": client.open, "search": catalog.search,
                      "items": search.items, "conversion": item.to_dict}[phase]
            target.side_effect = ProviderError("secret-provider-token")
            stderr, stdout = StringIO(), StringIO()
            with self.subTest(phase=phase), patch.dict(sys.modules, {
                "pystac_client": SimpleNamespace(Client=client),
                "planetary_computer": SimpleNamespace(sign_inplace=lambda item: None),
            }), redirect_stderr(stderr), redirect_stdout(stdout):
                self.assertEqual(preflight.main(args), 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(),
                             "stac-cog-preflight-blocked: invalid request, metadata or remote source\n")

    def test_input_not_mutated_or_urls_reported(self):
        """Verify input not mutated or urls reported."""
        data = sample()
        before = deepcopy(data)
        result = preflight.validate_item(data)
        self.assertEqual(data, before)
        self.assertNotIn("example.blob.core.windows.net", json.dumps(result))

    def test_local_fixture_duplicate_key_nonfinite_rejected(self):
        """Verify local fixture duplicate key nonfinite rejected."""
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
