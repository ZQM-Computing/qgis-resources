# Synthetic GeoPandas handoff fixture

`geopandas-handoff/` is the unmodified eight-file output from
ZQM Computing's GeoPandas Rank 1 example at commit
[`f91ca285cc89f77773776327c6c9547248695de7`](https://github.com/ZQM-Computing/geopandas-cookbook/tree/f91ca285cc89f77773776327c6c9547248695de7/examples/12-environmental-screening).

Generated with Python 3.12, GeoPandas 1.2.0, Shapely 2.2.0, pyogrio 0.13.0
and pyproj 3.8.0. All geometries, parcel IDs and source records are synthetic;
the `example.org` URLs do not assert a real publisher or real retrieval.
The demo records retrieval time 2026-11-02T12:00:00Z; it is fixture metadata,
not an assertion that live data was downloaded on that date.

To regenerate from a checkout at that exact upstream revision:

```bash
python3 /path/to/geopandas-cookbook/examples/12-environmental-screening/demo_bundle.py \
  /tmp/rank1-source-bundle
python3 /path/to/geopandas-cookbook/examples/12-environmental-screening/exhibit_prep.py \
  /tmp/rank1-source-bundle /tmp/rank1-source-handoff
```

Choose new directories; both commands refuse existing destinations.
Regeneration may change GeoPackage/PNG bytes across dependency versions;
the producer regenerates their inventory checksums. Never edit the committed
data while retaining old checksums. Core QGIS tests read this fixture without
changing it and verify its checksums and spatial/tabular consistency.

Expected cases are two 100 × 100 metre parcels in EPSG:32617: DEMO-P1 has
50% known wetland overlap and fully covered flood data with no mapped
intersection. DEMO-P2 has no wetland source coverage, 50% flood source
coverage and 25% known flood overlap. Unknown area is never treated as clear.

This fixture is desktop-only demonstration data, not a field delineation,
jurisdictional determination, Phase I ESA, survey, professional certification,
engineering opinion, permit approval or completed client project.
