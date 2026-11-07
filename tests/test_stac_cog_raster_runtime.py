"""End-to-end local Rasterio test of the *same* pixel-window function.

All GeoTIFFs are generated in TemporaryDirectory. URL validation is patched
ONLY in these tests to admit local files; production rejects local paths.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
except ImportError:
    np = None
    rasterio = None

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stac_cog_ndvi_preflight as stac


@unittest.skipUnless(rasterio is not None and np is not None, "Rasterio/Numpy runtime required")
class LocalRasterWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.transform = from_origin(-46.70, -23.50, 0.01, 0.01)
        self.bbox = [-46.69, -23.59, -46.61, -23.51]
        self.item = {"assets": {}}
        for key, value in (("B08", 6000), ("B04", 2000), ("SCL", 4)):
            arr = np.full((10, 10), value, dtype="uint16")
            self._write(key, arr)
        self.patch = patch.object(stac, "_safe_href", side_effect=lambda href: (
            isinstance(href, str) and Path(href).parent == self.root
        ))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def _write(self, key, arr):
        path = self.root / (key + ".tif")
        with rasterio.open(path, "w", driver="GTiff", height=10, width=10,
                           count=1, dtype=str(arr.dtype), crs="EPSG:4326",
                           transform=self.transform, nodata=0) as dst:
            dst.write(arr, 1)
        self.item["assets"][key] = {"href": str(path)}

    def test_expected_local_window_ratio_and_pixel_limits(self):
        result = stac.calculate_window_ndvi(self.item, self.bbox)
        self.assertEqual(result["status"], "EXPLORATORY_REVIEW_ONLY")
        self.assertAlmostEqual(result["mean_ndvi_dn_ratio"], 0.5, places=5)
        self.assertEqual(result["read_window_pixel_count"], 64)
        self.assertEqual(result["valid_pixel_count"], 64)
        self.assertFalse(result["radiometric_offset_and_scale_verified"])
        self.assertFalse(result["deforestation_determined"])
        self.assertFalse(result["asset_urls_logged"])

    def test_cloud_mask_reduces_valid_pixel_count(self):
        scl = np.full((10, 10), 4, dtype="uint16")
        scl[2, 2] = 9  # high-probability cloud class
        self._write("SCL", scl)
        result = stac.calculate_window_ndvi(self.item, self.bbox)
        self.assertEqual(result["valid_pixel_count"], 63)
        self.assertAlmostEqual(result["mean_ndvi_dn_ratio"], 0.5, places=5)

    def test_all_clouds_return_no_evidence(self):
        self._write("SCL", np.full((10, 10), 9, dtype="uint16"))
        with self.assertRaises(stac.PreflightError):
            stac.calculate_window_ndvi(self.item, self.bbox)

    def test_window_outside_raster_is_rejected(self):
        with self.assertRaises(stac.PreflightError):
            stac.calculate_window_ndvi(self.item, [-46.20, -23.59, -46.19, -23.58])

    def test_pixel_budget_is_enforced(self):
        with patch.object(stac, "MAX_PIXELS", 25):
            with self.assertRaises(stac.PreflightError):
                stac.calculate_window_ndvi(self.item, self.bbox)


if __name__ == "__main__":
    unittest.main()
