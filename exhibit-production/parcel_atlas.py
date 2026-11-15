#!/usr/bin/env python3
"""Render the Rank 1 synthetic GeoPandas exhibit handoff in QGIS 3.40.

Desktop/database demonstration only. Not a field delineation, jurisdictional
determination, Phase I ESA, survey, certification, engineering or permit opinion.
No live sources, geometry repair, reprojection, or source modification. Inputs
must use the producer's projected metre CRS. Export into a NEW directory only.
"""
from __future__ import annotations

import argparse
import csv
import gc
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtGui import QColor, QFont, QPolygonF
from qgis.PyQt.QtCore import QPointF
from qgis.core import (
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsExpression,
    QgsExpressionContextUtils, QgsFeature, QgsField, QgsFillSymbol, QgsGeometry,
    QgsLayoutExporter, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap,
    QgsLayoutItemMapOverview, QgsLayoutItemPolygon, QgsLayoutItemScaleBar,
    QgsLayoutPoint, QgsLayoutSize, QgsPalLayerSettings, QgsPrintLayout, QgsProject,
    QgsReadWriteContext, QgsTextBufferSettings, QgsTextFormat, QgsVectorFileWriter,
    QgsVectorLayer, QgsVectorLayerSimpleLabeling, QgsWkbTypes,
)

ROOT = Path(__file__).resolve().parent
EXPRESSIONS = json.loads((ROOT / "expressions.json").read_text(encoding="utf-8"))
TYPES = {"wetland_inventory": "wetland", "flood_hazard": "flood"}
STATUSES = {"intersects", "no_mapped_intersection", "partial_source_coverage", "no_source_coverage"}
INPUT_NAMES = {
    "parcel_constraints.csv", "parcel_screening.json", "parcel_screening.gpkg",
    "parcel_review_map.png", "manifest.json", "source_register.json", "LIMITATIONS.txt",
}
DISCLAIMER = (
    "DESKTOP SCREENING ONLY - SYNTHETIC DEMONSTRATION DATA\n"
    "Preliminary desktop environmental constraints screening using indicator data. "
    "Not a field wetland delineation, jurisdictional determination, Phase I ESA, "
    "boundary survey, engineering opinion, permit approval or professional certification. "
    "All features require field verification by qualified professionals. "
    "Source records and retrieval dates accompany this exhibit; coverage gaps remain unknown."
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_handoff_inventory(directory):
    """Reject non-flat inputs before copying or opening their contents."""
    members = list(directory.iterdir())
    if (any(p.is_symlink() or not p.is_file() for p in members)
            or {p.name for p in members} != INPUT_NAMES | {"exhibit_manifest.json"}):
        raise ValueError("Expected the complete flat GeoPandas exhibit handoff")


def read_handoff(directory):
    """Verify the producer's flat inventory, metadata and complete parcel/type grid.

    Hashes establish byte consistency, not source authority or environmental truth.
    Unknown publication/accuracy values remain unknown; no publisher is invented.
    """
    directory = Path(directory)
    check_handoff_inventory(directory)
    manifest = json.loads((directory / "exhibit_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("method") != "rank1_synthetic_exhibit_handoff_v1" or manifest.get("data") != "synthetic":
        raise ValueError("Only the synthetic Rank 1 handoff v1 is supported")
    entries = manifest.get("file_inventory", [])
    if (len(entries) != len(INPUT_NAMES)
            or {entry.get("filename") for entry in entries} != INPUT_NAMES):
        raise ValueError("Handoff manifest inventory mismatch")
    for entry in entries:
        path = directory / entry["filename"]
        if entry.get("bytes") != path.stat().st_size or entry.get("sha256") != sha256(path):
            raise ValueError(f"Handoff checksum mismatch: {path.name}")
    report = json.loads((directory / "parcel_screening.json").read_text(encoding="utf-8"))
    sources = json.loads((directory / "source_register.json").read_text(encoding="utf-8"))
    if (report.get("provenance_status") != "validated"
            or sources != report.get("source_register") or not isinstance(sources, list)
            or len(sources) != len(TYPES)
            or manifest.get("source_count") != len(sources)
            or {s.get("constraint_type") for s in sources} != set(TYPES)):
        raise ValueError("Validated source register must match both supported constraint types")
    for source in sources:
        for field in ("dataset_id", "source_url", "accessed_utc", "boundary_basis"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                raise ValueError(f"Missing source register field: {field}")
        parsed = urlparse(source["source_url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Source URL must be HTTPS")
        accessed = datetime.fromisoformat(source["accessed_utc"].replace("Z", "+00:00"))
        if accessed.tzinfo is None:
            raise ValueError("Source retrieval date requires timezone")
        for field in ("effective_date", "horizontal_accuracy_m", "native_resolution_m"):
            if field not in source:
                raise ValueError(f"Missing source uncertainty field: {field}")
        if source["effective_date"] is not None:
            date.fromisoformat(source["effective_date"])
        for field in ("horizontal_accuracy_m", "native_resolution_m"):
            value = source[field]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                raise ValueError(f"Invalid source uncertainty: {field}")
    rows = report.get("rows", [])
    keys = set()
    for row in rows:
        key = (row.get("parcel_id"), row.get("constraint_type"))
        if (not isinstance(key[0], str) or not key[0].strip()
                or key[1] not in TYPES or key in keys or row.get("status") not in STATUSES):
            raise ValueError("Invalid or duplicate parcel/type/status")
        keys.add(key)
        for field in ("parcel_m2", "covered_m2", "unknown_m2", "known_overlap_m2",
                      "known_overlap_pct_parcel", "coverage_pct_parcel"):
            value = row.get(field)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid screening number: {field}")
    ids = {key[0] for key in keys}
    if not ids or keys != {(pid, kind) for pid in ids for kind in TYPES}:
        raise ValueError("Incomplete parcel/type screening matrix")
    with (directory / "parcel_constraints.csv").open(newline="", encoding="utf-8") as stream:
        csv_rows = list(csv.DictReader(stream))
    if len(csv_rows) != len(rows):
        raise ValueError("CSV/report row count mismatch")
    expected = {(r["parcel_id"], r["constraint_type"]): r for r in rows}
    seen = set()
    for row in csv_rows:
        key = (row.get("parcel_id"), row.get("constraint_type"))
        if key in seen or key not in expected:
            raise ValueError("CSV/report parcel/type mismatch")
        seen.add(key)
        if any(row.get(field) != str(value) for field, value in expected[key].items()):
            raise ValueError("CSV/report screening value mismatch")
    return manifest, sources, expected


def load_polygon(path, name, crs, required, optional=False):
    layer = QgsVectorLayer(f"{path}|layername={name}", name, "ogr")
    if optional and not layer.isValid():
        return None
    if (not layer.isValid() or layer.crs() != crs
            or QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry
            or not set(required) <= set(layer.fields().names())):
        raise ValueError(f"{name}: invalid polygon layer, fields or CRS mismatch")
    for feature in layer.getFeatures():
        geometry = feature.geometry()
        if geometry.isNull() or geometry.isEmpty() or not geometry.isGeosValid() or geometry.area() <= 0:
            raise ValueError(f"{name}: null, empty, invalid or zero-area polygon")
    return layer


def geometry_by_key(layer, ids):
    groups = {}
    if layer is not None:
        for feature in layer.getFeatures():
            key = (feature["parcel_id"], feature["constraint_type"])
            if key[0] not in ids or key[1] not in TYPES:
                raise ValueError("Geometry references an unknown parcel/type")
            groups.setdefault(key, []).append(feature.geometry())
    return {key: QgsGeometry.unaryUnion(values) for key, values in groups.items()}


def prepare_layers(directory, manifest, rows):
    """Reconcile actual metre geometry with the matrix; derive coverage-gap polygons."""
    crs = QgsCoordinateReferenceSystem(manifest["analysis_crs"])
    if not crs.isValid() or crs.isGeographic() or crs.mapUnits() != Qgis.DistanceUnit.Meters:
        raise ValueError("Producer handoff requires a valid projected metre CRS")
    gpkg = Path(directory) / "parcel_screening.gpkg"
    parcels = load_polygon(gpkg, "parcels", crs, ("parcel_id",))
    features = list(parcels.getFeatures())
    ids = [f["parcel_id"] for f in features]
    if len(set(ids)) != len(ids) or set(ids) != {pid for pid, _ in rows}:
        raise ValueError("Duplicate parcel IDs or geometry/matrix ID mismatch")
    coverage = geometry_by_key(load_polygon(gpkg, "source_coverage", crs,
                               ("parcel_id", "constraint_type"), optional=True), ids)
    overlaps = geometry_by_key(load_polygon(gpkg, "known_overlaps", crs,
                               ("parcel_id", "constraint_type"), optional=True), ids)
    atlas = QgsVectorLayer(f"MultiPolygon?crs={crs.authid()}", "Parcel outlines", "memory")
    fields = [QgsField("parcel_id", QMetaType.Type.QString)]
    for prefix in TYPES.values():
        fields += [QgsField(prefix + "_status", QMetaType.Type.QString),
                   QgsField(prefix + "_known_pct", QMetaType.Type.Double),
                   QgsField(prefix + "_coverage_pct", QMetaType.Type.Double)]
    fields += [QgsField("has_indicator", QMetaType.Type.Int), QgsField("has_data_gap", QMetaType.Type.Int)]
    atlas.dataProvider().addAttributes(fields)
    atlas.updateFields()
    display = {"atlas_parcels": atlas}
    captions = {"wetland": "Wetland", "flood": "Flood"}
    for prefix in TYPES.values():
        for suffix, caption in (("indicators", "indicators"), ("gaps", "coverage gap")):
            display[prefix + "_" + suffix] = QgsVectorLayer(
                f"MultiPolygon?crs={crs.authid()}", captions[prefix] + " " + caption, "memory")
    for parcel in sorted(features, key=lambda f: f["parcel_id"]):
        pid, geometry = parcel["parcel_id"], parcel.geometry()
        values = [pid]
        indicator = gap = False
        for kind, prefix in TYPES.items():
            row = rows[(pid, kind)]
            cover = coverage.get((pid, kind), QgsGeometry())
            overlap = overlaps.get((pid, kind), QgsGeometry())
            area = geometry.area()
            covered = 0.0 if cover.isNull() else cover.area()
            known = 0.0 if overlap.isNull() else overlap.area()
            tol = max(1e-6, area * 1e-9)
            def close(actual, expected):
                if abs(actual - expected) > tol:
                    raise ValueError(f"{pid}/{kind}: screening/geometry area mismatch")
            close(area, row["parcel_m2"])
            close(covered, row["covered_m2"])
            close(area - covered, row["unknown_m2"])
            close(known, row["known_overlap_m2"])
            for geom, parent in ((cover, geometry), (overlap, cover)):
                if not geom.isNull() and (parent.isNull() or geom.difference(parent).area() > tol):
                    raise ValueError(f"{pid}/{kind}: geometry outside parcel/source coverage")
            for field, value in (("known_overlap_pct_parcel", 100 * known / area),
                                 ("coverage_pct_parcel", 100 * covered / area)):
                if abs(row[field] - value) > 1e-6:
                    raise ValueError(f"{pid}/{kind}: screening percentage mismatch")
            status = ("partial_source_coverage" if covered > 0 else "no_source_coverage") if area - covered > tol else (
                "intersects" if known > 0 else "no_mapped_intersection")
            if status != row["status"]:
                raise ValueError(f"{pid}/{kind}: contradictory screening status")
            values += [status, row["known_overlap_pct_parcel"], row["coverage_pct_parcel"]]
            indicator |= known > 0
            gap |= area - covered > tol
            unknown = geometry if cover.isNull() else geometry.difference(cover)
            for suffix, geom in (("indicators", overlap), ("gaps", unknown)):
                if not geom.isNull() and not geom.isEmpty() and geom.area() > 0:
                    result = QgsFeature()
                    result.setGeometry(geom)
                    if not display[prefix + "_" + suffix].dataProvider().addFeatures([result])[0]:
                        raise ValueError("Could not add display geometry")
        result = QgsFeature(atlas.fields())
        result.setGeometry(geometry)
        result.setAttributes(values + [int(indicator), int(gap)])
        if not atlas.dataProvider().addFeatures([result])[0]:
            raise ValueError("Could not add atlas parcel")
    for layer in display.values():
        layer.updateExtents()
    return crs, display


def save_layers(layers, path, project):
    """Persist memory layers, including empty ones, so the project remains portable."""
    saved = {}
    for index, (name, layer) in enumerate(layers.items()):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName, options.layerName = "GPKG", name
        options.actionOnExistingFile = (QgsVectorFileWriter.CreateOrOverwriteFile if index == 0
                                        else QgsVectorFileWriter.CreateOrOverwriteLayer)
        result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(path), project.transformContext(), options)
        if result[0] != QgsVectorFileWriter.NoError:
            raise ValueError(f"GeoPackage write failed: {result}")
        reopened = QgsVectorLayer(f"{path}|layername={name}", layer.name(), "ogr")
        if (not reopened.isValid() or reopened.featureCount() != layer.featureCount()
                or reopened.crs() != layer.crs() or reopened.fields().names()[1:] != layer.fields().names()):
            raise ValueError("Reopened display GeoPackage failed schema/count/CRS validation")
        saved[name] = reopened
    return saved


def add_label(layout, item_id, text, x, y, width, height, size=9, bold=False, color="#203646"):
    label = QgsLayoutItemLabel(layout)
    label.setId(item_id)
    label.setText(text)
    text_format = QgsTextFormat()
    text_format.setFont(QFont("DejaVu Sans", size, QFont.Bold if bold else QFont.Normal))
    text_format.setSize(size)
    text_format.setColor(QColor(color))
    label.setTextFormat(text_format)
    label.setMargin(0)
    layout.addLayoutItem(label)
    label.attemptMove(QgsLayoutPoint(x, y))
    label.attemptResize(QgsLayoutSize(width, height))
    return label


def make_layout(project, layers, sources, generation_date, findings_only):
    atlas_layer = layers["atlas_parcels"]
    palette = {
        "atlas_parcels": {"color": "transparent", "outline_color": "#253b46", "outline_width": "0.5"},
        "wetland_indicators": {"color": "#8cc9bd", "outline_style": "no"},
        "flood_indicators": {"color": "#a8c6e8", "outline_style": "no"},
        "wetland_gaps": {"color": "#b67c20", "style": "b_diagonal", "outline_style": "no"},
        "flood_gaps": {"color": "#826c9d", "style": "f_diagonal", "outline_style": "no"},
    }
    for name, layer in layers.items():
        layer.renderer().setSymbol(QgsFillSymbol.createSimple(palette[name]))
        project.addMapLayer(layer)
    # Topmost first: gap hatching must remain visible over another type's fill.
    ordered = [layers[name] for name in ("atlas_parcels", "wetland_gaps", "flood_gaps",
                                        "wetland_indicators", "flood_indicators")]
    labeling = QgsPalLayerSettings()
    labeling.fieldName = "parcel_id"
    text_format = QgsTextFormat()
    text_format.setFont(QFont("DejaVu Sans", 9))
    text_format.setSize(9)
    buffer = QgsTextBufferSettings()
    buffer.setEnabled(True)
    buffer.setSize(0.8)
    buffer.setColor(QColor("white"))
    text_format.setBuffer(buffer)
    labeling.setFormat(text_format)
    atlas_layer.setLabeling(QgsVectorLayerSimpleLabeling(labeling))
    atlas_layer.setLabelsEnabled(True)
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName("Env_Constraints_Parcel_Atlas")
    layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(279.4, 215.9))
    layout.renderContext().setDpi(300)
    QgsExpressionContextUtils.setLayoutVariable(layout, "exhibit_date", generation_date)
    project.layoutManager().addLayout(layout)
    atlas = layout.atlas()
    atlas.setEnabled(True)
    atlas.setCoverageLayer(atlas_layer)
    atlas.setPageNameExpression(EXPRESSIONS["page_name"])
    atlas.setFilenameExpression(EXPRESSIONS["filename"])
    atlas.setSortFeatures(True)
    atlas.setSortExpression('"parcel_id"')
    atlas.setSortAscending(True)
    if findings_only:
        atlas.setFilterExpression(EXPRESSIONS["findings_filter"])
        atlas.setFilterFeatures(True)
    def map_item(item_id, x, y, width, height, extent):
        item = QgsLayoutItemMap(layout)
        item.setId(item_id)
        layout.addLayoutItem(item)
        item.attemptMove(QgsLayoutPoint(x, y))
        item.attemptResize(QgsLayoutSize(width, height))
        item.setCrs(project.crs())
        item.setLayers(ordered)
        item.setKeepLayerSet(True)
        item.setKeepLayerStyles(True)
        item.setBackgroundColor(QColor("#f4f6f6"))
        item.setFrameEnabled(True)
        item.zoomToExtent(extent)
        return item
    extent = atlas_layer.extent()
    extent.scale(1.5)
    main = map_item("main_map", 10, 39, 170, 101, extent)
    main.setAtlasDriven(True)
    main.setAtlasScalingMode(QgsLayoutItemMap.Auto)
    main.setAtlasMargin(0.15)
    inset = map_item("inset_map", 190, 39, 79.4, 54, extent)
    overview = QgsLayoutItemMapOverview("Main map extent", inset)
    overview.setLinkedMap(main)
    overview.setFrameSymbol(QgsFillSymbol.createSimple(
        {"color": "transparent", "outline_color": "#c14328", "outline_width": "0.6"}))
    inset.overviews().addOverview(overview)
    add_label(layout, "title", '[% ' + EXPRESSIONS["title"] + ' %]', 10, 8, 193, 10, 17, True)
    add_label(layout, "date", 'Date: [% @exhibit_date %]\nPage [% ' + EXPRESSIONS["page"] + ' %]',
              215, 9, 54.4, 13, 9)
    add_label(layout, "subtitle", '[% ' + EXPRESSIONS["subtitle"] + ' %]', 10, 22, 259.4, 7, 10, True)
    add_label(layout, "main_caption", "PARCEL DETAIL | indicator geometry and coverage gaps", 10, 31, 170, 6, 9, True)
    add_label(layout, "inset_caption", "OVERVIEW | red frame = detail extent", 190, 31, 79.4, 6, 8, True)
    legend = QgsLayoutItemLegend(layout)
    legend.setId("legend")
    legend.setTitle("")
    legend.setAutoUpdateModel(False)
    legend.model().rootGroup().clear()
    for name in palette:
        legend.model().rootGroup().addLayer(layers[name])
    legend.setLinkedMap(main)
    legend.setLegendFilterByMapEnabled(True)
    layout.addLayoutItem(legend)
    legend.attemptMove(QgsLayoutPoint(190, 98))
    legend.attemptResize(QgsLayoutSize(79.4, 39))
    scale = QgsLayoutItemScaleBar(layout)
    scale.setId("scale_bar")
    scale.setStyle("Single Box")
    scale.setLinkedMap(main)
    scale.applyDefaultSize()
    scale.setUnits(Qgis.DistanceUnit.Meters)
    scale.setSegmentSizeMode(Qgis.ScaleBarSegmentSizeMode.FitWidth)
    scale.setMinimumBarWidth(40)
    scale.setMaximumBarWidth(60)
    scale.setNumberOfSegments(2)
    scale.setNumberOfSegmentsLeft(0)
    scale.setUnitLabel("m")
    layout.addLayoutItem(scale)
    scale.attemptMove(QgsLayoutPoint(10, 142))
    add_label(layout, "scale", '[% ' + EXPRESSIONS["scale"] + ' %]', 93, 144, 85, 6, 8)
    # The maps have zero rotation; this arrow explicitly denotes grid north.
    arrow = QgsLayoutItemPolygon(QPolygonF([QPointF(0, 6), QPointF(2, 0), QPointF(4, 6), QPointF(2, 4)]), layout)
    arrow.setId("grid_north")
    arrow.setSymbol(QgsFillSymbol.createSimple({"color": "#203646", "outline_style": "no"}))
    layout.addLayoutItem(arrow)
    arrow.attemptMove(QgsLayoutPoint(260, 142))
    add_label(layout, "north", "N", 265, 142, 5, 6, 8, True)
    add_label(layout, "wetland_summary", '[% ' + EXPRESSIONS["wetland_summary"] + ' %]', 10, 155, 259.4, 6, 9)
    add_label(layout, "flood_summary", '[% ' + EXPRESSIONS["flood_summary"] + ' %]', 10, 162, 259.4, 6, 9)
    source_lines = [f"{s['dataset_id']} | retrieved {s['accessed_utc'][:10]} | effective date: {s.get('effective_date') or 'unknown'}"
                    for s in sources]
    add_label(layout, "sources", "SOURCES (synthetic; full URLs and boundary basis in source_register.json)\n" + "\n".join(source_lines),
              10, 171, 259.4, 15, 8)
    add_label(layout, "disclaimer", DISCLAIMER, 10, 188, 259.4, 18, 8, True, "#7c3825")
    add_label(layout, "footer", "ZQM Computing | Rank 1 capability example | no imagery basemap | [% " + EXPRESSIONS["crs"] + " %]",
              10, 208, 259.4, 5, 7)
    layout.setReferenceMap(main)
    return layout


def build_atlas(handoff, destination, generation_date, findings_only=False):
    """Stage a portable project, XML layout, PDF and page manifest; refuse overwrite."""
    handoff, destination = Path(handoff).resolve(), Path(destination).resolve()
    if destination == handoff or handoff in destination.parents:
        raise ValueError("Atlas destination must be outside the source handoff directory")
    if destination.exists():
        raise FileExistsError("Atlas destination already exists; choose a new revision directory")
    date.fromisoformat(generation_date)
    check_handoff_inventory(handoff)
    destination.parent.mkdir(parents=True, exist_ok=True)
    project = QgsProject()
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    project.setTitle("Rank 1 - Synthetic environmental constraint parcel atlas")
    with tempfile.TemporaryDirectory(prefix=".parcel-atlas-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        # Validate and consume only this private snapshot, including provenance.
        snapshot = stage / "source_handoff"
        shutil.copytree(handoff, snapshot, symlinks=True)
        manifest, sources, rows = read_handoff(snapshot)
        crs, layers = prepare_layers(snapshot, manifest, rows)
        project.setCrs(crs)
        shutil.copyfile(snapshot / "source_register.json", stage / "source_register.json")
        layers = save_layers(layers, stage / "atlas_data.gpkg", project)
        layout = make_layout(project, layers, sources, generation_date, findings_only)
        atlas = layout.atlas()
        atlas.updateFeatures()
        if not atlas.beginRender():
            raise ValueError("Atlas has no exportable features")
        pages = []
        try:
            while atlas.next():
                feature = layout.reportContext().feature()
                context = layout.createExpressionContext()
                for expression in EXPRESSIONS.values():
                    value = QgsExpression(expression)
                    value.evaluate(context)
                    if value.hasParserError() or value.hasEvalError():
                        raise ValueError(f"Atlas expression failed: {expression}")
                pages.append({
                    "page": len(pages) + 1, "filename": "EnvConstraints_Atlas.pdf",
                    "parcel_id": feature["parcel_id"], "crs": crs.authid(),
                    "generation_date": generation_date, "synthetic": True,
                    "wetland_status": feature["wetland_status"], "flood_status": feature["flood_status"],
                    "has_data_gap": feature["has_data_gap"], "has_indicator": feature["has_indicator"],
                    "source_register_sha256": sha256(stage / "source_register.json"),
                    "source_register_snapshot": json.dumps(sources, sort_keys=True),
                })
        finally:
            atlas.endRender()
        if not pages:
            raise ValueError("Atlas filter produced no pages")
        settings = QgsLayoutExporter.PdfExportSettings()
        settings.dpi = 300
        settings.forceVectorOutput = False
        settings.simplifyGeometries = False
        settings.textRenderFormat = Qgis.TextRenderFormat.AlwaysText
        settings.appendGeoreference = False
        settings.writeGeoPdf = False
        result, error = QgsLayoutExporter.exportToPdf(atlas, str(stage / "EnvConstraints_Atlas.pdf"), settings)
        if result != QgsLayoutExporter.Success:
            raise ValueError(f"Atlas PDF export failed: {error}")
        verify_pdf(stage / "EnvConstraints_Atlas.pdf", pages, sources)
        if not project.write(str(stage / "Env_Constraints_Parcel_Atlas.qgz")):
            raise ValueError("Could not save QGIS project")
        context = QgsReadWriteContext()
        context.setPathResolver(project.pathResolver())
        if not layout.saveAsTemplate(str(stage / "Env_Constraints_Parcel_Atlas.qpt"), context):
            raise ValueError("Could not save XML layout template")
        # QGIS 3.40 writes weak layout-layer references as raw absolute URIs,
        # even with a relative path resolver. Normalize these XML attributes.
        template_path = stage / "Env_Constraints_Parcel_Atlas.qpt"
        template = ET.parse(template_path)
        for element in template.iter():
            for attribute in ("source", "coverageLayerSource"):
                value = element.get(attribute, "")
                if value.startswith(str(stage) + "/"):
                    element.set(attribute, "./" + value[len(str(stage)) + 1:])
        template.write(template_path, encoding="utf-8", xml_declaration=True)
        with (stage / "delivery_manifest.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(pages[0]))
            writer.writeheader()
            writer.writerows(pages)
        run = {"method": "rank1_qgis_parcel_atlas_v1", "qgis_version": Qgis.QGIS_VERSION,
               "generation_date": generation_date, "crs": crs.authid(), "page_count": len(pages),
               "filter": EXPRESSIONS["findings_filter"] if findings_only else None,
               "input_manifest_sha256": sha256(snapshot / "exhibit_manifest.json"),
               "disclaimer": DISCLAIMER,
               "files": [{"filename": str(p.relative_to(stage)), "sha256": sha256(p), "bytes": p.stat().st_size}
                         for p in sorted(stage.rglob("*")) if p.is_file()]}
        (stage / "atlas_run.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
        project.clear()
        layers.clear()
        stage.rename(destination)
    return destination


def verify_pdf(path, pages, sources):
    """Reopen every exported page through Poppler before publishing the directory."""
    info = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True).stdout
    counts = [line.split(":", 1)[1].strip() for line in info.splitlines() if line.startswith("Pages:")]
    if counts != [str(len(pages))]:
        raise ValueError("Exported PDF page count differs from atlas manifest")
    for page in pages:
        text = subprocess.run(["pdftotext", "-f", str(page["page"]), "-l", str(page["page"]),
                               str(path), "-"], check=True, capture_output=True, text=True).stdout
        text = " ".join(unicodedata.normalize("NFKC", text).split())
        required = [page["parcel_id"], page["crs"], page["generation_date"], "DESKTOP SCREENING ONLY",
                    "SYNTHETIC DEMONSTRATION DATA", "Phase I ESA", "field verification",
                    "Scale 1:", f"Page {page['page']} / {len(pages)}"]
        required += [s["dataset_id"] for s in sources] + [s["accessed_utc"][:10] for s in sources]
        if any(value not in text for value in required) or "[%" in text:
            raise ValueError(f"PDF page {page['page']} lacks required labels/source dates")
        if page["has_data_gap"] and "unknown" not in text:
            raise ValueError("Data-gap page lost its uncertainty label")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--date", required=True, help="Stable generation date YYYY-MM-DD")
    parser.add_argument("--findings-only", action="store_true", help="Retain mapped indicators OR source gaps")
    args = parser.parse_args()
    app = QgsApplication([], False)
    app.initQgis()
    failure = None
    try:
        output = build_atlas(args.handoff, args.destination, args.date, args.findings_only)
        print(json.dumps({"output": str(output), "data": "synthetic", "qgis_version": Qgis.QGIS_VERSION}))
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        failure = str(exc)
    finally:
        # Clear traceback-held SIP wrappers before shutting down QGIS providers.
        gc.collect()
        app.exitQgis()
    if failure:
        parser.exit(2, f"error: {failure}\n")


if __name__ == "__main__":
    main()
