# Parcel layout items and XML structure

Generate the actual `.qpt` and `.qgz` with
[parcel_atlas.py](parcel_atlas.py); it uses QGIS serialization. A `.qpt`
contains a layout, not a complete project or embedded data. Keep the generated
project, template and `atlas_data.gpkg` together.

## Item register

Coordinates are millimetres from the top-left of a landscape Letter page.
These are the starting layout's placements, not a promise that arbitrarily
long client names or new themes fit without design review.

| Item ID | Type | X, Y | Width × height | Link / content |
| --- | --- | --- | --- | --- |
| `title` | Label | 10, 8 | 193 × 10 | Environmental Constraints |
| `date` | Label | 215, 9 | 54.4 × 13 | Fixed date and atlas counter |
| `subtitle` | Label | 10, 22 | 259.4 × 7 | Current parcel and synthetic notice |
| `main_map` | Map | 10, 39 | 170 × 101 | Atlas controlled, auto scale, 15% margin |
| `inset_map` | Map | 190, 39 | 79.4 × 54 | Fixed study-wide extent; overview linked to `main_map` |
| `legend` | Legend | 190, 98 | 79.4 × 39 initial | Filtered by `main_map`; QGIS sizes the content |
| `scale_bar` | Scale bar | 10, 142 | QGIS computed | Metres; linked to `main_map` |
| `scale` | Label | 93, 144 | 85 × 6 | Representative fraction from `main_map` |
| `grid_north` | Polygon | 260, 142 | Arrow geometry | Grid north; map rotation is zero |
| `wetland_summary` | Label | 10, 155 | 259.4 × 6 | Four-state result, known overlap and coverage |
| `flood_summary` | Label | 10, 162 | 259.4 × 6 | Four-state result, known overlap and coverage |
| `sources` | Label | 10, 171 | 259.4 × 15 | Dataset IDs, retrieval/effective dates |
| `disclaimer` | Label | 10, 188 | 259.4 × 18 | Fixed desktop/synthetic/non-regulatory notice |
| `footer` | Label | 10, 208 | 259.4 × 5 | Firm, CRS, units, north and basemap limitations |

## Inspect the serialized XML

After generating the package:

```bash
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET

template = Path('/tmp/rank1-atlas-review/Env_Constraints_Parcel_Atlas.qpt')
root = ET.parse(template).getroot()
print('Root:', root.tag, 'QGIS version:', root.get('version'))
for item in root.findall('.//LayoutItem'):
    print(item.get('id'), item.get('type'), item.get('position'), item.get('size'))
atlas = root.find('.//Atlas')
print('Atlas:', atlas.attrib if atlas is not None else 'not found')
PY
```

QGIS supplies item UUIDs, numeric type identifiers, nested renderer settings
and inter-item references. Treat those as serializer output. Do not copy a
handwritten XML outline into QGIS and assume it defines a valid layout.
The generator normalizes QGIS 3.40's absolute weak layer-reference attributes
to relative paths after serialization. Runtime tests import the resulting
template into its matching relocated project and check map/atlas links.

## Safe adaptation

- Preserve item IDs used by expressions, especially `main_map`.
- Reconnect inset overviews and scale bars if replacing map items.
- Preview every feature after changing page size, scale, labels or filtering.
- Rebuild the PDF and manifest together through the generator for automated
  delivery. A manual GUI export needs a newly reconciled manifest.
- For a different CRS, validate real coordinate transformations and measurement
  units before applying a layout; a layout does not repair analytical inputs.
