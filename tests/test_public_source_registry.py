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


def test_2026_parcel_polygon_candidate_is_metadata_only_and_private_fields_excluded():
    candidates = json.loads(REGISTRY.read_text(encoding="utf-8"))["candidates"]
    parcel = next(item for item in candidates if item["id"] == "florida-dor-parcels-2026")
    assert parcel["geometry_type"] == "esriGeometryPolygon"
    assert parcel["service_url"].endswith("/Florida_Statewide_Cadastral/FeatureServer/0")
    assert "August 2026" in parcel["published_edition_claim"]
    assert "not tested" in parcel["published_edition_claim"]
    assert parcel["commercial_use_approved"] is False
    assert parcel["licensing_review"] == "pending"
    assert parcel["actual_feature_coverage"] == "unverified"
    assert "owner names/addresses" in parcel["caveat"]
