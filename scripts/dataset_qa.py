#!/usr/bin/env python3
"""Read-only vector/raster inventory and quality audit using GDAL/OGR.

Run with a Python interpreter that can import osgeo.gdal and osgeo.ogr.
The auditor never writes to input datasets. Reports are written only to the
explicit report paths supplied by the caller.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SUPPORTED_VECTOR = {".gpkg", ".shp", ".geojson", ".json", ".gml", ".kml", ".sqlite"}
SUPPORTED_RASTER = {".tif", ".tiff", ".vrt", ".img", ".asc", ".jp2", ".nc"}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def finding(rule_id: str, severity: str, message: str, *, dataset: str,
            layer: str | None = None, evidence: Any = None, remediation: str = "") -> dict[str, Any]:
    """Build a stable, serializable finding record."""
    if severity not in SEVERITY_ORDER:
        raise ValueError(f"Unsupported severity: {severity}")
    result = {
        "rule_id": rule_id,
        "severity": severity,
        "dataset": dataset,
        "message": message,
        "remediation": remediation,
    }
    if layer is not None:
        result["layer"] = layer
    if evidence is not None:
        result["evidence"] = evidence
    return result


def sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort findings deterministically for stable reports and diffs."""
    return sorted(findings, key=lambda item: (
        SEVERITY_ORDER[item["severity"]], item["dataset"],
        item.get("layer", ""), item["rule_id"], item["message"],
    ))


def summarize(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "error": sum(f["severity"] == "error" for f in findings),
        "warning": sum(f["severity"] == "warning" for f in findings),
        "info": sum(f["severity"] == "info" for f in findings),
        "total": len(findings),
    }


def _crs_text(spatial_ref: Any) -> str | None:
    if spatial_ref is None:
        return None
    authority = spatial_ref.GetAuthorityCode(None)
    authority_name = spatial_ref.GetAuthorityName(None)
    if authority and authority_name:
        return f"{authority_name}:{authority}"
    wkt = spatial_ref.ExportToWkt() or None
    # GeoPackage/OGR may expose an explicitly undefined CRS as a placeholder WKT.
    if wkt and "undefined" in wkt.casefold():
        return None
    return wkt


def _audit_vector(path: Path, display_path: str, gdal: Any, ogr: Any,
                  required_fields: list[str], id_fields: list[str],
                  expected_crs: str | None, check_geometry: bool) -> dict[str, Any] | None:
    dataset = ogr.Open(str(path), 0)  # 0 = read-only
    if dataset is None:
        return None
    inventory: dict[str, Any] = {
        "path": display_path, "kind": "vector", "driver": dataset.GetDriver().GetName(),
        "size_bytes": path.stat().st_size, "layers": [],
    }
    findings: list[dict[str, Any]] = []
    for index in range(dataset.GetLayerCount()):
        layer = dataset.GetLayerByIndex(index)
        if layer is None:
            findings.append(finding("VECTOR_LAYER_UNREADABLE", "error",
                "Could not open vector layer by index.", dataset=display_path,
                evidence={"layer_index": index}))
            continue
        name = layer.GetName()
        srs = layer.GetSpatialRef()
        crs = _crs_text(srs)
        definition = layer.GetLayerDefn()
        fields = [{"name": definition.GetFieldDefn(i).GetName(),
                   "type": definition.GetFieldDefn(i).GetTypeName()}
                  for i in range(definition.GetFieldCount())]
        field_names = {field["name"].casefold() for field in fields}
        feature_count = layer.GetFeatureCount(force=1)
        layer_info: dict[str, Any] = {
            "name": name, "geometry_type": ogr.GeometryTypeToName(layer.GetGeomType()),
            "feature_count": feature_count, "crs": crs, "fields": fields,
        }
        if not crs:
            findings.append(finding("VECTOR_CRS_MISSING", "error",
                "Vector layer has no declared CRS; coordinates must not be guessed.",
                dataset=display_path, layer=name,
                remediation="Identify the source CRS from authoritative metadata, then assign or transform it explicitly."))
        elif expected_crs and crs.casefold() != expected_crs.casefold():
            findings.append(finding("VECTOR_CRS_UNEXPECTED", "warning",
                "Vector layer CRS does not match the configured expected CRS.",
                dataset=display_path, layer=name,
                evidence={"actual": crs, "expected": expected_crs},
                remediation="Confirm the intended analysis CRS and transform a copy if required."))
        if feature_count < 0:
            findings.append(finding("VECTOR_FEATURE_COUNT_UNKNOWN", "info",
                "Provider did not return a reliable feature count; the audit still streams features for configured checks.",
                dataset=display_path, layer=name,
                remediation="If a count is required for acceptance, compute it with a provider-supported count operation and record the method."))
        elif feature_count == 0:
            findings.append(finding("VECTOR_LAYER_EMPTY", "warning",
                "Vector layer contains no features.", dataset=display_path, layer=name,
                remediation="Confirm that the source is expected to be empty and review upstream filters or exports."))
        for required in required_fields:
            if required.casefold() not in field_names:
                findings.append(finding("VECTOR_REQUIRED_FIELD_MISSING", "error",
                    f"Required field {required!r} is missing.", dataset=display_path, layer=name,
                    evidence={"required_field": required, "available_fields": [f["name"] for f in fields]},
                    remediation="Correct the schema or update the audit configuration to the authoritative field name."))
        # Resolve configured names to provider field indexes once. OGR field lookup
        # is not consistently case-insensitive across drivers.
        field_index_by_name = {field["name"].casefold(): index for index, field in enumerate(fields)}
        selected_ids = [
            (configured, field_index_by_name[configured.casefold()])
            for configured in id_fields if configured.casefold() in field_index_by_name
        ]
        if id_fields and not selected_ids:
            findings.append(finding("VECTOR_ID_FIELD_MISSING", "warning",
                "None of the configured identifier fields exists on this layer.",
                dataset=display_path, layer=name,
                evidence={"configured_fields": id_fields},
                remediation="Configure the identifier field used by this layer or accept that uniqueness was not checked."))
        layer.ResetReading()
        seen: set[tuple[str, str]] = set()
        null_ids = 0
        duplicate_ids = 0
        empty_geometries = 0
        invalid_geometries = 0
        unchecked_geometries = 0
        checked_geometries = 0
        for feature in layer:
            if selected_ids:
                # Use the first configured candidate present on this layer.
                id_name, id_index = selected_ids[0]
                value = feature.GetField(id_index)
                if value is None or (isinstance(value, str) and not value.strip()):
                    null_ids += 1
                else:
                    # Preserve type identity: integer 1 and string "1" are not
                    # silently treated as the same identifier.
                    key = (type(value).__name__, str(value))
                    if key in seen:
                        duplicate_ids += 1
                    else:
                        seen.add(key)
            if check_geometry:
                geometry = feature.GetGeometryRef()
                if geometry is None or geometry.IsEmpty():
                    empty_geometries += 1
                else:
                    try:
                        is_valid = geometry.IsValid()
                    except Exception:
                        unchecked_geometries += 1
                    else:
                        checked_geometries += 1
                        if not is_valid:
                            invalid_geometries += 1
        layer_info["geometry_checks"] = {
            "enabled": check_geometry,
            "checked_nonempty": checked_geometries,
            "unchecked_validity": unchecked_geometries,
            "empty": empty_geometries,
            "invalid": invalid_geometries,
        }
        if null_ids:
            findings.append(finding("VECTOR_ID_NULL", "warning",
                "Configured identifier field has null or blank values.", dataset=display_path, layer=name,
                evidence={"count": null_ids, "fields": [name for name, _ in selected_ids]},
                remediation="Review identifier generation and source records."))
        if duplicate_ids:
            findings.append(finding("VECTOR_ID_DUPLICATE", "warning",
                "Configured identifier field contains duplicate values.", dataset=display_path, layer=name,
                evidence={"duplicate_occurrences": duplicate_ids, "fields": [name for name, _ in selected_ids]},
                remediation="Determine whether identifiers must be unique; do not deduplicate without a domain rule."))
        if empty_geometries:
            findings.append(finding("VECTOR_GEOMETRY_EMPTY", "warning",
                "Layer contains features with empty or missing geometry.", dataset=display_path, layer=name,
                evidence={"count": empty_geometries},
                remediation="Review affected features and the requirements of downstream tools."))
        if invalid_geometries:
            findings.append(finding("VECTOR_GEOMETRY_INVALID", "warning",
                "Layer contains geometries reported invalid by the provider.", dataset=display_path, layer=name,
                evidence={"count": invalid_geometries},
                remediation="Inspect and repair a copy only after choosing a documented geometry-repair policy."))
        inventory["layers"].append(layer_info)
    dataset = None
    return {"inventory": inventory, "findings": findings}


def _audit_raster(path: Path, display_path: str, gdal: Any,
                  expected_crs: str | None) -> dict[str, Any] | None:
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None:
        return None
    projection = dataset.GetProjectionRef() or ""
    crs = None
    if projection:
        from osgeo import osr
        srs = osr.SpatialReference()
        if srs.ImportFromWkt(projection) == 0:
            authority = srs.GetAuthorityCode(None)
            authority_name = srs.GetAuthorityName(None)
            crs = f"{authority_name}:{authority}" if authority and authority_name else projection
    transform = dataset.GetGeoTransform(can_return_null=True)
    width, height, bands = dataset.RasterXSize, dataset.RasterYSize, dataset.RasterCount
    finite_transform = transform is not None and all(math.isfinite(float(v)) for v in transform)
    pixel_resolution = None
    if finite_transform:
        # Affine pixel/line vectors can be rotated; use vector magnitudes rather
        # than abs(GT(1))/abs(GT(5)), which is wrong for rotated grids.
        pixel_resolution = [
            math.hypot(float(transform[1]), float(transform[4])),
            math.hypot(float(transform[2]), float(transform[5])),
        ]
    info: dict[str, Any] = {
        "path": display_path, "kind": "raster",
        "driver": dataset.GetDriver().ShortName,
        "size_bytes": path.stat().st_size,
        "width": width, "height": height, "band_count": bands,
        "crs": crs,
        "geotransform": list(transform) if transform is not None else None,
        "resolution": pixel_resolution,
        "extent": None, "bands": [],
    }
    findings: list[dict[str, Any]] = []
    if not crs:
        findings.append(finding("RASTER_CRS_MISSING", "error",
            "Raster has no declared CRS; coordinates must not be guessed.",
            dataset=display_path,
            remediation="Recover the CRS from authoritative metadata before using this raster in spatial analysis."))
    elif expected_crs and crs.casefold() != expected_crs.casefold():
        findings.append(finding("RASTER_CRS_UNEXPECTED", "warning",
            "Raster CRS does not match the configured expected CRS.", dataset=display_path,
            evidence={"actual": crs, "expected": expected_crs},
            remediation="Confirm the target CRS and explicitly warp a copy if needed."))
    if width <= 0 or height <= 0 or bands <= 0:
        findings.append(finding("RASTER_DIMENSIONS_INVALID", "error",
            "Raster has a nonpositive width, height, or band count.", dataset=display_path,
            evidence={"width": width, "height": height, "bands": bands}))
    if transform is None:
        findings.append(finding("RASTER_GEOREFERENCE_MISSING", "warning",
            "Raster has no affine geotransform.", dataset=display_path,
            remediation="Check whether this raster requires georeferencing before spatial use."))
    else:
        x0, px, rx, y0, ry, py = transform
        corners = [(x0, y0), (x0 + width * px, y0 + width * rx),
                   (x0 + height * ry, y0 + height * py),
                   (x0 + width * px + height * ry, y0 + width * rx + height * py)]
        info["extent"] = {
            "xmin": min(p[0] for p in corners), "ymin": min(p[1] for p in corners),
            "xmax": max(p[0] for p in corners), "ymax": max(p[1] for p in corners),
        }
        if not all(math.isfinite(float(v)) for v in transform):
            findings.append(finding("RASTER_GEOREFERENCE_NONFINITE", "error",
                "Raster geotransform contains non-finite values.", dataset=display_path))
    for band_index in range(1, bands + 1):
        band = dataset.GetRasterBand(band_index)
        nodata = band.GetNoDataValue()
        if nodata is not None and not math.isfinite(float(nodata)):
            nodata = str(nodata).lower() if math.isnan(float(nodata)) else ("infinity" if nodata > 0 else "-infinity")
        scale = band.GetScale()
        offset = band.GetOffset()
        band_info = {"index": band_index, "data_type": gdal.GetDataTypeName(band.DataType),
                     "nodata": nodata, "scale": scale, "offset": offset,
                     "block_size": list(band.GetBlockSize())}
        info["bands"].append(band_info)
    dataset = None
    return {"inventory": info, "findings": findings}


def audit_paths(paths: list[Path], *, root: Path, required_fields: list[str] | None = None,
                id_fields: list[str] | None = None, expected_crs: str | None = None,
                check_geometry: bool = True) -> dict[str, Any]:
    """Inspect supported datasets read-only and return a deterministic report."""
    try:
        from osgeo import gdal, ogr
    except ImportError as exc:
        raise RuntimeError("GDAL Python bindings are required (osgeo.gdal and osgeo.ogr). Run with the QGIS/GDAL Python environment.") from exc
    gdal.UseExceptions()
    ogr.UseExceptions()
    required_fields = required_fields or []
    id_fields = id_fields or []
    candidates: list[Path] = []
    for supplied in paths:
        if supplied.is_dir():
            candidates.extend(p for p in supplied.rglob("*") if p.is_file())
        elif supplied.is_file():
            candidates.append(supplied)
    candidates = sorted({p.resolve() for p in candidates if p.suffix.casefold() in SUPPORTED_VECTOR | SUPPORTED_RASTER})
    datasets: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for path in candidates:
        try:
            display = path.relative_to(root.resolve()).as_posix()
        except ValueError:
            display = path.name
        result = None
        try:
            if path.suffix.casefold() in SUPPORTED_VECTOR:
                result = _audit_vector(path, display, gdal, ogr, required_fields, id_fields, expected_crs, check_geometry)
            if result is None and path.suffix.casefold() in SUPPORTED_RASTER:
                result = _audit_raster(path, display, gdal, expected_crs)
        except Exception as exc:
            unreadable.append(display)
            all_findings.append(finding("DATASET_READ_FAILED", "error",
                "GDAL/OGR raised an error while inspecting this dataset.",
                dataset=display, evidence={"error_type": type(exc).__name__, "message": str(exc)},
                remediation="Check dataset integrity, provider support, file permissions, and sidecar files."))
            continue
        if result is None:
            # Vector formats can be opened by GDAL as well; retry raster opening only for supported raster suffixes.
            unreadable.append(display)
            all_findings.append(finding("DATASET_UNREADABLE", "error",
                "Dataset could not be opened by the appropriate GDAL/OGR reader.",
                dataset=display, remediation="Check file integrity, provider support, access permissions, and whether sidecar files are present."))
        else:
            datasets.append(result["inventory"])
            all_findings.extend(result["findings"])
    sorted_findings = sort_findings(all_findings)
    return {
        "schema_version": 1,
        "root": ".",
        "dataset_count": len(datasets),
        "datasets": datasets,
        "findings": sorted_findings,
        "summary": summarize(sorted_findings),
        "unreadable_datasets": unreadable,
    }


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Geospatial dataset QA report", "",
        f"- Datasets inspected: **{report['dataset_count']}**",
        f"- Errors: **{summary['error']}**",
        f"- Warnings: **{summary['warning']}**",
        f"- Informational findings: **{summary['info']}**", "",
        "## Dataset inventory", "",
        "| Dataset | Kind | Layers / dimensions | CRS |",
        "|---|---|---|---|",
    ]
    for dataset in report["datasets"]:
        if dataset["kind"] == "vector":
            detail = "; ".join(f"{layer['name']} ({layer['feature_count']} features, {layer['geometry_type']})" for layer in dataset["layers"]) or "No layers"
        else:
            detail = f"{dataset['width']} × {dataset['height']}, {dataset['band_count']} band(s)"
        lines.append(f"| {dataset['path']} | {dataset['kind']} | {detail} | {dataset.get('crs') or 'MISSING'} |")
    lines.extend(["", "## Findings", ""])
    if not report["findings"]:
        lines.append("No findings for the configured checks.")
    else:
        lines.extend(["| Severity | Rule | Dataset / layer | Finding | Remediation |", "|---|---|---|---|---|"])
        for item in report["findings"]:
            location = item["dataset"] + (f" / {item['layer']}" if item.get("layer") else "")
            lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in (
                item["severity"].upper(), item["rule_id"], location, item["message"], item.get("remediation", "")
            )) + " |")
    lines.extend(["", "## Safety note", "",
        "This report is observational. It does not assign CRSs, repair geometries, delete features, or rewrite source datasets.", ""])
    return "\n".join(lines)


def json_safe(value: Any) -> Any:
    """Convert non-finite numeric metadata into JSON-safe strings."""
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "nan"
        return "infinity" if value > 0 else "-infinity"
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Input dataset paths or directories (searched recursively)")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Root used to make report paths relative (default: current directory)")
    parser.add_argument("--json", dest="json_path", type=Path, required=True, help="Write JSON report to this path")
    parser.add_argument("--markdown", type=Path, help="Optionally write a Markdown report")
    parser.add_argument("--required-field", action="append", default=[], help="Field required on every vector layer; repeatable")
    parser.add_argument("--id-field", action="append", default=[], help="Candidate unique identifier field; repeatable")
    parser.add_argument("--expected-crs", help="Expected CRS authority ID, e.g. EPSG:26917; mismatch is a warning")
    parser.add_argument("--skip-geometry-validity", action="store_true", help="Skip potentially expensive per-feature geometry validity checks")
    parser.add_argument("--fail-on-warning", action="store_true", help="Return nonzero if any warning is reported")
    args = parser.parse_args(argv)
    try:
        report = audit_paths(args.paths, root=args.root, required_fields=args.required_field,
                             id_fields=args.id_field, expected_crs=args.expected_crs,
                             check_geometry=not args.skip_geometry_validity)
    except (RuntimeError, OSError, ValueError) as exc:
        parser.error(str(exc))
    _write_report(args.json_path, json.dumps(json_safe(report), indent=2, sort_keys=True, allow_nan=False) + "\n")
    if args.markdown:
        _write_report(args.markdown, markdown_report(report))
    print(json.dumps(report["summary"], sort_keys=True))
    return 1 if report["summary"]["error"] or (args.fail_on_warning and report["summary"]["warning"]) else 0


if __name__ == "__main__":
    sys.exit(main())
