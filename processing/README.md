# Processing workflows

## Script: buffer features

The Processing script in this folder is [buffer_features.py](buffer_features.py). In QGIS, open the Processing Toolbox, choose Scripts → Add Script from File, and select that file.

It buffers every feature in the input layer by one fixed distance and writes the result to a new layer. Distance units are the input layer's CRS units, so use a projected CRS for distances in metres. Features without a usable geometry are skipped and counted in the run log.

## Script: clip and reproject

The Processing script is [patterns/clip_and_reproject.py](../patterns/clip_and_reproject.py). In QGIS, open the Processing Toolbox, choose Scripts → Add Script from File, and select that file.

It reprojects an input vector layer and boundary into a shared target CRS, clips the input, and writes the result. Choose a CRS appropriate to the study area and intended measurement. A shared CRS alone does not make area or distance measurements accurate.

## Recipe: zonal summary with the Graphical Modeler

**Problem:** summarize point or polygon data per zone (counts and sums per watershed, district, or service area).

Build this chain in Processing → Graphical Modeler:

1. **Inputs:** Zones (polygon layer), Data (layer to summarize), and optionally a numeric Value field on Data.
2. **Join attributes by location (summary)** (native:joinbylocationsummary): use Zones as input, Data as join layer, and intersects as the predicate. Select count, and sum for the numeric field when provided.
3. **Optional cleanup:** rename output fields to reporting-friendly names.
4. **Output:** save to a GeoPackage to preserve long field names.

### Validation and interpretation

- A point exactly on a zone boundary can intersect multiple zones. If zones must be exclusive, define and document an assignment rule rather than assuming intersects is exclusive.
- Verify one known zone's result manually before processing the full dataset.
- Reproject inputs deliberately when they have different CRSs; do not treat CRS assignment as reprojection.

This is the desktop analogue of a spatial join and aggregation in [postgis-cookbook](https://github.com/ZQM-Computing/postgis-cookbook). Use QGIS for interactive inspection and databases for repeatable, large-scale processing.

## Plugin: ZQM Geospatial Tools

The first user-facing Processing provider is packaged as a QGIS plugin in [zqm_geospatial_tools/](../zqm_geospatial_tools/). Follow its [installation and testing instructions](../zqm_geospatial_tools/README.md). Install the complete plugin directory in the QGIS profile's Python plugins directory, enable it, then find **ZQM — Batch buffer selected layers** in Processing Toolbox.

The algorithm writes one GeoPackage per selected vector layer. It preserves existing outputs by default, validates temporary outputs before replacement, and reports per-layer successes, skips, and failures. The selected layers must share one valid CRS; mixed-CRS batches are rejected. Buffer distance uses that CRS's units, and geographic CRSs produce an explicit warning because their units are angular. Runtime testing in the target QGIS version is still required before production use.
