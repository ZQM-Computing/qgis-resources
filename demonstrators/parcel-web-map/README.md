# Land-Parcel Web Map — Synthetic Demo (Demonstrator B)

Static, single-file interactive map (MapLibre GL JS) showing the parcel-screening
workflow: synthetic parcels with wetland / flood overlays, click popups, layer
toggles, and client-side KML/KMZ import.

## What this page proves

- Parcels and constraint overlays can be rendered on an interactive web map from
  GeoJSON, with per-parcel screening summaries on click.
- A buyer can toggle wetland / flood layers and import their own KML/KMZ boundary
  to see it against the same parcels — all in the browser, no upload, no account.
- The workflow (screen a parcel against constraint layers, report overlap +
  coverage) is the same one the companion parcel-screening demonstrator runs
  in Python/PostGIS-style logic; this page is its front-end face.

## How to open it

Double-click `index.html` (or open it in any modern browser via File → Open).
No server, no install, no login. An internet connection is needed for the CDN
libraries (MapLibre GL JS, toGeoJSON, JSZip) and the CartoDB basemap tiles; the
parcel data itself is embedded in the page.

## Honesty note — this is NOT a live PostGIS app

This is a **static front-end demonstration**. The parcels are hard-coded GeoJSON
embedded in `index.html`. There is no PostGIS database, no server, and no live
query behind the page. **The production version of this workflow would be
PostGIS-backed** — parcels and constraint layers stored in PostGIS, overlap and
coverage computed with spatial SQL, results served through an API. This page
demonstrates the user-facing workflow only; it must not be presented to a buyer
as a live PostGIS application. The same note appears in the page footer.

## Synthetic data only

Every geometry on the page is an invented fixture. No real parcel, owner,
address, or client record is represented. The page carries a visible banner:
"Synthetic demonstration data — no real property is represented."

No survey or engineering licensure is claimed, and no ArcGIS Enterprise
experience is claimed. No client names are used anywhere in this demonstrator.

## Fixture (EPSG:32617, converted to WGS84 lon/lat for MapLibre)

Source coordinates are UTM zone 17N (EPSG:32617), converted with the standard
transverse Mercator inverse formulas (WGS84 ellipsoid). Converted polygons are
~100 m squares (measured 99.85 m E–W × 100.37 m N–S) centred near 28.928°N,
81.000°W, with DEMO-P1 west of DEMO-P2.

| Parcel | UTM corners (E,N) | Area | Wetland overlap | Flood overlap |
|---|---|---|---|---|
| DEMO-P1 | (500000,3200000)–(500100,3200100) | 10,000 m² = 2.471053814671653 acres | 5,000 m² (50% of parcel), coverage 100% | 0 m² (0%), coverage 100% |
| DEMO-P2 | (500100,3200000)–(500200,3200100) | 10,000 m² = 2.471053814671653 acres | 0 m² (0%), coverage **unknown** | 2,500 m² (25% of parcel), coverage 50% |
| DEMO-P3 | (500200,3200000)–(500300,3200100) | 10,000 m² = 2.471053814671653 acres | 5,000 m² (50% of parcel), coverage 100% | 0 m² (0%), coverage **unknown** |
| DEMO-P4 | (500300,3200000)–(500400,3200100) | 10,000 m² = 2.471053814671653 acres | 2,500 m² (25% of parcel), coverage 50% | 2,500 m² (25% of parcel), coverage 100% |
| DEMO-P5 | (500000,3200100)–(500100,3200200) | 10,000 m² = 2.471053814671653 acres | 0 m² (0%), coverage **unknown** | 0 m² (0%), coverage 50% |
| DEMO-P6 | (500100,3200100)–(500200,3200200) | 10,000 m² = 2.471053814671653 acres | 10,000 m² (100% of parcel), coverage 100% | 2,500 m² (25% of parcel), coverage 100% |

- **Wetland indicator polygons** (4): western half of DEMO-P1
  (500000,3200000)–(500050,3200100); southern half of DEMO-P3
  (500200,3200000)–(500300,3200050); northern half of DEMO-P4
  (500300,3200050)–(500350,3200100); whole parcel DEMO-P6.
- **Flood hazard polygons** (3): 50 × 50 m square at the NE corner of
  DEMO-P2 (500100,3200050)–(500150,3200100); 100 × 25 m strip along the
  southern edge of DEMO-P4 (500300,3200000)–(500400,3200025); 50 × 50 m
  square at the SW corner of DEMO-P6 (500100,3200100)–(500150,3200150).

"Coverage" = share of the parcel for which the constraint layer's status is
known. A 0% coverage is encoded as `null` (unknown) in the page data, so a
0 m² overlap with unknown coverage is reported as "coverage unknown" — not
as "no wetland" / "no flood".

## KML / KMZ import — how it works

1. Choose a `.kml` or `.kmz` file with the file input.
2. **Client-side only:** a `.kml` file is parsed in the browser with
   [toGeoJSON](https://github.com/placemark/togeojson) (`toGeoJSON.kml`);
   a `.kmz` file is unzipped in the browser with
   [JSZip](https://stuk.github.io/jszip/) and its inner `.kml` parsed the same
   way. **Nothing is uploaded to any server** — stated on the page.
3. Imported features are drawn in magenta (contrasting with the blue/green/
   orange demo layers), the map zooms to them, and a status line reports the
   number of features imported. "Clear imported features" removes them.

## Files

- `index.html` — the whole demo (embedded GeoJSON + inline script).
- `parcels.geojson` — the same embedded fixture as a standalone GeoJSON file,
  so it can be diffed against the companion demonstrator's output.
- `README.md` — this file.

## Companion demonstrator

The page now embeds **all six parcels** (DEMO-P1–P6) plus the 4 wetland
and 3 flood overlay polygons, regenerated 2026-11-16 from the companion
parcel-screening GeoPackage
(`~/workspace/commercial/demonstrators/parcel-screening/parcel_screening.gpkg`)
with the same EPSG:32617 → WGS84 conversion (the conversion was checked
to reproduce the original DEMO-P1/DEMO-P2 corners exactly). The embedded
GeoJSON in `index.html` and the standalone `parcels.geojson` are byte-identical
(13 features). A 0% coverage is encoded as `null` (unknown) in the page
data, matching the page's existing "coverage unknown" rendering.

## Libraries (CDN, all verified 200 on 2026-11-16)

- MapLibre GL JS 4.7.1 — `https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js`
  (+ `.css`)
- toGeoJSON 5.8.1 (UMD) — `https://unpkg.com/@tmcw/togeojson@5.8.1/dist/togeojson.umd.js`
- JSZip 3.10.1 — `https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js`
- Basemap — CartoDB Voyager raster tiles, no API key:
  `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png`

## Verification (2026-11-16)

1. Inline JS extracted and `node --check` — **PASS** (10,194 bytes, then
   14,055 bytes after the six-parcel regeneration and the data-driven
   overlay popups).
2. Embedded GeoJSON parsed with node — **PASS**: originally 4 features;
   after regeneration **13 features** (6 parcels, 4 wetland, 3 flood),
   byte-identical to `parcels.geojson`. DEMO-P1 lon −81.000000 to
   −80.998974, lat 28.927922–28.928824; DEMO-P2 lon −80.998974 to
   −80.997948, same lat range; P1 west edge &lt; P2 west edge, shared
   boundary at −80.998974; wetland = west half of P1 (max lon −80.999487);
   flood min lat 28.928373 (mid-height of P2). Fixture properties verified:
   P1 wetland 5,000 m² / flood 0 m²; P2 wetland 0 m² with coverage `null`
   (unknown) / flood 2,500 m², coverage 50%; P3–P6 properties match the
   GeoPackage exactly (P3 wet 5,000/flood 0; P4 wet 2,500/flood 2,500;
   P5 wet 0/flood 0; P6 wet 10,000/flood 2,500). The regeneration's UTM →
   WGS84 conversion was asserted to reproduce the original DEMO-P1/DEMO-P2
   corners exactly before the page was updated, and the overlay click
   popups were generalised from hardcoded DEMO-P1/DEMO-P2 text to
   data-driven text (parcel looked up by `parcel_id`), so every overlay
   reports its own parcel's numbers.
3. All CDN URLs fetched — **HTTP 200, plausible content**: MapLibre JS
   803,086 B, CSS 65,534 B, toGeoJSON UMD 13,010 B (exposes `toGeoJSON.kml`),
   JSZip 97,630 B, CartoDB tile 2,049 B PNG.
4. Headless render check — **done with Playwright + chromium_headless_shell**.
   Caveat: the sandbox browser cannot reach the internet
   (`ERR_TUNNEL_CONNECTION_FAILED` on all CDN fetches; curl from the shell
   reaches them fine), so the delivered page was rendered from a throwaway
   `/tmp` copy with the same library files downloaded locally; the delivered
   `index.html` itself was not modified. Results: map initialises, canvas
   present, no page errors; DEMO-P1 popup shows the exact fixture numbers;
   DEMO-P2 popup shows the exact fixture numbers including "coverage
   unknown" for wetland (verified 3/3); flood-overlay click shows the flood
   popup; KML import reported "Imported 1 feature(s) from test.kml";
   KMZ import reported "Imported 2 feature(s) from test.kmz" with 2 imported
   point features on the map; "Clear imported features" works; unchecking
   the wetland toggle sets its layer visibility to `none`. Basemap tiles were
   blank in the sandbox render only (same network limitation); in a normal
   browser the CartoDB tiles load (verified 200 via curl). One earlier
   P2-click attempt in the sandbox returned no popup; re-running the identical
   click 3 times produced the correct popup every time — treated as a
   sandbox timing flake, not a page defect.
5. Six-parcel re-verification (after regeneration) — **PASS**: `node --check`
   exit 0; embedded GeoJSON parses (13 features, identical to
   `parcels.geojson`); in-page `queryRenderedFeatures` finds the correct
   features at P1/P2/P3/P4/P6 test points; rendered popups verified exact
   for DEMO-P1 (parcel + wetland overlay), DEMO-P2 (parcel, "coverage
   unknown"), DEMO-P4 (parcel + flood overlay), DEMO-P5 (parcel),
   DEMO-P6 (flood + wetland overlays). Two caveats, both sandbox-only:
   (a) the headless shell sometimes needs a few extra seconds before
   GeoJSON layers answer `queryRenderedFeatures` — an early query can
   return empty while a later identical query succeeds (diagnosed:
   element at the point is the map canvas, and a synthetic click on the
   canvas then produced the correct popup); in a normal browser the
   layers render on load. (b) Clicking exactly on a polygon corner
   (e.g. DEMO-P2's centre, which is the SE corner of its flood square)
   is hit-test ambiguous and can return no popup — expected MapLibre
   behaviour, not a page defect; interior clicks work.
