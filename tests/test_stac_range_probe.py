"""No-network tests for strict Sentinel COG Range probe boundaries."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from email.message import Message

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stac_cog_ndvi_preflight as stac
import stac_range_probe as probe

URL = "https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/fictional-test/B08.tif?sig=fictional-secret"


class FakeResponse:
    def __init__(self, *, status=206, content_range="bytes 0-4095/20000",
                 content_length="4096", data=b"II" + b"\0" * 4094,
                 encoding=None):
        self.status = status
        self.headers = Message()
        self.headers["Content-Range"] = content_range
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        if encoding is not None:
            self.headers["Content-Encoding"] = encoding
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.status

    def read(self, n):
        return self.data[:n]


class RangeTests(unittest.TestCase):
    def test_bounded_range_request_and_safe_no_token_output(self):
        requests = []
        def transport(req, *, timeout):
            requests.append((req, timeout))
            return FakeResponse()
        output = probe.probe_range(URL, transport=transport)
        self.assertEqual(output["payload_bytes_observed_by_probe"], 4096)
        self.assertEqual(output["request_count_observed_by_probe"], 1)
        self.assertFalse(output["full_gdal_request_and_egress_metering_established"])
        self.assertNotIn("fictional-secret", json.dumps(output))
        self.assertEqual(requests[0][0].get_header("Range"), "bytes=0-4095")
        self.assertEqual(requests[0][0].get_header("Accept-encoding"), "identity")
        self.assertEqual(requests[0][1], 8)

    def test_rejects_bad_http_range_replies(self):
        variants = (
            {"status": 200},
            {"status": 302},
            {"content_range": "bytes 0-10000/20000"},
            {"content_range": "bytes 1-4096/20000"},
            {"content_range": "bytes */20000"},
            {"content_range": "bytes 0-4095/*"},
            {"content_range": "bytes 0-4095/4095"},
            {"content_length": None},
            {"content_length": "5000"},
            {"content_length": "oops"},
            {"data": b"II" + b"x" * 4095},
            {"data": b"II"},
            {"data": b"NOT_TIFF" + b"x" * 4088},
            {"encoding": "gzip"},
        )
        for kwargs in variants:
            with self.subTest(kwargs=kwargs), self.assertRaises(probe.RangeProbeError):
                probe.probe_range(URL, transport=lambda req, timeout: FakeResponse(**kwargs))

    def test_rejects_untrusted_url_without_transport(self):
        with self.assertRaises(probe.RangeProbeError):
            probe.probe_range("https://untrusted.example.org/asset.tif",
                              transport=lambda *_a, **_kw: self.fail("network must not run"))

    def test_redirect_handler_explicitly_denies_redirects(self):
        with self.assertRaises(probe.RangeProbeError):
            probe._DenyRedirects().redirect_request(None, None, 302, "Found", {}, "https://other.example.org")

    def test_cli_does_not_probe_without_opt_in_and_budget(self):
        args = ["--bbox", "-46.63", "-23.55", "-46.60", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31"]
        with patch.object(probe, "probe_range", side_effect=AssertionError("probe unexpectedly called")):
            self.assertEqual(stac.main(args + ["--probe-range"]), 2)
        with patch.object(stac, "search_scene", side_effect=AssertionError("network unexpectedly called")):
            self.assertEqual(stac.main(args + ["--allow-network", "--probe-range"]), 2)
        with TemporaryDirectory() as td:
            fixture = json.loads((ROOT / "fixtures/stac-cost-budget-synthetic.json").read_text())
            path = Path(td) / "budget.json"
            scene = json.loads((ROOT / "fixtures/stac-sentinel-synthetic-item.json").read_text())
            for requests, nbytes in ((1, 4096), (2, 4095)):
                fixture["request_count"] = requests
                fixture["estimated_range_bytes"] = nbytes
                path.write_text(json.dumps(fixture))
                with patch.object(stac, "search_scene", side_effect=AssertionError("budget should block")):
                    self.assertEqual(stac.main(args + [
                        "--allow-network", "--probe-range", "--budget-plan", str(path)
                    ]), 2)
            fixture["request_count"] = 2
            fixture["estimated_range_bytes"] = 4096
            path.write_text(json.dumps(fixture))
            with patch.object(stac, "search_scene", return_value=[scene]) as discover:
                with patch.object(probe, "probe_range", return_value={"status": "synthetic"} ) as mock:
                    self.assertEqual(stac.main(args + [
                        "--allow-network", "--probe-range", "--budget-plan", str(path)
                    ]), 0)
                    discover.assert_called_once()
                    mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
