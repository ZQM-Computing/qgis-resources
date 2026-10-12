# QField field-data-collection setup

A practical checklist for packaging a QGIS project for offline field collection with [QField](https://qfield.org) — the setup used for environmental field verification work (wetland checks, gopher tortoise burrow surveys, outfall inspections), generalized so it fits most point/line/polygon collection jobs.

## 1. Build the project for the field, not the office

- **One GeoPackage per project** for editable layers. GeoPackage survives offline editing, sync, and round-tripping far better than shapefiles (no 10-character field names, no multi-file breakage). The batch-export snippet in [`../pyqgis/`](../pyqgis/) produces one from an existing project.
- **Basemaps offline:** export a raster tile package (MBTiles) of your work area at the zooms you actually need, or use QFieldCloud's offline basemap packaging. Field areas with no signal are the norm, not the exception.
- **CRS:** keep the project in the CRS your deliverable needs (for Florida: EPSG:2236 or the data's native CRS). QField handles on-the-fly reprojection, but a single consistent project CRS removes a whole class of "why is this offset" field problems.

## 2. Configure the forms — this is where data quality is won

For each editable layer (Layer Properties → Attributes Form):

- **Drag-and-drop designer:** hide system fields, group related fields in tabs or group boxes, put the fields the collector touches on every feature first.
- **Value maps / value relations:** wherever the answer is one of N choices (species, condition class, yes/no/unknown), use a widget with a fixed list — never free text for categorical data.
- **Constraints:** set NOT NULL on required fields, add range constraints on numeric fields, and mark constraints as *hard* for anything the office will have to chase down later.
- **Defaults:** pre-fill collector name, date (`now()`), and project ID as default values (apply on update where appropriate) so the collector never types them.
- **Photos:** add a text field with the **Attachment** widget configured for photos, one photo field per expected photo type (overview, detail, marker). QField stores the files alongside the GeoPackage and syncs them with the data.

## 3. Pre-flight checklist (the morning of)

- [ ] Project opens in QField on the actual device, offline mode on.
- [ ] Editable layers show the configured forms, not raw attribute tables.
- [ ] Test feature collected, photo attached, saved, and visible after closing/reopening.
- [ ] Basemap visible offline at working zooms across the whole site.
- [ ] GNSS: device location displays; if using an external receiver, it's paired and QField shows the external position source.
- [ ] Sync path tested (QFieldCloud sync or cable copy) with yesterday's test feature — *before* the real data exists.
- [ ] Battery plan: device + power bank; QField tracking off unless the job needs a track log.

## 4. Back in the office

- Sync first, edit second. Merge field edits into the master dataset before anyone "cleans up" the field copy.
- Validate against the same constraints the form enforced: required fields populated, categorical values in-domain, photos present for the features that need them.
- Archive the as-collected GeoPackage read-only. Corrections happen in the master, never by editing the archive.

## Common failure modes

| Symptom | Usual cause |
|---|---|
| Features offset from imagery | Mixed CRS between project, layer, and basemap — see §1. |
| Photos missing after sync | Attachment widget path settings; photos stored outside the synced folder. |
| Dropdown shows codes, not labels | Value map configured on the office project but the field copy predates it — repackage. |
| "Layer is read-only" in QField | Layer source is a shapefile in a zipped project or a non-editable format — convert to GeoPackage. |
