#!/usr/bin/env python3
"""Offline, conservative imagery job cost gate. Never triggers network or purchases.

Costs are computed from declared metering and declared price inputs. They are
neither provider invoices nor guaranteed estimates, and a PASS is only a budget
preflight, not permission to use licensed imagery or publish outputs.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation, ROUND_UP
import json
from pathlib import Path
import sys

MAX_FILE_BYTES = 64 * 1024
MAX_REMOTE_REQUESTS = 100
MAX_RANGE_BYTES = 2_000_000_000
MAX_COMPUTE_SECONDS = 3600
MAX_REVIEW_MINUTES = 240
MAX_TOTAL_USD = Decimal("10000.00")
CENT = Decimal("0.01")


class BudgetError(ValueError):
    pass


def _pairs_unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BudgetError("duplicate JSON field")
        result[key] = value
    return result


def _decimal(value, name, maximum, *, allow_zero=True):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise BudgetError(f"invalid {name}")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BudgetError(f"invalid {name}") from exc
    if not parsed.is_finite() or parsed < 0 or parsed > maximum or (not allow_zero and parsed == 0):
        raise BudgetError(f"out-of-range {name}")
    return parsed


def _count(value, name, maximum):
    if type(value) is not int or value < 0 or value > maximum:
        raise BudgetError(f"invalid {name}")
    return value


def calculate(plan):
    if not isinstance(plan, dict) or set(plan) != {
        "schema_version", "scope", "request_count", "estimated_range_bytes",
        "estimated_compute_seconds", "estimated_review_minutes", "rates",
        "approved_spend_ceiling_usd", "paid_imagery_requested",
    }:
        raise BudgetError("missing or unrecognized budget keys")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1 or plan["scope"] != "preflight-no-purchase":
        raise BudgetError("unsupported budget policy")
    if plan["paid_imagery_requested"] is not False:
        raise BudgetError("paid imagery not authorized in this pipeline")
    requests = _count(plan["request_count"], "request_count", MAX_REMOTE_REQUESTS)
    byte_count = _count(plan["estimated_range_bytes"], "estimated_range_bytes", MAX_RANGE_BYTES)
    duration = _count(plan["estimated_compute_seconds"], "estimated_compute_seconds", MAX_COMPUTE_SECONDS)
    minutes = _count(plan["estimated_review_minutes"], "estimated_review_minutes", MAX_REVIEW_MINUTES)
    rates = plan["rates"]
    if not isinstance(rates, dict) or set(rates) != {
        "per_request_usd", "per_gb_egress_usd", "per_compute_hour_usd",
        "per_review_hour_usd",
    }:
        raise BudgetError("missing or unrecognized price inputs")
    prices = {k: _decimal(v, k, Decimal("10000")) for k, v in rates.items()}
    ceiling = _decimal(plan["approved_spend_ceiling_usd"], "spend ceiling", MAX_TOTAL_USD)
    # Conservative USD rounding: do not round down an estimated expense.
    breakdown = {
        "remote_requests": Decimal(requests) * prices["per_request_usd"],
        "remote_egress": (Decimal(byte_count) / Decimal(1_000_000_000)) * prices["per_gb_egress_usd"],
        "processing": (Decimal(duration) / Decimal(3600)) * prices["per_compute_hour_usd"],
        "human_review": (Decimal(minutes) / Decimal(60)) * prices["per_review_hour_usd"],
    }
    total = sum(breakdown.values())
    upper = total.quantize(CENT, rounding=ROUND_UP)
    return {
        "schema_version": 1,
        "decision": "WITHIN_DECLARED_BUDGET_ONLY" if upper <= ceiling else "BLOCKED_OVER_BUDGET",
        "estimated_cost_upper_rounded_usd": str(upper),
        "declared_spend_ceiling_usd": str(ceiling.quantize(CENT)),
        "cost_components_usd": {key: str(value.quantize(CENT, rounding=ROUND_UP))
                                for key, value in sorted(breakdown.items())},
        "remote_requests": requests,
        "estimated_range_bytes": byte_count,
        "cost_rates_independently_verified": False,
        "actual_cloud_egress_measured": False,
        "provider_terms_verified": False,
        "purchase_authorized": False,
        "processing_authorized": False,
        "commercial_delivery_authorized": False,
        "human_review_required": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("budget_plan", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.budget_plan.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise BudgetError("oversized plan")
        plan = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(BudgetError("nonfinite JSON")))
        result = calculate(plan)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["decision"] == "WITHIN_DECLARED_BUDGET_ONLY" else 1
    except (BudgetError, OSError, UnicodeError, TypeError, ValueError):
        print("imagery-budget-preflight-invalid", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
