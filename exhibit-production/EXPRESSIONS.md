# Parcel atlas expression catalog

The runnable catalog is [expressions.json](expressions.json). Use raw
expressions in the Atlas panel, field calculator and data-defined properties.
For a text label, wrap an expression in `[% ... %]`. Do not put these label
delimiters inside the Atlas output-filename expression.

## Atlas and layout settings

| Setting | Raw expression / value |
| --- | --- |
| Coverage | `atlas_parcels`, displayed as **Parcel outlines** |
| Page name | Raw expression below |
| Sort, ascending | `"parcel_id"` |
| Default filter | Disabled; every parcel is included |
| Optional findings filter | `"has_indicator" = 1 OR "has_data_gap" = 1` |
| Main map item ID | `main_map` |
| Inset map item ID | `inset_map` |
| Fixed export date | Layout variable `exhibit_date`, set from `--date` |

```qgis
'Parcel ' || "parcel_id"
```

Each `parcel_id` is a nonempty unique string in the geometry layer. The
input screening matrix is long: two rows per parcel. It is pivoted before
Atlas, avoiding duplicate PDF pages from using that matrix as coverage.

## Copyable label text

| Element | Label text |
| --- | --- |
| Heading | `Environmental Constraints` |
| Parcel subtitle | `Parcel [% "parcel_id" %] \| SYNTHETIC DESKTOP SCREENING` |
| Date | `Date: [% @exhibit_date %]` |
| Feature/page counter | `Page [% @atlas_featurenumber %] / [% @atlas_totalfeatures %]` |
| Scale | `Scale 1:[% format_number(map_get(item_variables('main_map'), 'map_scale'), 0) %]` |
| CRS | `CRS: [% @project_crs %]` |

The vertical bar in the subtitle is shown escaped for the Markdown table;
paste a literal `|` in QGIS. The counter equals PDF page number only with
this **one physical page per atlas feature** layout. The scale expression
requires the exact item ID `main_map`, rather than a translated/default name
such as `Map 1`. The scale bar also links to `main_map`.

## Constraint summaries and uncertainty

Per-parcel derived fields:

| Field pattern | Meaning |
| --- | --- |
| `wetland_status`, `flood_status` | Exact upstream four-state result |
| `wetland_known_pct`, `flood_known_pct` | Known positive-area overlap as percent of whole parcel |
| `wetland_coverage_pct`, `flood_coverage_pct` | Percent of parcel covered by the source |
| `has_indicator` | Integer 1 when either known overlap is positive |
| `has_data_gap` | Integer 1 when either source leaves unknown parcel area |

Wetland status label, as raw expression:

```qgis
'Wetland indicator: ' ||
CASE
  WHEN "wetland_status" = 'intersects'
    THEN 'mapped overlap'
  WHEN "wetland_status" = 'no_mapped_intersection'
    THEN 'no mapped intersection (covered area)'
  WHEN "wetland_status" = 'partial_source_coverage'
    THEN 'PARTIAL COVERAGE - remainder unknown'
  ELSE 'NO SOURCE COVERAGE - unknown'
END ||
' | known overlap ' || format_number("wetland_known_pct", 1) || '%' ||
' | coverage ' || format_number("wetland_coverage_pct", 1) || '%'
```

The flood expression uses the corresponding `flood_*` fields. The producer
must pass validation first: the fallback label does not make malformed or
missing status values acceptable. No source coverage, partial coverage and
full-coverage negative findings are deliberately distinct.

Do not use `coalesce("has_wetland_indicator", false)` to collapse null results.
For other upstream nullable booleans, display an explicit `IS NULL` branch
as **unknown**. A source-gap flag remains independent of a positive indicator.

## Output filename

Raw Atlas output-filename expression:

```qgis
'EnvConstraints_' ||
lpad(to_string(@atlas_featurenumber), 4, '0') || '_' ||
regexp_replace("parcel_id", '[^A-Za-z0-9_-]', '_') || '_' ||
replace(@exhibit_date, '-', '')
```

Example basename: `EnvConstraints_0001_DEMO-P1_20261114`.
The ordinal avoids collisions after sanitizing parcel IDs, such as `A/B`
and `A_B`. QGIS adds the file extension for individual exports; the expression
returns a basename, without `.pdf` and without label delimiters.

For one multi-page PDF the GUI asks for a single filename and ignores the
per-feature filename expression. The implemented batch exporter always uses
`EnvConstraints_Atlas.pdf`; its page manifest reflects that single file.

## Source and date labels

The renderer reads the validated source-register snapshot and adds each
dataset ID, retrieval date and effective date (or **unknown**). The complete
source URL, boundary basis and uncertainty values remain in the accompanying
JSON register, which is also embedded verbatim as a CSV manifest field.
The supplied synthetic record does not identify a publisher.

Use a fixed generation-date variable rather than `now()` for reproducible
page labels. It is distinct from a source retrieval date and a dataset's
effective date; never substitute one for another.
