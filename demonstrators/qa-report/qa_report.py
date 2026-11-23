#!/usr/bin/env python3
"""
qa_report.py — Python data QA report + source timestamp validation.

SYNTHETIC DATA ONLY. No client records, no real parcels.
No real property is represented. No survey/engineering licensure
or ArcGIS Enterprise experience is claimed.

Standard library only (sqlite3, struct, math, hashlib, json, sys,
platform). No geopandas / fiona / shapely / ogr2ogr required.

Reads, in order of preference:
  1. ../parcel-screening/parcel_screening.gpkg, relative to this script
     (the GeoPackage built in parallel — validated when present)
  2. fixtures/parcel_screening.json (bundled fixture, used when the
     GeoPackage does not exist yet; a present but invalid GeoPackage
     is a FAIL even if the report falls back to the fixture)

The source register is read from the GeoPackage's source_register
table when the GeoPackage is used, and from the fixture JSON
otherwise; the report states which input was used. Flood overlap is
recomputed against the flood_hazard layer ONLY — the flood_coverage
layer is the known-coverage extent, not hazard, and is used to
recompute coverage, never added to the overlap. Main-dataset parcels
are identified by parcel_id and carry no name attribute; the
missing-name check applies to incoming named records, not to them.

Runs REAL checks computed by this script (never hardcoded outcomes):
  * geometry validity — ring closure, non-zero area, self-intersection
    spot-check via segment intersection
  * CRS consistency — every layer EPSG:32617
  * null / duplicate attribute checks on parcel_id
  * overlap accounting — each parcel's wetland / flood overlap is
    recomputed from the actual geometries (Sutherland-Hodgman polygon
    clipping; all fixture polygons are convex rectangles, so the clip
    is exact) and compared against the stored attributes (tolerance 1 m2)
  * source timestamp freshness vs the register (accessed date present,
    effective_date null flagged as "unknown — freshness cannot be
    verified")
  * a planted-defect incoming batch of 8 records (2 clean, 6 defective),
    accepted / rejected by computing the checks above

Writes qa_report.md and qa_report.html next to this script.
Exits 0 if the generated report contains PASS/FLAG findings only.
Exits 1 if a structural or data-integrity check fails, even when the
report files are successfully generated.
"""

import hashlib
import json
import math
import platform
import sqlite3
import struct
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GPKG_PATH = BASE_DIR.parent / "parcel-screening" / "parcel_screening.gpkg"
FIXTURE_PATH = BASE_DIR / "fixtures" / "parcel_screening.json"

TOLERANCE_M2 = 1.0
EXPECTED_EPSG = 32617
ACRES_PER_M2 = 0.0002471053814671653  # 1 m2 in acres (exact fixture value)

# Study boundary (metres, EPSG:32617) — the union extent of DEMO-P1..P6.
BOUNDARY = {"xmin": 500000, "ymin": 3200000, "xmax": 500400, "ymax": 3200200}

# Expected overlap values, embedded as a fallback if the fixture JSON
# is ever unavailable. The script still RECOMPUTES the overlaps from
# the geometries and compares; these are the comparison targets only.
EXPECTED = {
    "DEMO-P1": {"wetland_m2": 5000, "flood_m2": 0,
                "wetland_coverage_pct": 100, "flood_coverage_pct": 100},
    "DEMO-P2": {"wetland_m2": None, "flood_m2": 2500,
                "wetland_coverage_pct": 0, "flood_coverage_pct": 50},
}

REASON_LABELS = {
    "DUPLICATE_IDENTIFIER": "duplicate identifier",
    "MISSING_NAME": "missing name",
    "UNUSABLE_GEOMETRY": "unusable geometry",
    "WRONG_GEOMETRY_TYPE": "wrong geometry type",
    "OUTSIDE_BOUNDARY": "record outside the boundary",
}


# ---------------------------------------------------------------- geometry
def ring_area(ring):
    """Absolute planar area of a ring (shoelace), m2. Ring is a list of [x, y]."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def polygon_area(rings):
    """Area of a polygon: outer ring minus holes."""
    if not rings:
        return 0.0
    area = ring_area(rings[0])
    for hole in rings[1:]:
        area -= ring_area(hole)
    return area


def ring_is_closed(ring):
    return len(ring) >= 2 and ring[0] == ring[-1]


def _orient(a, b, c):
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(v) < 1e-9:
        return 0
    return 1 if v > 0 else -1


def _segments_cross(p1, p2, p3, p4):
    """True only for a proper crossing (not shared endpoints / touching)."""
    d1 = _orient(p3, p4, p1)
    d2 = _orient(p3, p4, p2)
    d3 = _orient(p1, p2, p3)
    d4 = _orient(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def ring_self_intersects(ring):
    """Spot-check: any non-adjacent pair of segments properly crossing."""
    pts = ring[:-1] if ring_is_closed(ring) and len(ring) > 1 else list(ring)
    n = len(pts)
    if n < 4:
        return False
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # adjacent via closure
            if _segments_cross(pts[i], pts[(i + 1) % n],
                               pts[j], pts[(j + 1) % n]):
                return True
    return False


def _clip_edge(subject, ax, ay, bx, by):
    """Sutherland-Hodgman: clip polygon against one half-plane of the
    (convex) clip polygon, keeping the inside of edge a->b (CCW clip)."""
    def inside(p):
        return (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= -1e-9

    def intersect(p1, p2):
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        ex, ey = bx - ax, by - ay
        denom = dx * ey - dy * ex
        if abs(denom) < 1e-12:
            return p1
        t = ((ax - p1[0]) * ey - (ay - p1[1]) * ex) / denom
        return [p1[0] + t * dx, p1[1] + t * dy]

    out = []
    if not subject:
        return out
    prev, prev_in = subject[-1], inside(subject[-1])
    for cur in subject:
        cur_in = inside(cur)
        if cur_in:
            if not prev_in:
                out.append(intersect(prev, cur))
            out.append(cur)
        elif prev_in:
            out.append(intersect(prev, cur))
        prev, prev_in = cur, cur_in
    return out


def polygon_intersection_area(rings_a, rings_b):
    """Intersection area of two (convex) polygons, m2."""
    if not rings_a or not rings_b:
        return 0.0
    subject = [list(p) for p in rings_a[0]]
    clip = rings_b[0]
    for i in range(len(clip) - 1):
        subject = _clip_edge(subject, clip[i][0], clip[i][1],
                             clip[i + 1][0], clip[i + 1][1])
        if not subject:
            return 0.0
    return ring_area(subject + [subject[0]])


def bbox(rings):
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def inside_boundary(rings):
    """True if any part of the geometry lies inside the study boundary."""
    if not rings:
        return False
    xmin, ymin, xmax, ymax = bbox(rings)
    return not (xmax <= BOUNDARY["xmin"] or xmin >= BOUNDARY["xmax"]
                or ymax <= BOUNDARY["ymin"] or ymin >= BOUNDARY["ymax"])


# ---------------------------------------------------------------- WKB
def _parse_wkb(buf, off=0):
    """Parse a WKB blob (little/big endian).
    Returns (geom_type, geometry, end_offset). Geometry is a point [x, y],
    a list of points (LineString), a list of rings (Polygon), or a list of
    polygons (MultiPolygon, each a list of rings)."""
    endian = "<" if buf[off] == 1 else ">"
    gtype = struct.unpack_from(endian + "I", buf, off + 1)[0]
    # Mask off Z/M/ISO high bits; base type is the low part.
    base = gtype % 1000
    pos = off + 5
    if base == 1:  # Point
        x, y = struct.unpack_from(endian + "dd", buf, pos)
        return "Point", [x, y], pos + 16
    if base == 2:  # LineString
        (n,) = struct.unpack_from(endian + "I", buf, pos)
        pos += 4
        pts = []
        for _ in range(n):
            x, y = struct.unpack_from(endian + "dd", buf, pos)
            pos += 16
            pts.append([x, y])
        return "LineString", pts, pos
    if base == 3:  # Polygon
        (nrings,) = struct.unpack_from(endian + "I", buf, pos)
        pos += 4
        rings = []
        for _ in range(nrings):
            (n,) = struct.unpack_from(endian + "I", buf, pos)
            pos += 4
            ring = []
            for _ in range(n):
                x, y = struct.unpack_from(endian + "dd", buf, pos)
                pos += 16
                ring.append([x, y])
            rings.append(ring)
        return "Polygon", rings, pos
    if base == 6:  # MultiPolygon
        (npoly,) = struct.unpack_from(endian + "I", buf, pos)
        pos += 4
        polys = []
        for _ in range(npoly):
            _, rings, pos = _parse_wkb(buf, pos)
            polys.append(rings)
        return "MultiPolygon", polys, pos
    raise ValueError(f"unsupported WKB geometry type {gtype}")


def parse_gpkg_geometry(blob):
    """Parse a GeoPackage geometry blob (GP header + WKB)."""
    if blob is None:
        return None, None
    if len(blob) >= 8 and blob[0:2] == b"GP":
        flags = blob[3]
        envelope_indicator = (flags >> 1) & 0x07
        # srs_id is bytes 4-7; envelope follows (0/32/48/64 bytes).
        env_bytes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[envelope_indicator]
        wkb_off = 8 + env_bytes
        gtype, geom, _ = _parse_wkb(blob, wkb_off)
        return gtype, geom
    gtype, geom, _ = _parse_wkb(blob, 0)
    return gtype, geom


# ---------------------------------------------------------------- inputs
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_fixture_json():
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    layers = {"parcels": [], "wetland": [], "flood": []}
    for p in data["parcels"]:
        layers["parcels"].append({
            "parcel_id": p["parcel_id"], "name": p.get("name"),
            "geom_type": p["geometry_type"], "rings": p["rings"],
            "srs": data.get("crs_epsg", EXPECTED_EPSG),
            "stored": {
                "area_m2": p.get("area_m2"),
                "area_acres": p.get("area_acres"),
                "wetland_overlap_m2": p.get("wetland_overlap_m2"),
                "flood_overlap_m2": p.get("flood_overlap_m2"),
                "wetland_coverage_pct": p.get("wetland_coverage_pct"),
                "flood_coverage_pct": p.get("flood_coverage_pct"),
            },
        })
    for hz in data["hazards"]:
        layers[hz["layer"]].append({
            "parcel_id": hz["layer"], "name": hz["layer"],
            "geom_type": hz["geometry_type"], "rings": hz["rings"],
            "srs": data.get("crs_epsg", EXPECTED_EPSG), "stored": {},
        })
    return data, layers


def load_gpkg():
    """Read the GeoPackage with sqlite3 only.
    Returns (layers, srs_by_layer, register or None). The flood_coverage
    layer is kept separate from flood_hazard: coverage is the known-
    coverage extent, not hazard, and must never be summed into the
    overlap. Raises on any structural problem so the caller can fall
    back with an explicitly failed GeoPackage source-integrity check."""
    con = sqlite3.connect(f"file:{GPKG_PATH}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        geom_cols = {}
        try:
            for table, col, srs in cur.execute(
                    "SELECT table_name, column_name, srs_id "
                    "FROM gpkg_geometry_columns"):
                geom_cols[table] = (col, srs)
        except sqlite3.Error as exc:
            raise ValueError(f"gpkg_geometry_columns unreadable: {exc}")
        if not geom_cols:
            raise ValueError("no geometry columns registered in GeoPackage")
        layers = {"parcels": [], "wetland": [], "flood": [],
                  "flood_coverage": []}
        srs_by_layer = {}
        for table, (gcol, srs) in geom_cols.items():
            low = table.lower()
            if "parcel" in low:
                key = "parcels"
            elif "wetland" in low:
                key = "wetland"
            elif "coverage" in low:
                # must precede the "flood" test: flood_coverage is an
                # extent layer, not hazard
                key = "flood_coverage"
            elif "flood" in low:
                key = "flood"
            else:
                continue  # unrelated layer: CRS still recorded below
            srs_by_layer[table] = srs
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
            if gcol not in cols:
                raise ValueError(f"geometry column {gcol} missing in {table}")
            rows = cur.execute(
                f"SELECT * FROM {table}").fetchall()
            for row in rows:
                rec = dict(zip(cols, row))
                gtype, geom = parse_gpkg_geometry(rec.get(gcol))
                rings = geom if gtype in ("Polygon", "MultiPolygon") else None
                if gtype == "MultiPolygon":
                    # QA treats each part as a polygon; use the first part
                    # (fixture parcels are single polygons).
                    rings = geom[0] if geom else None
                    gtype = "Polygon"
                stored = {}
                for cand in ("wetland_overlap_m2", "wetland_overlap_sq_m",
                             "flood_overlap_m2", "flood_overlap_sq_m",
                             "wetland_coverage_pct", "flood_coverage_pct",
                             "area_m2", "area_sq_m", "area_acres"):
                    if cand in rec:
                        stored[cand] = rec[cand]
                layers[key].append({
                    "parcel_id": rec.get("parcel_id") or rec.get("id"),
                    "name": rec.get("name"),
                    "geom_type": gtype, "rings": rings,
                    "srs": srs, "stored": stored,
                })
        if not layers["parcels"]:
            raise ValueError("parcels layer missing or empty in GeoPackage")
        register = None
        tables = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "source_register" in tables:
            reg_cols = [r[1] for r in cur.execute(
                "PRAGMA table_info(source_register)")]
            register = []
            for row in cur.execute("SELECT * FROM source_register"):
                rec = dict(zip(reg_cols, row))
                register.append({
                    "source_id": rec.get("dataset_id"),
                    "accessed": rec.get("accessed_utc"),
                    "effective_date": rec.get("effective_date"),
                    "accuracy": rec.get("horizontal_accuracy_m"),
                    "resolution": rec.get("native_resolution_m"),
                })
        return layers, srs_by_layer, register
    finally:
        con.close()


# ---------------------------------------------------------------- validation
def validate_record(parcel_id, name, geom_type, rings, seen_ids,
                    require_name=True):
    """Compute the defect reason codes for one record. Empty list = pass.
    Checks, in order: duplicate identifier, missing name, wrong geometry
    type, unusable geometry (unclosed ring / zero area / self-intersection),
    outside boundary. Main-dataset parcels are identified by parcel_id
    and carry no name attribute, so callers pass require_name=False for
    them; the missing-name check applies to incoming named records."""
    reasons = []
    if parcel_id is None or str(parcel_id).strip() == "":
        reasons.append("MISSING_NAME")  # no identifier at all: counted here
        # (a missing parcel_id is a missing-identifier defect; the
        #  documented vocabulary has no separate code for it)
    elif parcel_id in seen_ids:
        reasons.append("DUPLICATE_IDENTIFIER")
    if require_name and (name is None or str(name).strip() == ""):
        if "MISSING_NAME" not in reasons:
            reasons.append("MISSING_NAME")
    if geom_type != "Polygon":
        reasons.append("WRONG_GEOMETRY_TYPE")
        return reasons  # cannot run polygon checks on a non-polygon
    if not rings or not rings[0]:
        reasons.append("UNUSABLE_GEOMETRY")
        return reasons
    ring = rings[0]
    if not ring_is_closed(ring):
        reasons.append("UNUSABLE_GEOMETRY")
    elif polygon_area(rings) <= 0:
        reasons.append("UNUSABLE_GEOMETRY")
    elif ring_self_intersects(ring):
        reasons.append("UNUSABLE_GEOMETRY")
    if rings and not inside_boundary(rings):
        reasons.append("OUTSIDE_BOUNDARY")
    return reasons


# Planted-defect incoming batch: 2 clean records that must pass, 6
# defective records. Documented reasons: duplicate identifier, missing
# name, unusable geometry, wrong geometry type, outside boundary.
# B-008 carries TWO reasons (missing name + outside boundary), so the
# 6 rejected rows produce 7 reason instances — reason totals are NOT
# a second row count.
BATCH = [
    {"parcel_id": "B-001", "name": "Batch Parcel 1", "geom_type": "Polygon",
     "rings": [[[500010, 3200010], [500030, 3200010], [500030, 3200030],
                [500010, 3200030], [500010, 3200010]]]},
    {"parcel_id": "B-002", "name": "Batch Parcel 2", "geom_type": "Polygon",
     "rings": [[[500110, 3200010], [500130, 3200010], [500130, 3200030],
                [500110, 3200030], [500110, 3200010]]]},
    {"parcel_id": "B-001", "name": "Batch Parcel 1 duplicate",
     "geom_type": "Polygon",
     "rings": [[[500040, 3200010], [500060, 3200010], [500060, 3200030],
                [500040, 3200030], [500040, 3200010]]]},
    {"parcel_id": "B-004", "name": "", "geom_type": "Polygon",
     "rings": [[[500010, 3200050], [500030, 3200050], [500030, 3200070],
                [500010, 3200070], [500010, 3200050]]]},
    {"parcel_id": "B-005", "name": "Batch Parcel 5", "geom_type": "Polygon",
     "rings": [[[500020, 3200050], [500040, 3200050], [500020, 3200050]]]},
    {"parcel_id": "B-006", "name": "Batch Parcel 6", "geom_type": "Point",
     "rings": None, "point": [500050, 3200050]},
    {"parcel_id": "B-007", "name": "Batch Parcel 7", "geom_type": "Polygon",
     "rings": [[[500300, 3200300], [500320, 3200300], [500320, 3200320],
                [500300, 3200320], [500300, 3200300]]]},
    {"parcel_id": "B-008", "name": "", "geom_type": "Polygon",
     "rings": [[[500500, 3200000], [500520, 3200000], [500520, 3200020],
                [500500, 3200020], [500500, 3200000]]]},
]


# ---------------------------------------------------------------- report
def main():
    checks = []  # (name, status, detail)  status: PASS / FLAG / FAIL

    # ---- input selection
    if GPKG_PATH.exists():
        input_path = GPKG_PATH
        input_kind = "GeoPackage"
        try:
            layers, srs_by_layer, gpkg_register = load_gpkg()
            gpkg_ok = True
            gpkg_note = f"layers read: {', '.join(sorted(srs_by_layer))}"
        except Exception as exc:  # fall back to the fixture, say so
            layers = None
            gpkg_ok = False
            gpkg_register = None
            gpkg_note = f"GeoPackage unreadable ({exc}); fell back to fixture JSON"
        fixture_data, fixture_layers = load_fixture_json()
        if not gpkg_ok:
            layers = fixture_layers
            input_path = FIXTURE_PATH
            input_kind = "fixture JSON (GeoPackage present but unreadable)"
            source_register = fixture_data["source_register"]
        elif gpkg_register:
            source_register = gpkg_register
            gpkg_note += ("; source register read from the GeoPackage "
                          "source_register table")
        else:
            source_register = fixture_data["source_register"]
        expected = {p["parcel_id"]: p for p in fixture_data["parcels"]}
    else:
        input_path = FIXTURE_PATH
        input_kind = "fixture JSON (GeoPackage not present yet)"
        fixture_data, layers = load_fixture_json()
        source_register = fixture_data["source_register"]
        expected = {p["parcel_id"]: p for p in fixture_data["parcels"]}
        gpkg_note = "parcel_screening.gpkg not found — validated the bundled fixture instead"

    # An invalid provided GeoPackage must not silently pass as fixture evidence.
    if GPKG_PATH.exists():
        checks.append(("GeoPackage source integrity",
                       "PASS" if input_kind == "GeoPackage" else "FAIL",
                       gpkg_note))
    input_hash = sha256_file(input_path)
    parcels = layers["parcels"]
    wetlands = layers["wetland"]
    floods = layers["flood"]
    flood_cov = layers.get("flood_coverage", [])

    # ---- CRS consistency
    crs_values = sorted({f["srs"] for f in parcels + wetlands + floods
                         + flood_cov
                         if f.get("srs") is not None})
    crs_ok = crs_values == [EXPECTED_EPSG]
    checks.append(("CRS consistency — all layers EPSG:32617",
                   "PASS" if crs_ok else "FAIL",
                   f"layers report EPSG {crs_values}; expected [32617]. {gpkg_note}"))

    # ---- geometry validity + attributes on the main parcels
    seen_ids = set()
    parcel_rows = []
    for f in parcels:
        pid = f["parcel_id"]
        # Main-dataset parcels carry no name attribute (identified by
        # parcel_id); the missing-name check applies to incoming named
        # records only.
        reasons = validate_record(pid, f.get("name"), f["geom_type"],
                                  f["rings"], seen_ids, require_name=False)
        if pid is not None:
            seen_ids.add(pid)
        area = polygon_area(f["rings"]) if f["rings"] else 0.0
        stored_area = (f["stored"] or {}).get("area_m2")
        area_detail = f"recomputed area {area:,.0f} m2"
        if stored_area is not None:
            area_detail += (f"; stored {stored_area:,.0f} m2; "
                            f"diff {abs(area - stored_area):,.2f} m2")
        else:
            area_detail += f"; {area * ACRES_PER_M2:.15f} acres"
        parcel_rows.append({
            "parcel_id": pid, "name": f.get("name"),
            "geom_type": f["geom_type"],
            "closed": ring_is_closed(f["rings"][0]) if f["rings"] else False,
            "area_m2": area,
            "self_intersects": (ring_self_intersects(f["rings"][0])
                                if f["rings"] else None),
            "reasons": reasons, "area_detail": area_detail,
        })
    geom_ok = all(not r["reasons"] for r in parcel_rows)
    checks.append(("Geometry validity — ring closure, non-zero area, "
                   "self-intersection spot-check",
                   "PASS" if geom_ok else "FAIL",
                   "; ".join(
                       f"{r['parcel_id']}: closed={r['closed']}, "
                       f"area={r['area_m2']:,.0f} m2, "
                       f"self-intersects={r['self_intersects']}"
                       for r in parcel_rows) or "no parcels"))
    dupes = [r["parcel_id"] for r in parcel_rows
             if "DUPLICATE_IDENTIFIER" in r["reasons"]]
    null_ids = [r["parcel_id"] for r in parcel_rows if r["parcel_id"] is None]
    # Main-dataset parcels carry no name attribute by design; the
    # missing-name check applies to the incoming batch, not to them.
    checks.append(("Attribute checks — parcel_id null / duplicate",
                   "PASS" if not dupes and not null_ids else "FAIL",
                   f"parcels={len(parcel_rows)}, duplicate parcel_id={dupes or 'none'}, "
                   f"null parcel_id={null_ids or 'none'}"))

    # ---- overlap accounting (recomputed from the actual geometries)
    overlap_rows = []
    for f in parcels:
        pid = f["parcel_id"]
        exp = expected.get(pid, EXPECTED.get(pid, {}))
        for hazard, layer in (("wetland", wetlands), ("flood", floods)):
            recomputed = sum(
                polygon_intersection_area(f["rings"], h["rings"])
                for h in layer)
            stored = (f["stored"] or {}).get(f"{hazard}_overlap_m2")
            # Fixture targets must never conceal missing live GeoPackage attributes.
            if stored is None and input_kind != "GeoPackage":
                stored = exp.get(f"{hazard}_overlap_m2")
            coverage = (f["stored"] or {}).get(f"{hazard}_coverage_pct")
            if coverage is None and input_kind != "GeoPackage":
                coverage = exp.get(f"{hazard}_coverage_pct")
            parcel_area = polygon_area(f["rings"])
            if coverage is None or coverage <= 0:
                # Without mapped coverage, an observed 0 does not prove absence.
                status = "FLAG"
                verdict = (f"unknown — {hazard} coverage is {coverage}%; "
                           f"recomputed {recomputed:,.0f} m2 is NOT a "
                           "verified overlap")
            elif stored is None:
                status = "FLAG"
                verdict = (f"unverified — GeoPackage stored {hazard} overlap "
                           f"is missing; recomputed {recomputed:,.0f} m2 "
                           "must not be compared to a fixture target")
            elif abs(recomputed - stored) <= TOLERANCE_M2:
                status = "PASS"
                verdict = (f"recomputed {recomputed:,.0f} m2 matches stored "
                           f"{stored:,.0f} m2 (diff "
                           f"{abs(recomputed - stored):,.2f} m2, tolerance "
                           f"{TOLERANCE_M2:.0f} m2)")
            else:
                status = "FAIL"
                verdict = (f"recomputed {recomputed:,.0f} m2 does NOT match "
                           f"stored {stored:,.0f} m2 "
                           f"(diff {abs(recomputed - stored):,.2f} m2)")
            if hazard == "flood" and flood_cov and status == "PASS":
                # Coverage is recomputed from the flood_coverage layer
                # (the known-coverage extent), never from the hazard.
                cov_area = sum(
                    polygon_intersection_area(f["rings"], h["rings"])
                    for h in flood_cov)
                recomputed_coverage = (cov_area / parcel_area * 100
                                       if parcel_area else 0.0)
                if (coverage is not None
                        and abs(recomputed_coverage - coverage) > 1.0):
                    status = "FAIL"
                    verdict += (f"; coverage mismatch: recomputed "
                                f"{recomputed_coverage:.0f}% from the "
                                "flood_coverage layer vs stored "
                                f"{coverage}%")
                elif coverage is not None:
                    verdict += (f"; coverage recomputed "
                                f"{recomputed_coverage:.0f}% from the "
                                "flood_coverage layer — matches stored")
            if coverage is not None and coverage < 100 and status == "PASS":
                verdict += (f"; note: {hazard} coverage is only {coverage}% "
                            "of this parcel — the verified overlap covers "
                            "the known area only")
            overlap_rows.append({
                "parcel_id": pid, "hazard": hazard,
                "recomputed_m2": recomputed, "stored_m2": stored,
                "coverage_pct": coverage,
                "overlap_pct_of_parcel": (recomputed / parcel_area * 100
                                          if parcel_area else 0.0),
                "status": status, "verdict": verdict,
            })
    overlap_status = ("FAIL" if any(r["status"] == "FAIL" for r in overlap_rows)
                      else "FLAG" if any(r["status"] == "FLAG" for r in overlap_rows)
                      else "PASS")
    checks.append(("Overlap accounting — recomputed vs stored (±1 m2)",
                   overlap_status,
                   "; ".join(
                       f"{r['parcel_id']} {r['hazard']}: "
                       f"{r['recomputed_m2']:,.0f} m2 recomputed vs "
                       f"{'unknown' if r['stored_m2'] is None else format(r['stored_m2'], ',.0f') + ' m2 stored'} "
                       f"[{r['status']}]" for r in overlap_rows)))

    # ---- source timestamp freshness
    for src in source_register:
        accessed = src.get("accessed")
        effective = src.get("effective_date")
        if not isinstance(accessed, str) or not accessed.strip():
            status, detail = ("FAIL", "accessed_utc missing or blank — source freshness unverified")
        elif effective is None:
            status, detail = (
                "FLAG",
                f"accessed {accessed}; effective_date is null — "
                "unknown — freshness cannot be verified; "
                "accuracy/resolution also null (unknown)")
        else:
            status, detail = ("PASS", f"accessed {accessed}; effective {effective}")
        checks.append((f"Source freshness — {src['source_id']}",
                       status, detail))

    # ---- planted-defect incoming batch
    batch_seen = set()
    batch_results = []
    reason_counts = {}
    for rec in BATCH:
        reasons = validate_record(rec["parcel_id"], rec["name"],
                                  rec["geom_type"], rec["rings"], batch_seen)
        if rec["parcel_id"] is not None:
            batch_seen.add(rec["parcel_id"])
        for r in reasons:
            reason_counts[r] = reason_counts.get(r, 0) + 1
        batch_results.append({**rec, "reasons": reasons,
                              "accepted": not reasons})
    batch_accepted = sum(1 for r in batch_results if r["accepted"])
    batch_rejected = len(batch_results) - batch_accepted
    checks.append(("Incoming batch — accept/reject computed from the checks",
                   "PASS" if (batch_accepted == 2 and batch_rejected == 6
                              and batch_results[0]["accepted"]
                              and batch_results[1]["accepted"]) else "FAIL",
                   f"inputs 8, accepted {batch_accepted}, rejected "
                   f"{batch_rejected}; reason instances "
                   f"{sum(reason_counts.values())} across {batch_rejected} "
                   "rejected rows (a row can carry more than one reason)"))

    # ---- reconciliation
    main_accepted = sum(1 for r in parcel_rows if not r["reasons"])
    main_rejected = len(parcel_rows) - main_accepted

    # ---- render
    py_ver = platform.python_version()
    report_md = build_markdown(
        input_kind=input_kind, input_path=input_path, input_hash=input_hash,
        checks=checks, parcel_rows=parcel_rows, overlap_rows=overlap_rows,
        source_register=source_register, batch_results=batch_results,
        reason_counts=reason_counts, batch_accepted=batch_accepted,
        batch_rejected=batch_rejected, main_accepted=main_accepted,
        main_rejected=main_rejected, n_parcels=len(parcel_rows),
        py_ver=py_ver, gpkg_note=gpkg_note)
    (BASE_DIR / "qa_report.md").write_text(report_md, encoding="utf-8")
    (BASE_DIR / "qa_report.html").write_text(
        build_html(report_md, checks, parcel_rows, overlap_rows,
                   batch_results, reason_counts),
        encoding="utf-8")

    print(f"Input used: {input_kind}: {input_path}")
    print(f"Input SHA-256: {input_hash}")
    print(f"CRS: EPSG:{EXPECTED_EPSG} on all layers "
          f"(reported: {crs_values})")
    print("Per-check results:")
    for name, status, detail in checks:
        print(f"  [{status}] {name} — {detail}")
    print("Main dataset reconciliation: "
          f"inputs={len(parcel_rows)} accepted={main_accepted} "
          f"rejected={main_rejected}")
    print("Incoming batch reconciliation: "
          f"inputs={len(batch_results)} accepted={batch_accepted} "
          f"rejected={batch_rejected}")
    print(f"Reject reasons (instances, not rows): {reason_counts} "
          f"total={sum(reason_counts.values())}")
    print("Overlap (recomputed from geometry):")
    for r in overlap_rows:
        print(f"  {r['parcel_id']} {r['hazard']}: "
              f"{r['recomputed_m2']:,.0f} m2 "
              f"({r['overlap_pct_of_parcel']:.0f}% of parcel), "
              f"coverage {r['coverage_pct']}%, stored "
              f"{'unknown' if r['stored_m2'] is None else format(r['stored_m2'], ',.0f') + ' m2'} "
              f"[{r['status']}]")
    print(f"Wrote {BASE_DIR / 'qa_report.md'}")
    print(f"Wrote {BASE_DIR / 'qa_report.html'}")
    return 1 if any(status == "FAIL" for _, status, _ in checks) else 0


def build_markdown(**kw):
    lines = []
    lines.append("# QA Report — Synthetic Parcel Screening Data")
    lines.append("")
    lines.append("**SYNTHETIC DATA ONLY — no real property is represented.** "
                 "No client records were used. No survey/engineering "
                 "licensure or ArcGIS Enterprise experience is claimed.")
    lines.append("")
    lines.append("## Input")
    lines.append("")
    lines.append(f"- Input used: {kw['input_kind']}")
    lines.append(f"- Input file: `{kw['input_path']}`")
    lines.append(f"- Input SHA-256: `{kw['input_hash']}`")
    lines.append(f"- Note: {kw['gpkg_note']}")
    lines.append(f"- CRS: EPSG:32617 (WGS 84 / UTM zone 17N) on all layers")
    lines.append(f"- Software: Python {kw['py_ver']} (standard library only: "
                 f"sqlite3 {sqlite3.sqlite_version}, struct, math, hashlib); "
                 "no geopandas / fiona / shapely / ogr2ogr")
    lines.append("")
    lines.append("## Per-check results")
    lines.append("")
    lines.append("| Check | Result | Detail |")
    lines.append("| --- | --- | --- |")
    for name, status, detail in kw["checks"]:
        lines.append(f"| {name} | {status} | {detail} |")
    lines.append("")
    lines.append("## Parcel geometry (recomputed)")
    lines.append("")
    lines.append("| Parcel | Name | Type | Ring closed | Area (m2) | "
                 "Area (acres) | Self-intersects | Defects |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in kw["parcel_rows"]:
        lines.append(
            f"| {r['parcel_id']} | {r['name'] or '—'} | {r['geom_type']} | "
            f"{r['closed']} | {r['area_m2']:,.0f} | "
            f"{r['area_m2'] * ACRES_PER_M2:.15f} | {r['self_intersects']} | "
            f"{', '.join(r['reasons']) or 'none'} |")
    lines.append("")
    lines.append("## Overlap accounting (recomputed from the geometries)")
    lines.append("")
    lines.append("Overlap is recomputed by polygon clipping against the "
                 "hazard geometry and compared with the stored attribute "
                 "(tolerance 1 m2). Flood coverage is recomputed from the "
                 "flood_coverage layer when present (the known-coverage "
                 "extent, never hazard). Coverage is the share of the parcel "
                 "the source is known to cover; where coverage is below "
                 "100% the overlap is verified for the known area only, "
                 "and where coverage is 0% the overlap is unknown, not zero.")
    lines.append("")
    lines.append("| Parcel | Hazard | Recomputed overlap (m2) | "
                 "Overlap (% of parcel) | Stored overlap (m2) | "
                 "Coverage (%) | Result | Verdict |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in kw["overlap_rows"]:
        stored = ("unknown" if r["stored_m2"] is None
                  else f"{r['stored_m2']:,.0f}")
        lines.append(
            f"| {r['parcel_id']} | {r['hazard']} | "
            f"{r['recomputed_m2']:,.0f} | "
            f"{r['overlap_pct_of_parcel']:.0f} | {stored} | "
            f"{r['coverage_pct']} | {r['status']} | {r['verdict']} |")
    lines.append("")
    lines.append("## Source register — timestamp validation")
    lines.append("")
    lines.append("| Source | Accessed | Effective date | Accuracy | "
                 "Resolution | Finding |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for s in kw["source_register"]:
        lines.append(
            f"| {s['source_id']} | {s.get('accessed')} | "
            f"{s.get('effective_date') or 'null (unknown)'} | "
            f"{s.get('accuracy') or 'null (unknown)'} | "
            f"{s.get('resolution') or 'null (unknown)'} | "
            "effective_date null — unknown — freshness cannot be verified |")
    lines.append("")
    lines.append("## Reconciliation")
    lines.append("")
    lines.append("Counts account for every input row. A row can have more "
                 "than one reject reason, so reason totals are not a second "
                 "row count.")
    lines.append("")
    lines.append("| Batch | Inputs | Accepted | Rejected | Check |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.append(f"| Main parcels ({kw['n_parcels']} synthetic parcels) | {kw['n_parcels']} | "
                 f"{kw['main_accepted']} | {kw['main_rejected']} | "
                 f"{'inputs = accepted + rejected ✓' if kw['n_parcels'] == kw['main_accepted'] + kw['main_rejected'] else 'MISMATCH'} |")
    lines.append(f"| Incoming test batch | {len(kw['batch_results'])} | "
                 f"{kw['batch_accepted']} | {kw['batch_rejected']} | "
                 f"{'inputs = accepted + rejected ✓' if len(kw['batch_results']) == kw['batch_accepted'] + kw['batch_rejected'] else 'MISMATCH'} |")
    lines.append("")
    lines.append("## Incoming test batch — reason-coded reject list")
    lines.append("")
    lines.append("| Record | Parcel ID | Name | Type | Reasons | Disposition |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in kw["batch_results"]:
        reasons = ", ".join(
            f"{code} ({REASON_LABELS[code]})" for code in r["reasons"]) or "—"
        lines.append(
            f"| {r['parcel_id']} | {r['parcel_id']} | "
            f"{r['name'] or '(missing)'} | {r['geom_type']} | {reasons} | "
            f"{'ACCEPT' if r['accepted'] else 'REJECT'} |")
    lines.append("")
    lines.append("### Reject reason totals (instances, not rows)")
    lines.append("")
    for code, count in sorted(kw["reason_counts"].items()):
        lines.append(f"- {code} ({REASON_LABELS[code]}): {count}")
    lines.append(f"- **Total reason instances: "
                 f"{sum(kw['reason_counts'].values())} across "
                 f"{kw['batch_rejected']} rejected rows** — a row can carry "
                 "more than one reason, so this total is not a row count.")
    return "\n".join(lines) + "\n"


def _html_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def build_html(report_md, checks, parcel_rows, overlap_rows,
               batch_results, reason_counts):
    def check_rows():
        return "".join(
            f"<tr><td>{_html_escape(n)}</td>"
            f"<td class='{s.lower()}'>{s}</td>"
            f"<td>{_html_escape(d)}</td></tr>" for n, s, d in checks)

    def overlap_table():
        rows = "".join(
            f"<tr><td>{r['parcel_id']}</td><td>{r['hazard']}</td>"
            f"<td>{r['recomputed_m2']:,.0f}</td>"
            f"<td>{r['overlap_pct_of_parcel']:.0f}%</td>"
            f"<td>{'unknown' if r['stored_m2'] is None else format(r['stored_m2'], ',.0f')}</td>"
            f"<td>{r['coverage_pct']}%</td>"
            f"<td class='{r['status'].lower()}'>{r['status']}</td>"
            f"<td>{_html_escape(r['verdict'])}</td></tr>"
            for r in overlap_rows)
        return rows

    def batch_table():
        rows = "".join(
            f"<tr><td>{r['parcel_id']}</td>"
            f"<td>{_html_escape(r['name'] or '(missing)')}</td>"
            f"<td>{r['geom_type']}</td>"
            f"<td>{', '.join(r['reasons']) or '—'}</td>"
            f"<td>{'ACCEPT' if r['accepted'] else 'REJECT'}</td></tr>"
            for r in batch_results)
        return rows

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>QA Report — Synthetic Parcel Screening Data</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;
padding:0 1rem;color:#1a1a1a}}table{{border-collapse:collapse;width:100%;
margin:1rem 0}}th,td{{border:1px solid #ccc;padding:.4rem .6rem;
text-align:left;vertical-align:top}}th{{background:#f0f0f0}}
.pass{{color:#0a6b1a;font-weight:700}}.flag{{color:#8a5a00;font-weight:700}}
.fail{{color:#a00;font-weight:700}}
.banner{{background:#fff3cd;border:1px solid #e6c200;padding:.8rem 1rem}}
</style></head><body>
<h1>QA Report — Synthetic Parcel Screening Data</h1>
<p class="banner"><strong>SYNTHETIC DATA ONLY — no real property is
represented.</strong> No client records were used. No survey/engineering
licensure or ArcGIS Enterprise experience is claimed.</p>
<h2>Per-check results</h2>
<table><tr><th>Check</th><th>Result</th><th>Detail</th></tr>
{check_rows()}</table>
<h2>Overlap accounting (recomputed from the geometries)</h2>
<table><tr><th>Parcel</th><th>Hazard</th><th>Recomputed (m2)</th>
<th>% of parcel</th><th>Stored (m2)</th><th>Coverage</th><th>Result</th>
<th>Verdict</th></tr>{overlap_table()}</table>
<h2>Incoming test batch — reason-coded reject list</h2>
<table><tr><th>Parcel ID</th><th>Name</th><th>Type</th><th>Reasons</th>
<th>Disposition</th></tr>{batch_table()}</table>
<p>Reject reason instances: {sum(reason_counts.values())} across
{sum(1 for r in batch_results if not r['accepted'])} rejected rows —
a row can carry more than one reason, so reason totals are not a second
row count.</p>
<p>Full detail, reconciliation table, source register and input hash are
in <code>qa_report.md</code> (same report, same computed results).</p>
</body></html>
"""


if __name__ == "__main__":
    sys.exit(main())
