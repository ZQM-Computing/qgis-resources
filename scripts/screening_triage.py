"""Conservative, deterministic triage of the synthetic screening measurement ledger.

Not a regulatory, underwriting, investment, engineering, or legal decision.
No GO/NO-GO financial output is possible from these inputs.
"""
from __future__ import annotations
import math

KNOWN_FINDINGS = {
    "synthetic-mapped-overlap",
    "synthetic-no-mapped-overlap-not-a-clearance",
    "partial-source-measured-not-comprehensive",
    "coverage-unavailable-no-absence-inference",
    "external-reference-not-fetched-no-inference",
}
MEASURED_FINDINGS = {
    "synthetic-mapped-overlap",
    "synthetic-no-mapped-overlap-not-a-clearance",
    "partial-source-measured-not-comprehensive",
}


def build_triage(measurements: dict) -> dict:
    """Reject inconsistent evidence; explicitly preserve source gaps and uncertainty."""
    if not isinstance(measurements, dict):
        raise ValueError("measurement ledger required")
    if (measurements.get("input_geometry") != "synthetic-only"
            or measurements.get("regulatory_determination") is not False
            or measurements.get("human_review") != "pending"):
        raise ValueError("unsupported screening authority or geometry")
    results = measurements.get("source_results")
    area = measurements.get("study_area_m2")
    if not isinstance(results, list) or not results or len(results) > 32:
        raise ValueError("nonempty bounded source results required")
    if isinstance(area, bool) or not isinstance(area, (int, float)) or not math.isfinite(area) or area <= 0:
        raise ValueError("invalid study area")
    seen = set()
    flagged, gaps, observed_no_overlap = [], [], []
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValueError("invalid source result")
        source_id = result.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in seen:
            raise ValueError("invalid or duplicate source identifier")
        seen.add(source_id)
        finding = result.get("finding")
        coverage = result.get("declared_coverage")
        if finding not in KNOWN_FINDINGS or coverage not in {"verified", "partial", "missing", "unavailable", "unverified"}:
            raise ValueError("unsupported finding or coverage")
        measured = finding in MEASURED_FINDINGS
        percent = result.get("measured_intersection_percent")
        intersected = result.get("measured_intersection_area_m2")
        if measured:
            if coverage not in ({"partial"} if finding == "partial-source-measured-not-comprehensive" else {"verified"}):
                raise ValueError("finding conflicts with coverage")
            if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in (percent, intersected)):
                raise ValueError("measured finding requires finite values")
            if not 0 <= percent <= 100 or not 0 <= intersected <= area * (1 + 1e-9):
                raise ValueError("intersection exceeds study area")
            if finding == "synthetic-mapped-overlap" and (percent <= 0 or intersected <= 0):
                raise ValueError("mapped overlap must be positive")
            if finding == "synthetic-no-mapped-overlap-not-a-clearance" and (percent != 0 or intersected != 0):
                raise ValueError("no-overlap finding must measure zero")
            if finding == "synthetic-mapped-overlap":
                flagged.append(source_id)
            elif finding == "synthetic-no-mapped-overlap-not-a-clearance":
                observed_no_overlap.append(source_id)
            else:
                gaps.append(source_id)
                if intersected > 0:
                    flagged.append(source_id)
        else:
            if intersected is not None or percent is not None:
                raise ValueError("unassessed source cannot carry measured zero")
            if finding == "coverage-unavailable-no-absence-inference" and coverage in {"verified", "partial"}:
                raise ValueError("usable coverage must be assessed or explicitly marked unfetched")
            gaps.append(source_id)
    return {
        "schema_version": 1,
        "decision": "REVIEW" if flagged else "INSUFFICIENT_EVIDENCE",
        "priority": "mapped-constraint-and-gaps" if flagged and gaps else (
            "mapped-constraint" if flagged else ("coverage-gap" if gaps else "no-regulatory-clearance")
        ),
        "mapped_constraint_sources": flagged,
        "coverage_gap_sources": gaps,
        "measured_no_overlap_sources": observed_no_overlap,
        "human_review_required": True,
        "regulatory_determination": False,
        "financial_liability_estimate": None,
        "scope": "synthetic-test-only",
        "explanation": "A mapped polygon overlap is not a jurisdictional boundary or liability determination. No overlap is not clearance.",
    }
