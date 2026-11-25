#!/usr/bin/env python3
"""Build the SYNTHETIC parcel-screening demonstrator GeoPackage + GeoJSON.

SYNTHETIC DATA ONLY — no real property is represented.
No client records, no real parcels, no real property data.

Fixture (EPSG:32617, origin 500000, 3200000; every parcel 100 x 100 m):
  DEMO-P1 (500000,3200000)-(500100,3200100)
  DEMO-P2 (500100,3200000)-(500200,3200100)
  Wetland indicator: western half of DEMO-P1, 5,000 m2.
  Flood hazard: 50x50 m square in the northern half of DEMO-P2, 2,500 m2.
  Flood coverage extent: northern half of DEMO-P2, 5,000 m2.
  DEMO-P3..P6 extend the same 100 m grid; all overlap/coverage figures are
  COMPUTED from the actual geometries with shapely (intersection areas),
  never hand-written.

Wetland coverage: the wetland inventory's mapped extent is recorded per
parcel as an attribute (there is no separate wetland_coverage layer in the
required layer list). The in-memory extent polygons used to compute it are
listed in WETLAND_COVERAGE_EXTENTS below and documented in README.md.
Flood coverage IS a layer (flood_coverage), so its figures come from
intersection with that layer's polygons.

Run:  python3 build_parcel_screening.py
Writes: parcel_screening.gpkg, parcel_screening.geojson (same dir).
"""
import sqlite3
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

OUT = Path(__file__).resolve().parent
GPKG = OUT / "parcel_screening.gpkg"
GEOJSON = OUT / "parcel_screening.geojson"
CRS = "EPSG:32617"
SQM_PER_ACRE = 0.0002471053814671653  # 1 m2 in acres; 10,000 m2 = 2.471053814671653 ac
SYNTH = "SYNTHETIC - no real property is represented"

# ---------------------------------------------------------------- parcels
PARCELS = {
    "DEMO-P1": box(500000, 3200000, 500100, 3200100),
    "DEMO-P2": box(500100, 3200000, 500200, 3200100),
    "DEMO-P3": box(500200, 3200000, 500300, 3200100),
    "DEMO-P4": box(500300, 3200000, 500400, 3200100),
    "DEMO-P5": box(500000, 3200100, 500100, 3200200),
    "DEMO-P6": box(500100, 3200100, 500200, 3200200),
}

# ------------------------------------------------------- wetland indicator
# Mapped wetland areas (the inventory's indicator polygons).
WETLAND_INDICATOR = [
    ("WI-01", "DEMO-P1", box(500000, 3200000, 500050, 3200100)),   # W half of P1, 5,000 m2
    ("WI-02", "DEMO-P3", box(500200, 3200000, 500300, 3200050)),   # S half of P3, 5,000 m2
    ("WI-03", "DEMO-P4", box(500300, 3200050, 500350, 3200100)),   # NW quarter of P4, 2,500 m2
    ("WI-04", "DEMO-P6", box(500100, 3200100, 500200, 3200200)),   # full P6, 10,000 m2
]
# Wetland inventory mapped extent per parcel (used ONLY to compute
# wetland_coverage_pct; P2/P5 have no mapped extent -> 0% coverage, unknown).
WETLAND_COVERAGE_EXTENTS = {
    "DEMO-P1": [box(500000, 3200000, 500100, 3200100)],  # full parcel
    "DEMO-P2": [],
    "DEMO-P3": [box(500200, 3200000, 500300, 3200100)],  # full parcel
    "DEMO-P4": [box(500300, 3200050, 500400, 3200100)],  # N half
    "DEMO-P5": [],
    "DEMO-P6": [box(500100, 3200100, 500200, 3200200)],  # full parcel
}

# ------------------------------------------------------------ flood hazard
FLOOD_HAZARD = [
    ("FH-01", "DEMO-P2", box(500100, 3200050, 500150, 3200100)),  # 50x50 m, 2,500 m2
    ("FH-02", "DEMO-P4", box(500300, 3200000, 500400, 3200025)),  # S strip of P4, 2,500 m2
    ("FH-03", "DEMO-P6", box(500100, 3200100, 500150, 3200150)),  # SW quarter of P6, 2,500 m2
]
# Flood coverage extents (the flood_coverage layer).
FLOOD_COVERAGE = [
    ("FC-01", "DEMO-P1", box(500000, 3200000, 500100, 3200100)),  # full P1
    ("FC-02", "DEMO-P2", box(500100, 3200050, 500200, 3200100)),  # N half of P2
    ("FC-03", "DEMO-P4", box(500300, 3200000, 500400, 3200100)),  # full P4
    ("FC-04", "DEMO-P5", box(500050, 3200100, 500100, 3200200)),  # E half of P5
    ("FC-05", "DEMO-P6", box(500100, 3200100, 500200, 3200200)),  # full P6
]

NOTES = {
    "DEMO-P1": "Wetland indicator covers half the parcel; flood hazard none mapped within full flood coverage.",
    "DEMO-P2": "No wetland inventory coverage - wetland status unknown for the whole parcel; flood hazard covers a quarter of the parcel within the mapped northern half.",
    "DEMO-P3": "Wetland indicator covers the southern half; no flood coverage - flood status unknown for the whole parcel.",
    "DEMO-P4": "Wetland indicator covers a quarter within the mapped northern half; flood hazard covers a quarter (southern strip) within full flood coverage.",
    "DEMO-P5": "No wetland inventory coverage - wetland status unknown; flood hazard none mapped within the mapped eastern half.",
    "DEMO-P6": "Wetland indicator covers the whole parcel; flood hazard covers a quarter (south-west) within full flood coverage.",
}


def inter_area(parcel_geom, polys):
    """Area (m2) of parcel_geom intersected with the union of polys."""
    total = 0.0
    for p in polys:
        total += parcel_geom.intersection(p).area
    return total


def main():
    if GPKG.exists():
        GPKG.unlink()

    # --- parcels: every figure computed from geometry -------------------
    wet_polys = [g for _, _, g in WETLAND_INDICATOR]
    fh_polys = [g for _, _, g in FLOOD_HAZARD]
    fc_polys = [g for _, _, g in FLOOD_COVERAGE]
    rows = []
    for pid, geom in PARCELS.items():
        area = geom.area
        w_over = inter_area(geom, wet_polys)
        w_cov = inter_area(geom, WETLAND_COVERAGE_EXTENTS[pid])
        f_over = inter_area(geom, fh_polys)
        f_cov = inter_area(geom, fc_polys)
        rows.append({
            "parcel_id": pid,
            "parcel_m2": round(area, 2),
            "parcel_acres": area * SQM_PER_ACRE,
            "wetland_overlap_m2": round(w_over, 2),
            "wetland_overlap_pct": round(w_over / area * 100, 2),
            "wetland_coverage_pct": round(w_cov / area * 100, 2),
            "flood_overlap_m2": round(f_over, 2),
            "flood_overlap_pct": round(f_over / area * 100, 2),
            "flood_coverage_pct": round(f_cov / area * 100, 2),
            "notes": NOTES[pid],
            "data_class": SYNTH,
            "geometry": geom,
        })
    parcels = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)

    def layer_frame(specs, id_col="feature_id"):
        return gpd.GeoDataFrame(
            [{
                id_col: fid,
                "parcel_id": pid,
                "area_m2": round(g.area, 2),
                "data_class": SYNTH,
                "geometry": g,
            } for fid, pid, g in specs],
            geometry="geometry", crs=CRS)

    wetland = layer_frame(WETLAND_INDICATOR)
    flood_haz = layer_frame(FLOOD_HAZARD)
    flood_cov = layer_frame(FLOOD_COVERAGE)

    parcels.to_file(GPKG, layer="parcels", driver="GPKG")
    wetland.to_file(GPKG, layer="wetland_indicator", driver="GPKG")
    flood_haz.to_file(GPKG, layer="flood_hazard", driver="GPKG")
    flood_cov.to_file(GPKG, layer="flood_coverage", driver="GPKG")

    # --- source_register: non-spatial attribute table --------------------
    # Registered in gpkg_contents (content_type 'attributes') so QGIS and
    # other GeoPackage readers list it alongside the spatial layers.
    register = [
        ("parcels", "SYNTH-PARCELS-2026", "parcel boundary (synthetic fixture)",
         "https://example.org/synthetic/parcels"),
        ("wetland_indicator", "SYNTH-WETLAND-2026", "wetland inventory",
         "https://example.org/synthetic/wetland-inventory"),
        ("flood_hazard", "SYNTH-FLOOD-HAZARD-2026", "flood hazard",
         "https://example.org/synthetic/flood-hazard"),
        ("flood_coverage", "SYNTH-FLOOD-COVERAGE-2026", "flood hazard coverage extent",
         "https://example.org/synthetic/flood-coverage"),
    ]
    con = sqlite3.connect(GPKG)
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS source_register")
    cur.execute("""CREATE TABLE source_register (
        layer TEXT NOT NULL,
        dataset_id TEXT NOT NULL,
        constraint_type TEXT NOT NULL,
        source_url TEXT NOT NULL,
        accessed_utc TEXT NOT NULL,
        effective_date TEXT,
        horizontal_accuracy_m REAL,
        native_resolution_m REAL,
        boundary_basis TEXT NOT NULL,
        license_note TEXT NOT NULL)""")
    cur.executemany(
        "INSERT INTO source_register VALUES (?,?,?,?,?,NULL,NULL,NULL,?,?)",
        [(layer, ds, ctype, url, "2026-11-02T12:00:00Z",
          "synthetic fixture; not a surveyed boundary",
          "synthetic example data; no real property is represented")
         for layer, ds, ctype, url in register])
    cur.execute(
        "INSERT INTO gpkg_contents (table_name, data_type, identifier, description, min_x, min_y, max_x, max_y, srs_id)"
        " VALUES ('source_register','attributes','source_register','Synthetic source register (no real property is represented)',NULL,NULL,NULL,NULL,4326)")
    con.commit()
    con.close()

    # --- GeoJSON: same parcels, identical attributes, same CRS -----------
    parcels.to_file(GEOJSON, driver="GeoJSON")

    print(f"Wrote {GPKG}")
    print(f"Wrote {GEOJSON}")
    print(parcels.drop(columns="geometry").to_string(index=False))


if __name__ == "__main__":
    main()
