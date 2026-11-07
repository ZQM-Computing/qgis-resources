"""Prevent candidate source metadata from being mistaken for commercial approval."""
from __future__ import annotations

import json
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "sources" / "florida-public-candidates.json"


def test_candidate_registry_cannot_claim_authoritative_commercial_approval():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["status"] == "discovery-candidates-not-approved"
    candidates = payload["candidates"]
    assert len(candidates) >= 3
    assert len({item["id"] for item in candidates}) == len(candidates)
    for item in candidates:
        assert item["commercial_use_approved"] is False
        assert item["licensing_review"] == "pending"
        assert item["actual_feature_coverage"] == "unverified"
        assert item["current_effective_edition"] == "unverified"
        assert item["official_reference"].startswith("https://")
        assert item["caveat"]


def test_fws_registry_source_matches_fixed_allowlisted_client_endpoint():
    from nwi_source_inspector import LAYER_URL

    candidates = json.loads(REGISTRY.read_text(encoding="utf-8"))["candidates"]
    nwi = next(item for item in candidates if item["id"] == "usfws-nwi-wetlands")
    assert nwi["service_url"] == LAYER_URL
    assert nwi["screening_use"] == "inspection-only"
    assert nwi["source_maturity"].startswith("published-service-metadata")
