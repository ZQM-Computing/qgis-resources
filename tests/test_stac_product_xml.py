"""Local Sentinel product XML byte/digest and radiometric contract tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from stac_product_xml import verify_local_product_xml
from stac_radiometry import RadiometryError
import stac_cog_ndvi_preflight as preflight

XML = ROOT / "fixtures" / "stac-product-metadata-synthetic.xml"
RECORD = ROOT / "fixtures" / "stac-radiometry-synthetic.json"
STAC = ROOT / "fixtures" / "stac-sentinel-synthetic-item.json"


def record():
    """Load a fresh unverified radiometry record for XML consistency tests."""
    return json.loads(RECORD.read_text())


class ProductXmlTests(unittest.TestCase):
    def test_fixture_digest_and_offsets_match_but_not_source_authenticated(self):
        """Verify fixture digest and offsets match but not source authenticated."""
        original = record()
        self.assertEqual(hashlib.sha256(XML.read_bytes()).hexdigest(),
                         original["product_metadata_sha256"])
        output = verify_local_product_xml(XML, original, original["scene_id"])
        self.assertTrue(output["local_product_xml_sha256_verified"])
        self.assertTrue(output["local_product_xml_radiometric_values_crosschecked"])
        self.assertFalse(output["original_provider_identity_authenticated"])
        self.assertFalse(output["commercial_approval"])

    def test_digest_mismatch_rejected(self):
        """Verify digest mismatch rejected."""
        r = record()
        r["product_metadata_sha256"] = "0" * 64
        with self.assertRaises(RadiometryError):
            verify_local_product_xml(XML, r, r["scene_id"])

    def test_duplicate_baseline_and_offset_differ_from_record(self):
        """Verify duplicate baseline and offset differ from record."""
        original = XML.read_text()
        variants = [
            original.replace("<PROCESSING_BASELINE>05.10", "<PROCESSING_BASELINE>04.00"),
            original.replace("</Product_Info>", "<PROCESSING_BASELINE>05.10</PROCESSING_BASELINE></Product_Info>"),
            original.replace('band_id="7">-1000', 'band_id="7">-999'),
            original.replace("</BOA_ADD_OFFSET_VALUES_LIST>",
                             '<BOA_ADD_OFFSET band_id="7">-1000</BOA_ADD_OFFSET></BOA_ADD_OFFSET_VALUES_LIST>'),
        ]
        for xml in variants:
            with self.subTest(xml=xml[-70:]):
                with TemporaryDirectory() as folder:
                    path = Path(folder) / "changed.xml"
                    path.write_text(xml)
                    r = record()
                    r["product_metadata_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                    with self.assertRaises(RadiometryError):
                        verify_local_product_xml(path, r, r["scene_id"])

    def test_doctype_external_entity_rejected_despite_matching_hash(self):
        """Verify doctype external entity rejected despite matching hash."""
        xml = '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><Level-2A_User_Product/>'
        with TemporaryDirectory() as folder:
            path = Path(folder) / "hostile.xml"
            path.write_text(xml)
            r = record()
            r["product_metadata_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(RadiometryError):
                verify_local_product_xml(path, r, r["scene_id"])

    def test_cli_requires_both_xml_and_json_no_network(self):
        """Verify cli requires both xml and json no network."""
        args = ["--bbox", "-46.63", "-23.55", "-46.60", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31",
                "--fixture", str(STAC)]
        self.assertEqual(preflight.main(args + ["--radiometry-json", str(RECORD)]), 2)
        self.assertEqual(preflight.main(args + ["--product-metadata-xml", str(XML)]), 2)
        self.assertEqual(preflight.main(args + ["--radiometry-json", str(RECORD),
                                               "--product-metadata-xml", str(XML)]), 0)

    def test_mismatched_source_records_block_before_remote_pixel_read(self):
        """Verify mismatched source records block before remote pixel read."""
        args = ["--bbox", "-46.63", "-23.55", "-46.60", "-23.53",
                "--start", "2026-10-01", "--end", "2026-10-31",
                "--allow-network",
                "--budget-plan", str(ROOT / "fixtures" / "stac-cost-budget-synthetic.json")]
        with TemporaryDirectory() as folder:
            path = Path(folder) / "mismatch.json"
            d = record()
            d["product_metadata_sha256"] = "0" * 64
            path.write_text(json.dumps(d))
            scene = json.loads(STAC.read_text())
            with patch.object(preflight, "search_scene", return_value=[scene]):
                with patch.object(preflight, "calculate_window_ndvi",
                                  side_effect=AssertionError("should not read pixels")):
                    self.assertEqual(preflight.main(args + [
                        "--radiometry-json", str(path),
                        "--product-metadata-xml", str(XML), "--stream-window"
                    ]), 2)


if __name__ == "__main__":
    unittest.main()
