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
        """Create isolated local fixtures and register cleanup for each test."""
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
        """Write a synthetic single-band raster and attach its path to the test item."""
        path = self.root / (key + ".tif")
        with rasterio.open(path, "w", driver="GTiff", height=10, width=10,
                           count=1, dtype=str(arr.dtype), crs="EPSG:4326",
                           transform=self.transform, nodata=0) as dst:
            dst.write(arr, 1)
        self.item["assets"][key] = {"href": str(path)}

    def test_raster_library_errors_are_wrapped_and_validation_preserved(self):
        """Verify raster library errors are wrapped and validation preserved."""
        from rasterio.errors import WindowError
        for target in ("rasterio.open", "rasterio.warp.transform_bounds",
                       "rasterio.windows.from_bounds", "rasterio.vrt.WarpedVRT"):
            with self.subTest(target=target), patch(target, side_effect=WindowError("secret-token")):
                with self.assertRaisesRegex(stac.PreflightError, "^raster window analysis failed$") as caught:
                    stac.calculate_window_ndvi(self.item, self.bbox)
                self.assertTrue(caught.exception.__suppress_context__)
        original = stac.PreflightError("existing validation failure")
        with patch("rasterio.open", side_effect=original):
            with self.assertRaises(stac.PreflightError) as caught:
                stac.calculate_window_ndvi(self.item, self.bbox)
            self.assertIs(caught.exception, original)

    def test_documented_aoi_bbox_fits_ten_metre_window(self):
        """Verify documented aoi bbox fits ten metre window."""
        import json
        import re
        from rasterio.warp import transform_bounds
        doc = (ROOT / "docs/STAC_COG_NDVI_PREFLIGHT.md").read_text()
        example = next(block for block in re.findall(r"```bash\n(.*?)```", doc, re.S)
                       if "--aoi-geojson fixtures/stac-aoi-synthetic.geojson" in block)
        bbox = stac.check_bbox([float(v) for v in re.search(r"--bbox ([^\n]+)", example)[1].split()[:4]])
        geometry = json.loads((ROOT / "fixtures/stac-aoi-synthetic.geojson").read_text())
        from stac_aoi import validate_aoi
        validate_aoi(geometry, bbox)
        left, bottom, right, top = transform_bounds("EPSG:4326", "EPSG:32723", *bbox)
        # Two extra pixels per axis conservatively allow grid alignment.
        pixels = (int(np.ceil((right-left)/10)) + 2) * (int(np.ceil((top-bottom)/10)) + 2)
        self.assertLess(pixels, stac.MAX_PIXELS)

    def test_expected_local_window_ratio_and_pixel_limits(self):
        """Verify expected local window ratio and pixel limits."""
        result = stac.calculate_window_ndvi(self.item, self.bbox)
        self.assertEqual(result["status"], "EXPLORATORY_REVIEW_ONLY")
        self.assertAlmostEqual(result["mean_ndvi_dn_ratio"], 0.5, places=5)
        self.assertEqual(result["read_window_pixel_count"], 64)
        self.assertEqual(result["valid_pixel_count"], 64)
        self.assertFalse(result["radiometric_offset_and_scale_verified"])
        self.assertFalse(result["deforestation_determined"])
        self.assertFalse(result["asset_urls_logged"])

    def test_polygon_mask_excludes_outside_pixels(self):
        """Verify polygon mask excludes outside pixels."""
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
        """Verify polygon mask cloud and empty mask fail closed."""
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
        """Verify corrected reflectance candidate requires metadata and is unverified."""
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
        """Verify prescaled raster metadata blocks double radiometric adjustment."""
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
        """Verify wrong scene radiometry is rejected before any raster open."""
        import json
        record = json.loads((ROOT / "fixtures" / "stac-radiometry-synthetic.json").read_text())
        self.item["id"] = "wrong-scene-identifier"
        with patch.object(rasterio, "open", side_effect=AssertionError("opened raster before metadata validation")):
            with self.assertRaises(ValueError):
                stac.calculate_window_ndvi(self.item, self.bbox, radiometry=record)

    def test_negative_reflectance_candidate_is_not_silently_used(self):
        """Verify negative reflectance candidate is not silently used."""
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
        """Verify cloud mask reduces valid pixel count."""
        scl = np.full((10, 10), 4, dtype="uint16")
        scl[2, 2] = 9  # high-probability cloud class
        self._write("SCL", scl)
        result = stac.calculate_window_ndvi(self.item, self.bbox)
        self.assertEqual(result["valid_pixel_count"], 63)
        self.assertAlmostEqual(result["mean_ndvi_dn_ratio"], 0.5, places=5)

    def test_all_clouds_return_no_evidence(self):
        """Verify all clouds return no evidence."""
        self._write("SCL", np.full((10, 10), 9, dtype="uint16"))
        with self.assertRaises(stac.PreflightError):
            stac.calculate_window_ndvi(self.item, self.bbox)

    def test_window_outside_raster_is_rejected(self):
        """Verify window outside raster is rejected."""
        with self.assertRaises(stac.PreflightError):
            stac.calculate_window_ndvi(self.item, [-46.20, -23.59, -46.19, -23.58])

    def test_partial_raster_coverage_is_blocked_not_reported_as_full(self):
        # A scene may intersect a request but not fully cover it.
        """Verify partial raster coverage is blocked not reported as full."""
        for bbox in (
            [-46.71, -23.59, -46.61, -23.51],
            [-46.69, -23.61, -46.61, -23.51],
            [-46.69, -23.59, -46.59, -23.51],
        ):
            with self.subTest(bbox=bbox), self.assertRaises(stac.PreflightError):
                stac.calculate_window_ndvi(self.item, bbox)

    def test_pixel_budget_is_enforced(self):
        """Verify pixel budget is enforced."""
        with patch.object(stac, "MAX_PIXELS", 25):
            with self.assertRaises(stac.PreflightError):
                stac.calculate_window_ndvi(self.item, self.bbox)


if __name__ == "__main__":
    unittest.main()
