"""Offline GeoJSON polygon acceptance tests; no remote imagery or customer data."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stac_aoi
import stac_cog_ndvi_preflight as stac

BBOX = [-46.69, -23.59, -46.61, -23.51]


def fixture():
    return json.loads((ROOT / "fixtures" / "stac-aoi-synthetic.geojson").read_text())


@unittest.skipUnless(importlib.util.find_spec("shapely") is not None, "Shapely required")
class AoiGeometryTests(unittest.TestCase):
    def test_valid_polygon_does_not_mutate_source(self):
        geometry = fixture()
        original = deepcopy(geometry)
        self.assertEqual(stac_aoi.validate_aoi(geometry, BBOX), geometry)
        self.assertEqual(geometry, original)

    def test_rejects_nonpolygon_and_out_of_scope_geometry(self):
        cases = [
            {"type": "Point", "coordinates": [-46.65, -23.54]},
            {"type": "Feature", "geometry": fixture(), "properties": {}},
            {"type": "Polygon", "coordinates": [[
                [-46.71, -23.56], [-46.64, -23.56],
                [-46.64, -23.52], [-46.71, -23.56],
            ]]},
            {"type": "Polygon", "coordinates": [[
                [-46.68, -23.56], [-46.64, -23.56],
                [-46.64, -23.52], [-46.68, -23.52],
            ]]},
        ]
        for geometry in cases:
            with self.subTest(geometry=geometry), self.assertRaises(stac_aoi.AoiError):
                stac_aoi.validate_aoi(geometry, BBOX)

    def test_rejects_self_crossing_and_overlapping_multipolygons(self):
        crossed = {"type": "Polygon", "coordinates": [[
            [-46.68, -23.56], [-46.64, -23.52],
            [-46.68, -23.52], [-46.64, -23.56],
            [-46.68, -23.56],
        ]]}
        overlapping = {"type": "MultiPolygon",
                       "coordinates": [fixture()["coordinates"], fixture()["coordinates"]]}
        for geometry in (crossed, overlapping):
            with self.subTest(geometry=geometry), self.assertRaises(stac_aoi.AoiError):
                stac_aoi.validate_aoi(geometry, BBOX)

    def test_rejects_nan_bool_and_large_vertex_counts(self):
        for value in (float("nan"), True):
            g = fixture()
            g["coordinates"][0][1][0] = value
            with self.subTest(value=value), self.assertRaises(stac_aoi.AoiError):
                stac_aoi.validate_aoi(g, BBOX)
        g = fixture()
        ring = [[-46.68, -23.56], [-46.64, -23.56], [-46.64, -23.52]]
        g["coordinates"][0] = (ring * 667) + [ring[0]]
        with self.assertRaises(stac_aoi.AoiError):
            stac_aoi.validate_aoi(g, BBOX)

    def test_rejects_duplicate_json_keys_and_nonfinite_json(self):
        for raw in (
            '{"type":"Polygon","type":"MultiPolygon","coordinates":[]}',
            '{"type":"Polygon","coordinates":[[[0,NaN]]]}',
        ):
            with TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.geojson"
                path.write_text(raw)
                with self.assertRaises(stac_aoi.AoiError):
                    stac_aoi.load_aoi(path, BBOX)

    def test_offline_cli_accepts_valid_boundary_metadata_only(self):
        args = [
            "--bbox", "-46.69", "-23.59", "-46.61", "-23.51",
            "--start", "2026-10-01", "--end", "2026-10-31",
            "--fixture", str(ROOT / "fixtures" / "stac-sentinel-synthetic-item.json"),
            "--aoi-geojson", str(ROOT / "fixtures" / "stac-aoi-synthetic.geojson"),
        ]
        self.assertEqual(stac.main(args), 0)

    def test_cli_refuses_invalid_polygon_before_optional_network(self):
        from unittest.mock import patch
        with TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.geojson"
            bad.write_text('{"type":"Point","coordinates":[-46.65,-23.54]}')
            args = [
                "--bbox", "-46.69", "-23.59", "-46.61", "-23.51",
                "--start", "2026-10-01", "--end", "2026-10-31",
                "--allow-network",
                "--budget-plan", str(ROOT / "fixtures" / "stac-cost-budget-synthetic.json"),
                "--aoi-geojson", str(bad),
            ]
            with patch.object(stac, "search_scene", side_effect=AssertionError("unwanted network")):
                self.assertEqual(stac.main(args), 2)


if __name__ == "__main__":
    unittest.main()
