# Processing workflows

## Script: clip and reproject

[`clip_and_reproject.py`](clip_and_reproject.py) — a Processing toolbox script that reprojects an input layer and a boundary layer into a shared target CRS, clips, and writes the result. Install it via Processing Toolbox → Scripts → Add Script from File.

Why reproject *before* clipping: overlay results inherit the geometry of the run, and any follow-on area or distance step assumes the analysis CRS. Doing the CRS move first makes the whole chain consistent and makes the intermediate state easy to inspect when something looks wrong.

## Recipe: zonal summary with the Graphical Modeler

**Problem:** summarize point or polygon data per zone (counts and sums per watershed, district, or service area) — the desktop-GIS twin of a PostGIS spatial join + `GROUP BY`.

Build this chain in Processing → Graphical Modeler:

1. **Inputs:** `Zones` (polygon layer), `Data` (layer to summarize), `Value field` (numeric field on `Data`, optional).
2. **Join attributes by location (summary)** (`native:joinbylocationsummary`)
   - Input: `Zones`; Join layer: `Data`; Geometric predicate: *intersect* (add *contains* only if your zone semantics require it).
   - Summaries: check **count**, and **sum** on the value field if you added one.
   - The output carries `<field>_count` and `<field>_sum` columns.
3. **(Optional) Field calculator cleanup** — rename the summary columns to something report-friendly (`site_count`, `total_value`) with two `native:fieldcalculator` steps, or leave the machine names and document them in your metadata.
4. **Output:** save as a GeoPackage layer, not a shapefile — the summary column names are longer than the shapefile's 10-character field limit and will be silently truncated otherwise.

**Checks before you trust it:**

- Predicate choice changes answers: a point exactly on a zone boundary counts in *both* zones under *intersect*. If your zones must be exclusive, assign by centroid instead: run **Centroids** on `Data` first and join with *within*.
- Count what you expect on one known zone by hand before running the whole layer.
- If `Data` and `Zones` have different CRSs, QGIS will warn — stop and reproject (the script above does this) rather than letting the modeler run mixed.

This is the same pattern as the PostGIS spatial-join examples in the companion repo, [postgis-patterns](https://github.com/ZQM-Computing/postgis-patterns) — desktop for exploration and one-offs, database for repeatability at scale.
