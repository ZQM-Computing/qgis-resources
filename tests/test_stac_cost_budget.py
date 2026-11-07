"""USD-based local budget preflight, with no network or purchase execution."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stac_cost_budget as budget


def template():
    """Load a fresh hypothetical no-purchase cost plan."""
    return {
        "schema_version": 1,
        "scope": "preflight-no-purchase",
        "request_count": 10,
        "estimated_range_bytes": 1000000000,
        "estimated_compute_seconds": 3600,
        "estimated_review_minutes": 60,
        "rates": {
            "per_request_usd": "0.01",
            "per_gb_egress_usd": "0.10",
            "per_compute_hour_usd": "1.00",
            "per_review_hour_usd": "20.00"
        },
        "approved_spend_ceiling_usd": "21.20",
        "paid_imagery_requested": False,
    }


class BudgetTests(unittest.TestCase):
    def test_conservative_cost_and_no_operational_approval(self):
        """Verify conservative cost and no operational approval."""
        result = budget.calculate(template())
        self.assertEqual(result["decision"], "WITHIN_DECLARED_BUDGET_ONLY")
        self.assertEqual(result["estimated_cost_upper_rounded_usd"], "21.20")
        for denied in ("actual_cloud_egress_measured", "purchase_authorized",
                       "processing_authorized", "provider_terms_verified",
                       "commercial_delivery_authorized"):
            self.assertFalse(result[denied])

    def test_over_budget_is_blocking(self):
        """Verify over budget is blocking."""
        d = template()
        d["approved_spend_ceiling_usd"] = "21.19"
        result = budget.calculate(d)
        self.assertEqual(result["decision"], "BLOCKED_OVER_BUDGET")
        self.assertEqual(result["estimated_cost_upper_rounded_usd"], "21.20")

    def test_small_nonzero_cost_rounds_up_to_one_cent(self):
        """Verify small nonzero cost rounds up to one cent."""
        d = template()
        for k in d["rates"]:
            d["rates"][k] = "0"
        d["rates"]["per_request_usd"] = "0.00001"
        d["request_count"] = 1
        d["approved_spend_ceiling_usd"] = "0"
        self.assertEqual(budget.calculate(d)["estimated_cost_upper_rounded_usd"], "0.01")
        self.assertEqual(budget.calculate(d)["decision"], "BLOCKED_OVER_BUDGET")

    def test_paid_purchase_never_authorized(self):
        """Verify paid purchase never authorized."""
        for bad in (True, "false", None, 0):
            with self.subTest(bad=bad):
                d = template()
                d["paid_imagery_requested"] = bad
                with self.assertRaises(budget.BudgetError):
                    budget.calculate(d)

    def test_invalid_cost_and_metering_inputs_fail_closed(self):
        """Verify invalid cost and metering inputs fail closed."""
        for field, val in (("request_count", 101),
                           ("request_count", -1),
                           ("request_count", 1.5),
                           ("estimated_range_bytes", 2_000_000_001),
                           ("estimated_compute_seconds", 3601),
                           ("estimated_review_minutes", 241),
                           ("approved_spend_ceiling_usd", "NaN"),
                           ("approved_spend_ceiling_usd", "-5"),
                           ("approved_spend_ceiling_usd", True)):
            with self.subTest(field=field, val=val):
                d = template()
                d[field] = val
                with self.assertRaises(budget.BudgetError):
                    budget.calculate(d)
        for bad in ("Infinity", "nan", -1, True, {}, None):
            d = template()
            d["rates"]["per_gb_egress_usd"] = bad
            with self.subTest(bad=bad), self.assertRaises(budget.BudgetError):
                budget.calculate(d)

    def test_unknown_fields_and_missing_rates_blocked(self):
        """Verify unknown fields and missing rates blocked."""
        for field in ("unapproved_extra",):
            d = template()
            d[field] = "yes"
            with self.assertRaises(budget.BudgetError):
                budget.calculate(d)
        d = template()
        del d["rates"]["per_review_hour_usd"]
        with self.assertRaises(budget.BudgetError):
            budget.calculate(d)

    def test_deterministic_pure(self):
        """Verify deterministic pure."""
        d = template()
        before = deepcopy(d)
        self.assertEqual(budget.calculate(d), budget.calculate(d))
        self.assertEqual(d, before)

    def test_cli_exit_codes_and_json_rejection(self):
        """Verify cli exit codes and json rejection."""
        with TemporaryDirectory() as td:
            p = Path(td) / "budget.json"
            p.write_text(json.dumps(template()), encoding="utf-8")
            self.assertEqual(budget.main([str(p)]), 0)
            d = template()
            d["approved_spend_ceiling_usd"] = "0"
            p.write_text(json.dumps(d), encoding="utf-8")
            self.assertEqual(budget.main([str(p)]), 1)
            for invalid in ('{"schema_version":1,"schema_version":2}',
                            '{"approved_spend_ceiling_usd": NaN}'):
                p.write_text(invalid, encoding="utf-8")
                self.assertEqual(budget.main([str(p)]), 2)


if __name__ == "__main__":
    unittest.main()
