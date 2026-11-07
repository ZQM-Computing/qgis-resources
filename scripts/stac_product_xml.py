"""Offline, digest-bound Sentinel-2 L2A product metadata consistency checker.

Reads a local bounded XML product manifest. It confirms local evidence
consistency, not provider origin, product authenticity, or legal usage rights.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import xml.etree.ElementTree as ET

from stac_radiometry import RadiometryError, validate_radiometry

MAX_XML_BYTES = 2 * 1024 * 1024
MAX_ELEMENTS = 30000
BAND_IDS = {"3": "boa_add_offset_b04", "7": "boa_add_offset_b08"}


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def verify_local_product_xml(path, record, scene_id):
    """Validate original *local* bytes and declared offsets; never trust origins."""
    validate_radiometry(record, scene_id)
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_XML_BYTES + 1)
    if len(raw) > MAX_XML_BYTES:
        raise RadiometryError("product XML exceeds byte limit")
    # Disallow external entities, DTDs and processing instructions to remove
    # XXE and untrusted parser extension paths even in local-only input.
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper or b"<?" in upper.replace(b"<?XML ", b""):
        raise RadiometryError("DTD, entities and XML processing instructions refused")
    if sha256(raw).hexdigest() != record["product_metadata_sha256"]:
        raise RadiometryError("local product XML digest mismatch")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RadiometryError("invalid product XML") from exc
    elements = list(root.iter())
    if len(elements) > MAX_ELEMENTS:
        raise RadiometryError("too many XML elements")
    names = {
        "PROCESSING_BASELINE": [],
        "BOA_QUANTIFICATION_VALUE": [],
        "BOA_ADD_OFFSET": [],
    }
    for element in elements:
        name = _tag(element)
        if name in names:
            names[name].append(element)
    if len(names["PROCESSING_BASELINE"]) != 1 or len(names["BOA_QUANTIFICATION_VALUE"]) != 1:
        raise RadiometryError("missing or duplicate quantification/baseline tag")
    baseline = (names["PROCESSING_BASELINE"][0].text or "").strip()
    if baseline != record["processing_baseline"]:
        raise RadiometryError("product processing baseline mismatch")
    try:
        quantification = float((names["BOA_QUANTIFICATION_VALUE"][0].text or "").strip())
    except ValueError as exc:
        raise RadiometryError("invalid XML quantification") from exc
    if quantification != float(record["boa_quantification_value"]):
        raise RadiometryError("product quantification mismatch")
    offsets = {}
    for offset in names["BOA_ADD_OFFSET"]:
        band = offset.attrib.get("band_id")
        if band not in BAND_IDS:
            continue
        if band in offsets:
            raise RadiometryError("duplicate relevant band offset")
        try:
            offsets[band] = float((offset.text or "").strip())
        except ValueError as exc:
            raise RadiometryError("invalid product offset") from exc
    if set(offsets) != set(BAND_IDS):
        raise RadiometryError("missing product B04/B08 offsets")
    for band, field in BAND_IDS.items():
        if offsets[band] != float(record[field]):
            raise RadiometryError("product B04/B08 offset differs from declared value")
    return {
        "local_product_xml_sha256_verified": True,
        "local_product_xml_radiometric_values_crosschecked": True,
        "original_provider_identity_authenticated": False,
        "stac_scene_to_product_lineage_independently_verified": False,
        "original_product_metadata_source_verified": False,
        "commercial_approval": False,
    }
