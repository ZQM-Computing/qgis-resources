"""Keep the buyer-facing synthetic handoff example aligned with its source fixture.

Runs in ordinary Python/pytest without QGIS. It checks documentation truth,
not PDF rendering or professional acceptance.
"""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "exhibit-production/fixtures/geopandas-handoff/parcel_screening.json"
SAMPLE = ROOT / "exhibit-production/BUYER_HANDOFF_SAMPLE.md"
SCOPE = ROOT / "docs/ENVIRONMENTAL_GIS_BRIEF_TEMPLATE.md"


def expected_rows():
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    return {(r["parcel_id"], r["constraint_type"]): r for r in data["rows"]}


def documented_table():
    content = SAMPLE.read_text(encoding="utf-8")
    section = content.split("## Expected result by parcel\n", 1)[1].split("\n## ", 1)[0]
    result = {}
    for line in section.splitlines():
        if not line.startswith("| DEMO-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            raise AssertionError("Sample table must have four columns")
        if cells[0] in result:
            raise AssertionError("Duplicate parcel in sample")
        result[cells[0]] = cells
    return result


class BuyerHandoffDocumentation(unittest.TestCase):
    def test_table_matches_two_parcel_fixture(self):
        rows = expected_rows()
        table = documented_table()
        self.assertEqual(set(table), {"DEMO-P1", "DEMO-P2"})
        self.assertEqual(set(rows), {
            ("DEMO-P1", "wetland_inventory"),
            ("DEMO-P1", "flood_hazard"),
            ("DEMO-P2", "wetland_inventory"),
            ("DEMO-P2", "flood_hazard"),
        })

        for parcel_id in table:
            wetland = rows[(parcel_id, "wetland_inventory")]
            flood = rows[(parcel_id, "flood_hazard")]
            wetland_cell, flood_cell, note_cell = table[parcel_id][1:]
            if wetland["coverage_pct_parcel"] == 0:
                self.assertIn("unknown", wetland_cell.lower())
                self.assertNotIn("clear", wetland_cell.lower())
            else:
                self.assertIn(
                    f'{wetland["known_overlap_pct_parcel"]:g}%', wetland_cell
                )
                self.assertIn(
                    f'{wetland["coverage_pct_parcel"]:g}%', wetland_cell
                )
            self.assertIn(f'{flood["known_overlap_pct_parcel"]:g}%', flood_cell)
            self.assertIn(f'{flood["coverage_pct_parcel"]:g}%', flood_cell)
            if wetland["coverage_pct_parcel"] < 100 or flood["coverage_pct_parcel"] < 100:
                self.assertIn("unknown", note_cell.lower())

    def test_document_retains_truth_and_quote_boundaries(self):
        sample = SAMPLE.read_text(encoding="utf-8").lower()
        scope = SCOPE.read_text(encoding="utf-8").lower()
        self.assertIn("not a client deliverable", sample)
        self.assertIn("not a pre-generated pdf download", sample)
        self.assertIn("buyer approval: not sought", sample)
        self.assertIn("not a price", scope)
        self.assertIn("source coverage", scope)
        self.assertIn("revisions", scope)
        self.assertIn("professional", scope)


if __name__ == "__main__":
    unittest.main()
