#!/usr/bin/env python3
"""Independent verification for parcel_screening.gpkg / .geojson.

Reads the files back and checks, from the stored geometries (not the build
script's in-memory values):
  - layer names, row counts, CRS
  - parcel areas / acres
  - wetland/flood overlap and coverage figures, recomputed by intersecting
    the parcels layer with the indicator / hazard / coverage layers
  - the DEMO-P1 / DEMO-P2 fixture numbers exactly
  - source_register contents (via sqlite3)
  - GeoJSON parcel attributes identical to the GeoPackage parcels
Exits non-zero on any failure.
"""
import json
import sqlite3
import sys
from pathlib import Path

import geopandas as gpd

OUT = Path(__file__).resolve().parent
GPKG = OUT / "parcel_screening.gpkg"
GEOJSON = OUT / "parcel_screening.geojson"
# Independent fixture truth: check wetland source coverage for EVERY parcel,
# not just the two reference examples; GeoJSON and GPKG may both be corrupted.
WETLAND_COVERAGE = {
    "DEMO-P1": 100.0, "DEMO-P2": 0.0, "DEMO-P3": 100.0,
    "DEMO-P4": 50.0, "DEMO-P5": 0.0, "DEMO-P6": 100.0,
}

failures = []


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def main():
    layers = gpd.list_layers(GPKG)
    print("Layers in parcel_screening.gpkg:")
    print(layers.to_string(index=False))
    names = list(layers["name"])
    check(names == ["parcels", "wetland_indicator", "flood_hazard", "flood_coverage", "source_register"],
          f"layer names/order == parcels, wetland_indicator, flood_hazard, flood_coverage, source_register (got {names})")

    parcels = gpd.read_file(GPKG, layer="parcels")
    wetland = gpd.read_file(GPKG, layer="wetland_indicator")
    flood_h = gpd.read_file(GPKG, layer="flood_hazard")
    flood_c = gpd.read_file(GPKG, layer="flood_coverage")
    for gdf, name, want in [(parcels, "parcels", 6), (wetland, "wetland_indicator", 4),
                            (flood_h, "flood_hazard", 3), (flood_c, "flood_coverage", 5)]:
        check(len(gdf) == want, f"{name}: {len(gdf)} rows (expected {want})")
        check(str(gdf.crs) == "EPSG:32617", f"{name}: CRS {gdf.crs} (expected EPSG:32617)")

    # Recompute every figure from the geometries as read back.
    print("\nRecomputed from stored geometries vs stored attributes:")
    for _, row in parcels.sort_values("parcel_id").iterrows():
        geom = row.geometry
        w_over = sum(geom.intersection(g).area for g in wetland.geometry)
        f_over = sum(geom.intersection(g).area for g in flood_h.geometry)
        f_cov = sum(geom.intersection(g).area for g in flood_c.geometry)
        area = geom.area
        ok = (abs(row.parcel_m2 - area) < 0.01
              and abs(row.parcel_acres - area * 0.0002471053814671653) < 1e-9
              and abs(row.wetland_overlap_m2 - w_over) < 0.01
              and abs(row.wetland_overlap_pct - w_over / area * 100) < 0.01
              and row.parcel_id in WETLAND_COVERAGE
              and abs(row.wetland_coverage_pct - WETLAND_COVERAGE[row.parcel_id]) < 0.01
              and abs(row.flood_overlap_m2 - f_over) < 0.01
              and abs(row.flood_overlap_pct - f_over / area * 100) < 0.01
              and abs(row.flood_coverage_pct - f_cov / area * 100) < 0.01)
        print(f"  {row.parcel_id}: area={area:.0f} wet={w_over:.0f} ({w_over/area*100:.0f}%) "
              f"flood={f_over:.0f} ({f_over/area*100:.0f}%) flood_cov={f_cov:.0f} ({f_cov/area*100:.0f}%) "
              f"stored wet_cov={row.wetland_coverage_pct:.0f}% -> {'OK' if ok else 'MISMATCH'}")
        check(ok, f"{row.parcel_id}: stored attributes match recomputed geometry")

    # Fixture exactness: DEMO-P1 / DEMO-P2.
    p1 = parcels.set_index("parcel_id").loc["DEMO-P1"]
    p2 = parcels.set_index("parcel_id").loc["DEMO-P2"]
    check(p1.parcel_m2 == 10000.0 and abs(p1.parcel_acres - 2.471053814671653) < 1e-12,
          f"DEMO-P1: 10,000 m2 / 2.471053814671653 ac (got {p1.parcel_m2} m2 / {p1.parcel_acres!r})")
    check(p1.wetland_overlap_m2 == 5000.0 and p1.wetland_overlap_pct == 50.0 and p1.wetland_coverage_pct == 100.0,
          f"DEMO-P1 wetland: 5,000 m2 / 50% overlap / 100% coverage (got {p1.wetland_overlap_m2} / {p1.wetland_overlap_pct}% / {p1.wetland_coverage_pct}%)")
    check(p1.flood_overlap_m2 == 0.0 and p1.flood_overlap_pct == 0.0 and p1.flood_coverage_pct == 100.0,
          f"DEMO-P1 flood: 0 m2 / 0% overlap / 100% coverage (got {p1.flood_overlap_m2} / {p1.flood_overlap_pct}% / {p1.flood_coverage_pct}%)")
    check(p2.parcel_m2 == 10000.0 and abs(p2.parcel_acres - 2.471053814671653) < 1e-12,
          f"DEMO-P2: 10,000 m2 / 2.471053814671653 ac (got {p2.parcel_m2} m2 / {p2.parcel_acres!r})")
    check(p2.wetland_overlap_m2 == 0.0 and p2.wetland_overlap_pct == 0.0 and p2.wetland_coverage_pct == 0.0,
          f"DEMO-P2 wetland: 0 m2 / 0% overlap / 0% coverage, 10,000 m2 unknown (got {p2.wetland_overlap_m2} / {p2.wetland_overlap_pct}% / {p2.wetland_coverage_pct}%)")
    check(p2.flood_overlap_m2 == 2500.0 and p2.flood_overlap_pct == 25.0 and p2.flood_coverage_pct == 50.0,
          f"DEMO-P2 flood: 2,500 m2 / 25% known overlap / 50% coverage, 5,000 m2 unknown (got {p2.flood_overlap_m2} / {p2.flood_overlap_pct}% / {p2.flood_coverage_pct}%)")
    # Exact fixture geometry.
    check(p1.geometry.bounds == (500000.0, 3200000.0, 500100.0, 3200100.0),
          f"DEMO-P1 bounds {p1.geometry.bounds} (expected (500000, 3200000, 500100, 3200100))")
    check(p2.geometry.bounds == (500100.0, 3200000.0, 500200.0, 3200100.0),
          f"DEMO-P2 bounds {p2.geometry.bounds} (expected (500100, 3200000, 500200, 3200100))")
    check(all("SYNTHETIC" in str(v) for v in parcels["data_class"]),
          "all parcel rows labelled SYNTHETIC in data_class")

    # source_register via sqlite3.
    con = sqlite3.connect(GPKG)
    cols = [r[1] for r in con.execute("PRAGMA table_info(source_register)")]
    print("\nsource_register columns:", cols)
    check(cols == ["layer", "dataset_id", "constraint_type", "source_url", "accessed_utc",
                   "effective_date", "horizontal_accuracy_m", "native_resolution_m",
                   "boundary_basis", "license_note"], "source_register has the specified columns")
    reg = con.execute("SELECT * FROM source_register ORDER BY layer").fetchall()
    print(f"source_register: {len(reg)} rows")
    for r in reg:
        print("  ", r)
    check(len(reg) == 4, "source_register: 4 rows")
    check(all(r[4] == "2026-11-02T12:00:00Z" for r in reg), "source_register: accessed_utc 2026-11-02T12:00:00Z on all rows")
    check(all(r[3].startswith("https://example.org/synthetic/") for r in reg),
          "source_register: all source_url values under https://example.org/synthetic/")
    check(all(r[5] is None and r[6] is None and r[7] is None for r in reg),
          "source_register: effective_date / horizontal_accuracy_m / native_resolution_m all NULL (unknown)")
    check(all(r[8] == "synthetic fixture; not a surveyed boundary" for r in reg),
          "source_register: boundary_basis 'synthetic fixture; not a surveyed boundary' on all rows")
    check(all(r[9] == "synthetic example data; no real property is represented" for r in reg),
          "source_register: license_note 'synthetic example data; no real property is represented' on all rows")
    check(con.execute("SELECT count(*) FROM gpkg_contents WHERE table_name='source_register' AND data_type='attributes'").fetchone()[0] == 1,
          "source_register registered in gpkg_contents as an attributes table")
    con.close()

    # GeoJSON: identical parcel attributes.
    gj = gpd.read_file(GEOJSON)
    check(len(gj) == 6 and str(gj.crs) == "EPSG:32617", f"GeoJSON: 6 parcels, CRS {gj.crs}")
    attr = ["parcel_id", "parcel_m2", "parcel_acres", "wetland_overlap_m2", "wetland_overlap_pct",
            "wetland_coverage_pct", "flood_overlap_m2", "flood_overlap_pct", "flood_coverage_pct",
            "notes", "data_class"]
    merged = parcels.sort_values("parcel_id")[attr].reset_index(drop=True).compare(
        gj.sort_values("parcel_id")[attr].reset_index(drop=True))
    check(merged.empty, "GeoJSON parcel attributes identical to GeoPackage parcels")
    check(gj.sort_values("parcel_id")["parcel_id"].tolist() ==
          ["DEMO-P1", "DEMO-P2", "DEMO-P3", "DEMO-P4", "DEMO-P5", "DEMO-P6"],
          "GeoJSON parcel_ids DEMO-P1..P6")

    print()
    if failures:
        print(f"VERIFICATION FAILED: {len(failures)} check(s)")
        sys.exit(1)
    print("VERIFICATION PASSED: all checks green.")


if __name__ == "__main__":
    main()
