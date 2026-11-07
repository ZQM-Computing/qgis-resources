"""Unit checks for bounded screening triage and conservative decision semantics."""
from __future__ import annotations
from copy import deepcopy
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from screening_triage import build_triage


def fixture():
    return {
        "input_geometry": "synthetic-only",
        "human_review": "pending",
        "regulatory_determination": False,
        "study_area_m2": 100.0,
        "source_results": [
            {
                "source_id": "wetlands",
                "declared_coverage": "verified",
                "finding": "synthetic-mapped-overlap",
                "measured_intersection_area_m2": 25.0,
                "measured_intersection_percent": 25.0,
            },
            {
                "source_id": "flood",
                "declared_coverage": "unavailable",
                "finding": "coverage-unavailable-no-absence-inference",
                "measured_intersection_area_m2": None,
                "measured_intersection_percent": None,
            },
        ],
    }


def test_overlap_and_missing_source_escalate_without_liability_claim():
    result = build_triage(fixture())
    assert result["decision"] == "REVIEW"
    assert result["priority"] == "mapped-constraint-and-gaps"
    assert result["mapped_constraint_sources"] == ["wetlands"]
    assert result["coverage_gap_sources"] == ["flood"]
    assert result["financial_liability_estimate"] is None
    assert result["regulatory_determination"] is False


def test_no_overlap_never_go():
    data = fixture()
    data["source_results"] = [{
        **data["source_results"][0],
        "finding": "synthetic-no-mapped-overlap-not-a-clearance",
        "measured_intersection_area_m2": 0,
        "measured_intersection_percent": 0,
    }]
    result = build_triage(data)
    assert result["decision"] == "INSUFFICIENT_EVIDENCE"
    assert result["priority"] == "no-regulatory-clearance"


def test_only_missing_never_appears_clear():
    data = fixture()
    data["source_results"] = data["source_results"][1:]
    assert build_triage(data)["priority"] == "coverage-gap"


@pytest.mark.parametrize("mutation", [
    lambda d: d["source_results"][0].update(measured_intersection_area_m2=float("nan")),
    lambda d: d["source_results"][0].update(measured_intersection_percent=110),
    lambda d: d["source_results"][0].update(measured_intersection_area_m2=101),
    lambda d: d["source_results"][1].update(measured_intersection_area_m2=0),
    lambda d: d["source_results"][0].update(finding="go"),
    lambda d: d.update(human_review="approved"),
    lambda d: d["source_results"][1].update(source_id="wetlands"),
    lambda d: d["source_results"][0].update(declared_coverage="missing"),
    lambda d: d["source_results"][0].update(finding="synthetic-no-mapped-overlap-not-a-clearance"),
])
def test_invalid_or_misleading_evidence_fails_closed(mutation):
    data = fixture()
    mutation(data)
    with pytest.raises(ValueError):
        build_triage(data)


def test_pure_determinism():
    data = fixture()
    saved = deepcopy(data)
    assert build_triage(data) == build_triage(data)
    assert data == saved



@pytest.mark.parametrize("field,value", [
    ("finding", ["synthetic-mapped-overlap"]),
    ("declared_coverage", ["verified"]),
    ("finding", {"synthetic-mapped-overlap": True}),
    ("declared_coverage", {"verified": True}),
    ("finding", None),
    ("declared_coverage", None),
])
def test_unhashable_or_wrong_type_categories_are_rejected_as_value_errors(field, value):
    data = fixture()
    data["source_results"][0][field] = value
    with pytest.raises(ValueError, match="unsupported finding or coverage"):
        build_triage(data)


@pytest.mark.parametrize("intersected,percent", [
    (25.0, 26.0),
    (25.0, 90.0),
    (0.0, 50.0),
    (75.0, 1.0),
])
def test_contradictory_area_percentage_never_passes_review(intersected, percent):
    data = fixture()
    item = data["source_results"][0]
    item["measured_intersection_area_m2"] = intersected
    item["measured_intersection_percent"] = percent
    with pytest.raises(ValueError):
        build_triage(data)


def test_accepts_expected_metric_rounding_without_changing_inputs():
    data = fixture()
    data["study_area_m2"] = 49226557688.123
    data["source_results"][0]["measured_intersection_area_m2"] = 12304814950.123
    data["source_results"][0]["measured_intersection_percent"] = round(
        100 * 12304814950.123 / 49226557688.123, 6
    )
    before = deepcopy(data)
    assert build_triage(data)["decision"] == "REVIEW"
    assert data == before
