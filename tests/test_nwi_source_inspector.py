"""Offline, no-network contract tests for bounded USFWS NWI source inspection."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nwi_source_inspector as nwi  # noqa: E402

BBOX = (-81.01, 29.01, -81.00, 29.02)


def shape(oid: int) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "OBJECTID": oid, "ATTRIBUTE": "PFO1A", "WETLAND_TYPE": "Freshwater Forested/Shrub Wetland",
            "UNTRUSTED_HTML": "<script>unsafe</script>",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-81.009, 29.011], [-81.005, 29.011],
                [-81.005, 29.015], [-81.009, 29.011],
            ]],
        },
    }


def metadata(**overrides):
    result = {
        "id": 0, "name": "Wetlands", "geometryType": "esriGeometryPolygon",
        "capabilities": "Map,Query,Data", "supportedQueryFormats": "JSON, geoJSON, PBF",
        "maxRecordCount": 500,
        "fields": [
            {"name": "OBJECTID", "type": "esriFieldTypeOID"},
            {"name": "ATTRIBUTE", "type": "esriFieldTypeString"},
            {"name": "WETLAND_TYPE", "type": "esriFieldTypeString"},
        ],
        "advancedQueryCapabilities": {"supportsPagination": True, "supportsOrderBy": True},
    }
    return {**result, **overrides}


def fake_source(count=2, alter=None):
    calls = []

    def fetch(url):
        calls.append(url)
        params = parse_qs(urlsplit(url).query)
        if urlsplit(url).path == urlsplit(nwi.LAYER_URL).path:
            return metadata()
        if params.get("returnCountOnly") == ["true"]:
            return {"count": count}
        offset = int(params["resultOffset"][0])
        requested = int(params["resultRecordCount"][0])
        result = {
            "type": "FeatureCollection",
            "features": [shape(x) for x in range(offset + 1, offset + requested + 1)],
        }
        return alter(result, offset) if alter else result

    return fetch, calls


def test_small_florida_inspection_is_reconciled_but_never_commercially_cleared():
    fetch, calls = fake_source()
    value = nwi.collect(BBOX, fetch, obtained_at="2026-11-07T20:00:00Z")
    assert value["source"]["features_reconciled"] == 2
    assert value["status"] == "inspection-only-not-screened"
    assert value["coverage_state"] == "unverified"
    assert value["reuse_rights"] == "unverified"
    assert value["regulatory_determination"] is False
    assert value["human_review"] == "pending"
    assert value["source"]["requested_output_crs"] == "EPSG:4326"
    assert len(value["feature_collection"]["features"]) == 2
    assert list(value["feature_collection"]["features"][0]["properties"]) == [
        "OBJECTID", "ATTRIBUTE", "WETLAND_TYPE"
    ]
    assert "UNTRUSTED_HTML" not in json.dumps(value)
    assert len(calls) == 3
    assert calls[0] == nwi.LAYER_URL + "?f=json"
    query = parse_qs(urlsplit(calls[-1]).query)
    assert query["orderByFields"] == ["OBJECTID ASC"]
    assert query["outSR"] == ["4326"]
    assert query["spatialRel"] == ["esriSpatialRelIntersects"]
    assert query["resultRecordCount"] == ["2"]


def test_zero_count_is_not_proof_of_no_wetland():
    fetch, _ = fake_source(0)
    value = nwi.collect(BBOX, fetch)
    assert value["source"]["features_reconciled"] == 0
    assert value["coverage_state"] == "unverified"
    assert value["feature_collection"]["features"] == []


def test_pagination_recovers_exact_count_and_queries_each_page():
    fetch, urls = fake_source(123)
    value = nwi.collect(BBOX, fetch)
    assert len(value["feature_collection"]["features"]) == 123
    query_urls = [url for url in urls if "resultOffset" in url]
    assert len(query_urls) == 2
    assert parse_qs(urlsplit(query_urls[0]).query)["resultRecordCount"] == ["100"]
    assert parse_qs(urlsplit(query_urls[1]).query)["resultOffset"] == ["100"]
    assert parse_qs(urlsplit(query_urls[1]).query)["resultRecordCount"] == ["23"]


@pytest.mark.parametrize("count", [-1, 201, "2", None, True])
def test_invalid_or_unbounded_count_fails_closed(count):
    fetch, _ = fake_source(count)
    with pytest.raises(nwi.SourceInspectionError):
        nwi.collect(BBOX, fetch)


def test_incomplete_page_or_duplicate_id_fails_closed():
    def short_page(payload, offset):
        payload["features"].pop()
        return payload

    with pytest.raises(nwi.SourceInspectionError, match="incomplete"):
        nwi.collect(BBOX, fake_source(2, short_page)[0])

    def duplicate(payload, offset):
        payload["features"][1]["properties"]["OBJECTID"] = 1
        return payload

    with pytest.raises(nwi.SourceInspectionError, match="duplicate"):
        nwi.collect(BBOX, fake_source(2, duplicate)[0])


def test_invalid_layer_metadata_blocks_retrieval_before_count():
    for bad in (
        {"geometryType": "esriGeometryPoint"},
        {"name": "Not Wetlands"},
        {"maxRecordCount": 20},
        {"advancedQueryCapabilities": {"supportsPagination": False}},
    ):
        def fetch(url, replacement=bad):
            return metadata(**replacement)
        with pytest.raises(nwi.SourceInspectionError):
            nwi.collect(BBOX, fetch)


def test_reject_non_polygon_or_malformed_coordinates():
    for invalid in (
        {"type": "Point", "coordinates": [-81, 29]},
        {"type": "Polygon", "coordinates": [[[-81, 29], [-81, 29], [-81, 29], [-80, 29]]]},
        {"type": "Polygon", "coordinates": [[[-81, 29], [-80, 29], [-80, float("nan")], [-81, 29]]]},
    ):
        def corrupt(payload, _offset):
            payload["features"][0]["geometry"] = invalid
            return payload
        with pytest.raises(nwi.SourceInspectionError):
            nwi.collect(BBOX, fake_source(2, corrupt)[0])


@pytest.mark.parametrize("bbox", [
    (-81, 29, -80.9, 29.01),  # too wide
    (-100, 29, -99.99, 29.01),  # outside Florida
    (-81, 29, -81, 29.01),  # empty
    (-81, 29, -80.99, 29.01 + float("inf")),
    (False, 29, -80.99, 29.01),
])
def test_reject_invalid_or_out_of_scope_bbox_before_network(bbox):
    fetch, urls = fake_source()
    with pytest.raises(nwi.SourceInspectionError):
        nwi.collect(bbox, fetch)
    assert urls == []


def test_http_client_rejects_unknown_domains_without_network():
    with pytest.raises(nwi.SourceInspectionError, match="allowlisted"):
        nwi._http_json("https://example.org/arcgis/rest/services/Wetlands/MapServer/0?f=json")
    with pytest.raises(nwi.SourceInspectionError, match="allowlisted"):
        nwi._http_json("http://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0?f=json")


def test_source_json_decoder_fails_on_duplicate_keys_and_nonfinite():
    for raw in (
        b'{"count": 1, "count": 2}',
        b'{"count": NaN}',
        b'{"error": {"code": 503}}',
        b'[]',
    ):
        with pytest.raises(nwi.SourceInspectionError):
            nwi._decode_json(raw)


def test_atomic_snapshot_refuses_overwrite_and_preserves_original(tmp_path):
    fetch, _ = fake_source()
    value = nwi.collect(BBOX, fetch, obtained_at="2026-11-07T20:00:00Z")
    destination = tmp_path / "nwi-snapshot.json"
    digest = nwi.publish_snapshot(destination, value)
    assert len(digest) == 64
    assert json.loads(destination.read_text())["status"] == "inspection-only-not-screened"
    original = destination.read_bytes()
    with pytest.raises(nwi.SourceInspectionError, match="destination exists"):
        nwi.publish_snapshot(destination, {"different": True})
    assert destination.read_bytes() == original
    assert list(tmp_path.glob(".nwi-inspect-*")) == []


def test_atomic_snapshot_failure_removes_temporary_data(tmp_path, monkeypatch):
    destination = tmp_path / "nwi-snapshot.json"
    def deny_link(*args):
        raise OSError("blocked publication")
    monkeypatch.setattr(nwi.os, "link", deny_link)
    with pytest.raises(OSError):
        nwi.publish_snapshot(destination, {"safe": True})
    assert not destination.exists()
    assert list(tmp_path.glob(".nwi-inspect-*")) == []


def test_no_network_without_explicit_flag(tmp_path, monkeypatch, capsys):
    def unexpected(_):
        raise AssertionError("network should not occur")
    monkeypatch.setattr(nwi, "_http_json", unexpected)
    result = nwi.main([
        "--bbox", "-81.01", "29.01", "-81.0", "29.02",
        "--out", str(tmp_path / "no.json"),
    ])
    assert result == 2
    assert "No network request made" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []



def test_rejects_nonmonotonic_ids_even_when_unique():
    def wrong_order(payload, offset):
        payload["features"][0]["properties"]["OBJECTID"] = 19
        payload["features"][1]["properties"]["OBJECTID"] = 5
        return payload

    with pytest.raises(nwi.SourceInspectionError, match="out-of-order"):
        nwi.collect(BBOX, fake_source(2, wrong_order)[0])


def test_rejects_mismatched_geojson_crs_and_truncation_signals():
    def wrong_crs(payload, offset):
        payload["crs"] = {"type": "name", "properties": {"name": "EPSG:3857"}}
        return payload

    def bad_transfer_flag(payload, offset):
        payload["exceededTransferLimit"] = "true"
        return payload

    for transform in (wrong_crs, bad_transfer_flag):
        with pytest.raises(nwi.SourceInspectionError):
            nwi.collect(BBOX, fake_source(2, transform)[0])


def test_rejects_nonfinite_z_values_and_missing_required_wetland_type():
    def bad_z(payload, offset):
        ring = payload["features"][0]["geometry"]["coordinates"][0]
        ring[0] = [ring[0][0], ring[0][1], float("nan")]
        ring[-1] = ring[0][:]
        return payload

    def missing_wetland_type(payload, offset):
        payload["features"][0]["properties"]["WETLAND_TYPE"] = None
        return payload

    for transform in (bad_z, missing_wetland_type):
        with pytest.raises(nwi.SourceInspectionError):
            nwi.collect(BBOX, fake_source(2, transform)[0])


def test_source_hash_and_pagination_disclaimers_are_stable():
    first = nwi.collect(BBOX, fake_source(2)[0], obtained_at="2026-11-07T20:00:00Z")
    second = nwi.collect(BBOX, fake_source(2)[0], obtained_at="2026-11-07T20:00:00Z")
    assert first == second
    assert first["source"]["normalized_geojson_sha256"] == second["source"]["normalized_geojson_sha256"]
    assert len(first["source"]["normalized_geojson_sha256"]) == 64
    assert "point-in-time-snapshot-unverified" in first["source"]["feature_pagination_integrity"]
    assert first["source"]["feature_vertices_checked"] > 0
    assert first["coverage_state"] == "unverified"
    assert first["reuse_rights"] == "unverified"


def test_layer_metadata_accepts_whitespace_variations_but_rejects_boolean_id():
    layer = metadata(supportedQueryFormats="JSON,geoJSON,PBF", capabilities="Map, Query, Data")
    nwi._verify_layer(layer)
    with pytest.raises(nwi.SourceInspectionError):
        nwi._verify_layer(metadata(id=False))



@pytest.mark.parametrize("timestamp", ["fakeZ", "2026-11-07Z", "2026-15-07T20:00:00Z", "+00:00"])
def test_rejects_malformed_provenance_timestamp(timestamp):
    with pytest.raises(nwi.SourceInspectionError):
        nwi.collect(BBOX, fake_source(2)[0], obtained_at=timestamp)



def test_malformed_provider_container_responses_fail_closed():
    for invalid in ([], "not json", None):
        with pytest.raises(nwi.SourceInspectionError, match="layer metadata"):
            nwi.collect(BBOX, lambda _url, value=invalid: value)

        def bad_count(url, value=invalid):
            if urlsplit(url).path == urlsplit(nwi.LAYER_URL).path:
                return metadata()
            return value

        with pytest.raises(nwi.SourceInspectionError, match="count response"):
            nwi.collect(BBOX, bad_count)

        def bad_page(url, value=invalid):
            p = parse_qs(urlsplit(url).query)
            if urlsplit(url).path == urlsplit(nwi.LAYER_URL).path:
                return metadata()
            if p.get("returnCountOnly") == ["true"]:
                return {"count": 1}
            return value

        with pytest.raises(nwi.SourceInspectionError, match="feature page"):
            nwi.collect(BBOX, bad_page)


def test_existing_or_invalid_output_is_rejected_before_any_network(tmp_path, monkeypatch):
    output = tmp_path / "existing.json"
    output.write_text('{"previous":true}')
    called = []

    def untrusted_network(url):
        called.append(url)
        raise AssertionError("Network should never run after a bad output preflight")

    monkeypatch.setattr(nwi, "_http_json", untrusted_network)
    for destination in (output, tmp_path / "bad.txt", tmp_path / "missing" / "out.json"):
        result = nwi.main([
            "--bbox", "-81.01", "29.01", "-81.0", "29.02",
            "--out", str(destination), "--network",
        ])
        assert result == 1
    assert called == []
    assert output.read_text() == '{"previous":true}'
    assert not list(tmp_path.glob(".nwi-inspect-*"))


def test_reject_schema_drift_and_malformed_field_type_metadata():
    """Reject a layer that changes required field semantics or metadata shape."""
    for fields in (
        [],
        None,
        [{"name": ["OBJECTID"], "type": "esriFieldTypeOID"}],
        [
            {"name": "OBJECTID", "type": "esriFieldTypeString"},
            {"name": "ATTRIBUTE", "type": "esriFieldTypeString"},
            {"name": "WETLAND_TYPE", "type": "esriFieldTypeString"},
        ],
        [
            {"name": "OBJECTID", "type": "esriFieldTypeOID"},
            {"name": "OBJECTID", "type": "esriFieldTypeOID"},
            {"name": "ATTRIBUTE", "type": "esriFieldTypeString"},
            {"name": "WETLAND_TYPE", "type": "esriFieldTypeString"},
        ],
    ):
        with pytest.raises(nwi.SourceInspectionError):
            nwi._verify_layer(metadata(fields=fields))


def test_reject_source_when_ordered_pagination_is_not_supported():
    """Sorted IDs are necessary to detect simple offset-page inconsistencies."""
    with pytest.raises(nwi.SourceInspectionError, match="pagination or ordering"):
        nwi._verify_layer(metadata(
            advancedQueryCapabilities={"supportsPagination": True, "supportsOrderBy": False}
        ))
