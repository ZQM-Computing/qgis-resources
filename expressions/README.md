# QGIS expression functions

Copy-pasteable expressions for the Field Calculator, label settings, and rule-based symbology. Placeholder layer and field names are in `monospace` — replace them with yours. Unless noted, these fit QGIS 3.28 LTR and newer.

---

## 1. Real-world acreage in a projected CRS

**Problem:** `$area` depends on the project's ellipsoid settings, and measuring a longitude/latitude layer directly gives meaningless numbers. For Florida work, calculate in Florida State Plane East (EPSG:2236, US survey feet; 1 acre = 43,560 ft²). Swap EPSG:2236 for your own State Plane / UTM zone elsewhere.

```text
area(
  transform(
    $geometry,
    layer_property(@layer, 'crs'),
    'EPSG:2236'
  )
) / 43560
```

- `layer_property(@layer, 'crs')` reads the layer's own CRS, so the transform is honest even if the layer isn't in EPSG:4326.
- Wrap in `round(..., 2)` for report-ready values.
- **Sharp edge:** `transform()` needs the target CRS installed in QGIS's CRS database (all EPSG State Plane zones are). For features crossing a zone boundary, no single projected CRS is right — use a geodesic method or split the analysis.

## 2. Attributes from every intersecting feature (e.g., flood zones touching a parcel)

**Problem:** A parcel can overlap several flood zones. You want the list of zone values without building a permanent spatial join. Run this on the *parcels* layer; `flood_zones` is the other layer, `zone` is its field.

```text
aggregate(
  layer := 'flood_zones',
  aggregate := 'array_agg',
  expression := "zone",
  filter := intersects($geometry, geometry(@parent))
)
```

- Inside `aggregate()`, `$geometry` is the *other* layer's feature; `geometry(@parent)` is the current feature.
- Change `'array_agg'` to `'concatenate'` (with `concatenator := ', '`) to get a single text value like `AE, X, VE` for labels.
- **Sharp edge:** This evaluates per feature against the whole other layer. On very large layers, a one-time spatial join (**Join attributes by location**) will be faster for repeated use.

## 3. Attribute of the nearest feature

**Problem:** For each site, find the ID of the closest parcel (or pump station, or sample point). Run on the *sites* layer; `parcels` is the target layer, `parcel_id` its field.

```text
array_first(
  aggregate(
    layer := 'parcels',
    aggregate := 'array_agg',
    expression := "parcel_id",
    order_by := distance($geometry, geometry(@parent))
  )
)
```

- `order_by` sorts the aggregated values by distance from the current feature, so `array_first(...)` keeps only the nearest.
- Add `filter := distance($geometry, geometry(@parent)) < 5000` inside `aggregate(...)` to ignore candidates beyond 5,000 CRS units.
- **Sharp edge:** `distance()` here is planar, in the layer CRS units. If the layers are in EPSG:4326 those units are degrees — reproject first, or accept approximate ranking only.

## 4. Human-friendly labels: title case + formatted date

**Problem:** Raw attribute values (`JOHN SMITH`, `2024-03-05 00:00:00`) make ugly map labels.

```text
concat(
  title("owner_name"),
  ' — surveyed ',
  format_date("last_survey", 'MMM d, yyyy')
)
```

Produces labels like `John Smith — surveyed Mar 5, 2024`.

- `title()` title-cases text; `format_date()` takes Qt date-format strings.
- In label settings you can use the same expression and control line breaks with the label placement options, or build multi-line labels with `'\n'` inside `concat(...)` when your QGIS version renders it (test on your version).

## 5. Centroid coordinates in a projected CRS (for field calculator)

**Problem:** You need X/Y fields in State Plane feet for a CAD or survey handoff, not degrees.

```text
-- X field
x(
  transform(
    centroid($geometry),
    layer_property(@layer, 'crs'),
    'EPSG:2236'
  )
)

-- Y field: same shape with y(...)
```

- Create the fields as Decimal (real) with width 18, precision 3.
- **Sharp edge:** `centroid()` of a concave polygon can fall *outside* the polygon. For a guaranteed in-polygon point, use `point_on_surface($geometry)` instead of `centroid($geometry)`.

---

Have an expression you use weekly? PRs welcome — follow the format above: problem, expression, why it works, sharp edge. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
