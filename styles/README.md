# Layer styles and palettes

## .qml styles

Load via Layer Properties → Symbology → Style (bottom-left) → Load Style.

| Style | Use |
|---|---|
| [`parcels.qml`](parcels.qml) | Transparent fill, dark 0.46 mm outline — parcel boundaries that read over any basemap or aerial without hiding what's underneath. |
| [`flood_zones.qml`](flood_zones.qml) | Semi-transparent blue fill (`31,120,180` at ~35% opacity) with a solid blue outline — flood hazard areas over imagery or parcels. |

Both are single-symbol starting points. For a published flood map, switch `flood_zones` to a categorized renderer on your zone field using the palette below.

## Palette: FEMA-style flood zones

| Zone | Meaning | Fill (RGB, ~40% opacity) |
|---|---|---|
| VE | Coastal high-hazard (velocity) | `189, 0, 38` |
| AE | 1% annual-chance floodplain | `31, 120, 180` |
| AO / AH | Shallow flooding / ponding | `107, 174, 214` |
| X (shaded) | 0.2% annual-chance | `254, 204, 92` |
| X (unshaded) | Minimal flood hazard | `240, 240, 240` |

Keep the risk ramp sequential in *perceived* severity, not just hue: VE must be the darkest/most saturated thing on the map.

## Palette: generalized land use

| Class | Fill (RGB) |
|---|---|
| Residential | `255, 255, 179` |
| Commercial | `251, 128, 114` |
| Industrial | `190, 186, 218` |
| Conservation / open space | `141, 211, 141` |
| Agriculture | `255, 237, 160` |
| Water | `128, 205, 255` |
| Transportation / utilities | `211, 211, 211` |

These are starting points for choropleths at county scale — check contrast against your basemap and run the result past a color-vision-deficiency simulator (QGIS: View → Preview Mode) before publishing.
