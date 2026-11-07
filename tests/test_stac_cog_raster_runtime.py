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

    def test_polygon_mask_excludes_outside_pixels(self):
        import json
        polygon = json.loads((ROOT / "fixtures" / "stac-aoi-synthetic.geojson").read_text())
        result = stac.calculate_window_ndvi(self.item, self.bbox, polygon)
        self.assertTrue(result["aoi_polygon_mask_applied"])
        self.assertEqual(result["read_window_pixel_count"], 64)
        self.assertEqual(result["aoi_pixel_count"], 16)
        self.assertEqual(result["valid_pixel_count"], 16)
        self.assertEqual(result["valid_fraction_of_aoi"], 1.0)
        self.assertAlmostEqual(result["mean_ndvi_dn_ratio"], 0.5, places=5)

    def test_polygon_mask_cloud_and_empty_mask_fail_closed(self):
        import json
        polygon = json.loads((ROOT / "fixtures" / "stac-aoi-synthetic.geojson").read_text())
        scl = np.full((10, 10), 4, dtype="uint16")
        scl[2, 2] = 9
        self._write("SCL", scl)
        result = stac.calculate_window_ndvi(self.item, self.bbox, polygon)
        self.assertEqual(result["aoi_pixel_count"], 16)
        self.assertEqual(result["valid_pixel_count"], 15)
        self.assertAlmostEqual(result["valid_fraction_of_aoi"], 15/16, places=5)
        # A topologically valid micro-polygon can lie between pixel centers.
        tiny = {"type": "Polygon", "coordinates": [[
            [-46.6500, -23.5500], [-46.6499, -23.5500],
            [-46.6499, -23.5499], [-46.6500, -23.5500],
        ]]}
        with self.assertRaises(stac.PreflightError):
            stac.calculate_window_ndvi(self.item, self.bbox, tiny)

    def test_corrected_reflectance_candidate_requires_metadata_and_is_unverified(self):
        import json
        record = json.loads((ROOT / "fixtures" / "stac-radiometry-synthetic.json").read_text())
        self.item["id"] = record["scene_id"]
        baseline = stac.calculate_window_ndvi(self.item, self.bbox)
        self.assertNotIn("radiometric_candidate", baseline)
        candidate = stac.calculate_window_ndvi(self.item, self.bbox, radiometry=record)
        corrected = candidate["radiometric_candidate"]
        self.assertEqual(candidate["mean_ndvi_dn_ratio"], 0.5)
        self.assertAlmostEqual(corrected["mean_ndvi_reflectance_candidate"], 0.666667, places=5)
        self.assertEqual(corrected["corrected_valid_pixel_count"], 64)
        self.assertFalse(corrected["product_metadata_authenticity_verified"])
        self.assertFalse(corrected["customer_ready_ndvi"])
        self.assertFalse(candidate["radiometric_offset_and_scale_verified"])

    def test_prescaled_raster_metadata_blocks_double_radiometric_adjustment(self):
        import json
        record = json.loads((ROOT / "fixtures" / "stac-radiometry-synthetic.json").read_text())
        self.item["id"] = record["scene_id"]
        for band in ("B04", "B08"):
            for metadata_type, value in (("scales", 0.0001), ("offsets", -0.1)):
                with self.subTest(band=band, metadata_type=metadata_type):
                    path = self.root / (band + ".tif")
                    with rasterio.open(path, "r+") as src:
                        setattr(src, metadata_type, (value,))
                    with self.assertRaises(stac.PreflightError, msg="pre-scaled raster must not be corrected"):
                        stac.calculate_window_ndvi(self.item, self.bbox, radiometry=record)
                    with rasterio.open(path, "r+") as src:
                        setattr(src, metadata_type, (1.0 if metadata_type == "scales" else 0.0,))

    def test_wrong_scene_radiometry_is_rejected_before_any_raster_open(self):
        import json
        record = json.loads((ROOT / "fixtures" / "stac-radiometry-synthetic.json").read_text())
        self.item["id"] = "wrong-scene-identifier"
        with patch.object(rasterio, "open", side_effect=AssertionError("opened raster before metadata validation")):
            with self.assertRaises(ValueError):
                stac.calculate_window_ndvi(self.item, self.bbox, radiometry=record)

    def test_negative_reflectance_candidate_is_not_silently_used(self):
        import json
        record = json.loads((ROOT / "fixtures" / "stac-radiometry-synthetic.json").read_text())
        self.item["id"] = record["scene_id"]
        self._write("B04", np.full((10, 10), 500, dtype="uint16"))
        result = stac.calculate_window_ndvi(self.item, self.bbox, radiometry=record)
        candidate = result["radiometric_candidate"]
        self.assertIsNone(candidate["mean_ndvi_reflectance_candidate"])
        self.assertEqual(candidate["corrected_valid_pixel_count"], 0)
        self.assertEqual(candidate["excluded_negative_or_zero_reflectance_pixels"], 64)

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

    def test_partial_raster_coverage_is_blocked_not_reported_as_full(self):
        # A scene may intersect a request but not fully cover it.
        for bbox in (
            [-46.71, -23.59, -46.61, -23.51],
            [-46.69, -23.61, -46.61, -23.51],
            [-46.69, -23.59, -46.59, -23.51],
        ):
            with self.subTest(bbox=bbox), self.assertRaises(stac.PreflightError):
                stac.calculate_window_ndvi(self.item, bbox)

    def test_pixel_budget_is_enforced(self):
        with patch.object(stac, "MAX_PIXELS", 25):
            with self.assertRaises(stac.PreflightError):
                stac.calculate_window_ndvi(self.item, self.bbox)


if __name__ == "__main__":
    unittest.main()
