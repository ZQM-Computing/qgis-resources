#!/usr/bin/env python3
"""Build one reproducible, synthetic-only screening evidence bundle.

The ZIP is staged and published atomically; no client-facing approval,
real-world data-source verification, or regulatory conclusion is implied.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html import escape
from io import BytesIO
import json
import math
import os
from pathlib import Path
import tempfile
import zipfile

from screening_manifest import load_manifest
from screening_triage import build_triage
from screening_spatial import (
    AREA_CRS, INPUT_CRS, ScreeningError, _collect_polygons,
    _fixture_path, _spatial_reference, analyze,
)

ARCHIVE_FILES = ("constraints.md", "map.svg", "report.json", "sources.json")
PALETTE = ("#0c7f86", "#a95d2a", "#7865a9", "#5b7b2c", "#9b4670", "#306eb1")
MAX_SVG_VERTICES = 50000


def _json_bytes(value: object) -> bytes:
    """Serialize finite JSON deterministically as newline-terminated UTF-8 bytes."""
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True) + "\n").encode("utf-8")


def _cell(value: object) -> str:
    """Prevent metadata from altering report table structure."""
    if value is None:
        return "Not available"
    return " ".join(str(value).replace("|", r"\|").split())


def _geometry_path(geometry: object, ogr: object, project: object) -> str:
    """Convert projected OGR polygon rings into bounded SVG paths."""
    commands: list[str] = []
    count = 0

    def emit(geom: object) -> None:
        """Append polygon rings recursively while enforcing the map vertex budget."""
        nonlocal count
        kind = ogr.GT_Flatten(geom.GetGeometryType())
        if kind in (ogr.wkbMultiPolygon, ogr.wkbGeometryCollection):
            for i in range(geom.GetGeometryCount()):
                emit(geom.GetGeometryRef(i))
            return
        if kind in (ogr.wkbPoint, ogr.wkbLineString, ogr.wkbMultiLineString):
            # Zero-area intersections may contain line-only boundary touches.
            return
        if kind != ogr.wkbPolygon:
            raise ScreeningError("Unsupported projected geometry for map")
        for ring_i in range(geom.GetGeometryCount()):
            ring = geom.GetGeometryRef(ring_i)
            length = ring.GetPointCount()
            if length < 4:
                raise ScreeningError("Malformed projected polygon ring")
            points = []
            for i in range(length):
                count += 1
                if count > MAX_SVG_VERTICES:
                    raise ScreeningError("Map geometry exceeds vertex budget")
                x, y = ring.GetX(i), ring.GetY(i)
                if not math.isfinite(x) or not math.isfinite(y):
                    raise ScreeningError("Invalid map coordinates")
                px, py = project(x, y)
                points.append((px, py))
            commands.append(
                "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in points) + " Z"
            )

    emit(geometry)
    return " ".join(commands)


def _map_svg(manifest: dict, root: Path, measurements: dict) -> str:
    """Create a measurement-projection map of only measured synthetic layers."""
    from osgeo import ogr, osr

    input_srs = _spatial_reference(osr, INPUT_CRS)
    area_srs = _spatial_reference(osr, AREA_CRS)
    aoi = _collect_polygons(
        _fixture_path(root, manifest["study_area"]["reference"]),
        input_srs, area_srs, ogr, osr,
    )
    minx, maxx, miny, maxy = aoi.GetEnvelope()
    if not maxx > minx or not maxy > miny:
        raise ScreeningError("Empty study area map extent")
    # Fit projected coordinates without stretching the x/y scale differently.
    scale = min(670 / (maxx - minx), 460 / (maxy - miny))
    offsetx = 38 + (670 - (maxx - minx) * scale) / 2
    offsety = 112 + (460 - (maxy - miny) * scale) / 2

    def project(x: float, y: float) -> tuple[float, float]:
        """Fit projected coordinates into the SVG viewport with a uniform scale."""
        return offsetx + (x - minx) * scale, offsety + (maxy - y) * scale

    outline = _geometry_path(aoi, ogr, project)
    fills: list[str] = []
    legends: list[str] = []
    for index, (source, result) in enumerate(zip(manifest["sources"], measurements["source_results"])):
        hue = PALETTE[index % len(PALETTE)]
        label = escape(source["id"][:45])
        if result["measured_intersection_area_m2"] is not None:
            overlays = _collect_polygons(
                _fixture_path(root, source["source_ref"]),
                input_srs, area_srs, ogr, osr,
            )
            intersection = aoi.Intersection(overlays)
            if intersection is None:
                raise ScreeningError("Map overlay intersection failed")
            path = _geometry_path(intersection, ogr, project)
            if path:
                fills.append(
                    f'<path d="{path}" fill="{hue}" fill-opacity="0.52" '
                    f'fill-rule="evenodd" stroke="{hue}" stroke-width="1.5"/>'
                )
            description = f'{result["measured_intersection_percent"]:.4f}% measured'
        else:
            description = "NO DATA - not mapped"
        if index < 8:
            y = 190 + 49 * index
            legends.append(
                f'<rect x="750" y="{y-17}" width="15" height="15" '
                f'fill="{hue if result["measured_intersection_area_m2"] is not None else "#ffffff"}" '
                f'stroke="#4e6578" stroke-width="1"/>'
                f'<text x="774" y="{y-4}" font-size="12" fill="#18324a">{label}</text>'
                f'<text x="774" y="{y+13}" font-size="11" fill="#586a78">{escape(description)}</text>'
            )
    title = escape(manifest["project_id"])
    hidden = max(0, len(manifest["sources"]) - 8)
    hidden_note = f'<text x="749" y="615" font-size="12">+{hidden} more in report.json</text>' if hidden else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 680" '
        'width="1120" height="680" role="img" aria-labelledby="title desc">\n'
        f'<title id="title">Synthetic screening diagram - {title}</title>\n'
        '<desc id="desc">Projected synthetic study boundary and measured polygon '
        'intersections only. Unavailable layers are not mapped.</desc>\n'
        '<rect width="1120" height="680" fill="#f7f9fa"/>\n'
        '<rect x="22" y="98" width="705" height="493" rx="9" fill="#edf4f7" stroke="#b2c3ce"/>\n'
        f'<text x="32" y="42" font-size="25" font-weight="700" fill="#193951">{title}</text>\n'
        '<text x="32" y="69" font-size="16" fill="#a13b2f" font-weight="700">'
        'SYNTHETIC ONLY - NOT A PARCEL OR REGULATORY MAP</text>\n'
        f'<path d="{outline}" fill="#ffffff" fill-opacity="0.6" fill-rule="evenodd" '
        'stroke="#173d59" stroke-width="3"/>\n'
        + "\n".join(fills) + "\n"
        f'<path d="{outline}" fill="none" stroke="#173d59" stroke-width="2.5"/>\n'
        '<text x="39" y="617" font-size="13" fill="#314f65">'
        'Measurement/display projection: EPSG:6933 | area in square metres</text>\n'
        '<text x="39" y="640" font-size="13" fill="#314f65">'
        'No regulatory setbacks or survey boundaries shown</text>\n'
        '<rect x="740" y="100" width="360" height="525" rx="9" fill="#ffffff" stroke="#b2c3ce"/>\n'
        '<text x="751" y="137" font-size="19" font-weight="700" fill="#193951">Constraint layers</text>\n'
        '<text x="751" y="158" font-size="12" fill="#5c6876">No data is not a clear result.</text>\n'
        + "\n".join(legends) + "\n" + hidden_note + "\n"
        '<text x="33" y="669" font-size="12" fill="#914c3d">'
        'REVIEW PENDING | Not verified against external datasets | Not for client delivery</text>\n'
        '</svg>\n'
    )


def _source_register(manifest: dict, root: Path, measurements: dict) -> list[dict]:
    """Pair source claims with findings and hashes of measured synthetic fixtures."""
    records = []
    for src, result in zip(manifest["sources"], measurements["source_results"]):
        local_hash = None
        if src["origin"] == "synthetic" and src["coverage_state"] in {"verified", "partial"}:
            local_hash = sha256(_fixture_path(root, src["source_ref"]).read_bytes()).hexdigest()
        records.append({
            "id": src["id"],
            "title": src["title"],
            "authority": src["authority"],
            "origin": src["origin"],
            "source_reference": src.get("source_ref"),
            "fixture_sha256": local_hash,
            "coverage_state_claimed": src["coverage_state"],
            "reuse_rights_claimed": src["reuse_rights"],
            "license_claimed": src.get("license"),
            "retrieved_at_utc_claimed": src.get("retrieved_at_utc"),
            "effective_date_claimed": src.get("effective_date"),
            "declared_crs": src.get("crs"),
            "limitations": src["limitations"],
            "finding": result["finding"],
        })
    return records


def _markdown(manifest: dict, measurements: dict, records: list[dict]) -> str:
    """Render measurements and source limitations as a synthetic review report."""
    lines = [
        "# Preliminary synthetic GIS screening - review copy",
        "",
        "**NOT A CUSTOMER DELIVERABLE OR REGULATORY DETERMINATION.**",
        "",
        f'Project: {_cell(manifest["project_id"])}  ',
        f'Jurisdiction: {_cell(manifest["jurisdiction"]["country_code"])} / '
        f'{_cell(manifest["jurisdiction"]["region"])} (synthetic)  ',
        f'Method: {_cell(measurements["method"])}  ',
        f'Measurement CRS: {AREA_CRS}; units: square metres  ',
        f'Area of interest: {measurements["study_area_m2"]:,.3f} m²  ',
        "Review: pending; synthetic input and provenance assertions are not independently verified.",
        "",
        "## Constraint matrix",
        "",
        "| Source | Coverage claim | Finding | Intersected m² | AOI % |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for source, result in zip(records, measurements["source_results"]):
        area = result["measured_intersection_area_m2"]
        percent = result["measured_intersection_percent"]
        lines.append(
            f'| {_cell(source["id"])} | {_cell(result["declared_coverage"])} | '
            f'{_cell(result["finding"])} | '
            f'{"Not assessed" if area is None else f"{area:,.3f}"} | '
            f'{"Not assessed" if percent is None else f"{percent:.6f}"} |'
        )
    lines += [
        "",
        "## Source provenance and caveats",
        "",
        "Source references are recorded for reproducibility, not verified public citations.",
    ]
    for source in records:
        lines += [
            "",
            f'### {_cell(source["id"])}',
            "",
            f'- Authority: {_cell(source["authority"])}',
            f'- Reference: {_cell(source["source_reference"])}',
            f'- Source-file SHA256: {_cell(source["fixture_sha256"])}',
            f'- Licensing assertion: {_cell(source["license_claimed"])} / rights {_cell(source["reuse_rights_claimed"])}',
            f'- Effective / retrieved UTC: {_cell(source["effective_date_claimed"])} / {_cell(source["retrieved_at_utc_claimed"])}',
            f'- Limitations: {_cell(source["limitations"])}',
        ]
    lines += [
        "",
        "## Human review and escalation",
        "",
        "- Confirm real-world parcel boundary, coordinate reference system and data usage rights before any applied analysis.",
        "- Verify complete jurisdiction-specific sources, effective editions and missing-data coverage.",
        "- Fieldwork, professional surveys, wetlands delineations, environmental site assessments, legal interpretations and permitting are excluded.",
        "- All source coverage claims in this package describe artificial fixtures; no real-world absence or approval may be inferred.",
        "- Human review is pending; no customer delivery, regulatory determination or production release is authorized.",
        "",
        "See map.svg for the projected schematic and report.json for machine-readable findings.",
        "",
    ]
    return "\n".join(lines)


def build_bundle(manifest: dict, root: Path) -> bytes:
    """Compute and package all evidence before any output is published."""
    measurements = analyze(manifest, root)
    sources = _source_register(manifest, root, measurements)
    triage = build_triage(measurements)
    report = {
        "schema_version": 1,
        "status": "synthetic-review-only",
        "project_id": manifest["project_id"],
        "jurisdiction": manifest["jurisdiction"],
        "study_area_reference": manifest["study_area"]["reference"],
        "measurement": measurements,
        "screening_triage": triage,
        "constraint_matrix": [
            {
                "source_id": item["source_id"],
                "coverage_state": item["declared_coverage"],
                "finding": item["finding"],
                "intersected_area_m2": item["measured_intersection_area_m2"],
                "intersected_percent": item["measured_intersection_percent"],
            }
            for item in measurements["source_results"]
        ],
        "source_register": sources,
        "human_review": "pending",
        "regulatory_determination": False,
        "disclaimer": "Synthetic test only: no real-world coverage, clearance, or licensing verification.",
    }
    contents = {
        "constraints.md": _markdown(manifest, measurements, sources).encode("utf-8"),
        "map.svg": _map_svg(manifest, root, measurements).encode("utf-8"),
        "report.json": _json_bytes(report),
        "sources.json": _json_bytes(sources),
    }
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for name in ARCHIVE_FILES:
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            handle.writestr(entry, contents[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return archive.getvalue()


def publish_bundle(path: Path, bundle: bytes, *, overwrite: bool = False) -> str:
    """Atomically publish one ZIP; never expose a mixed-generation report set.

    This intentionally requires filesystem hard links for no-clobber mode.
    An unsupported host/filesystem fails closed instead of partial publication.
    """
    if path.suffix.lower() != ".zip" or path.is_symlink():
        raise ScreeningError("Output must be a non-symlink .zip path")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ScreeningError("Output parent must be an existing real directory")
    if path.exists() and not overwrite:
        raise ScreeningError("Output already exists; overwrite not authorized")
    if not isinstance(bundle, bytes) or len(bundle) > 32 * 1024 * 1024:
        raise ScreeningError("Invalid report bundle size")
    try:
        with zipfile.ZipFile(BytesIO(bundle)) as reader:
            if tuple(sorted(reader.namelist())) != ARCHIVE_FILES or reader.testzip() is not None:
                raise ScreeningError("Bundle integrity validation failed")
    except (zipfile.BadZipFile, EOFError, OSError) as exc:
        raise ScreeningError("Bundle integrity validation failed") from exc
    fd, candidate = tempfile.mkstemp(prefix=".zqm-screening-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(bundle)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ScreeningError("Refusing to replace a symlink or non-file")
            os.replace(candidate, path)
        else:
            # Atomic create-only publication; avoids check-then-write races.
            os.link(candidate, path)
        return sha256(bundle).hexdigest()
    finally:
        if os.path.exists(candidate):
            os.unlink(candidate)


def main(argv: list[str] | None = None) -> int:
    """Build and publish a synthetic ZIP or report a sanitized failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Synthetic manifest JSON")
    parser.add_argument("--out", type=Path, required=True, help="ZIP output destination")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace existing ZIP")
    args = parser.parse_args(argv)
    try:
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(args.manifest)
        bundle = build_bundle(manifest, root)
        digest = publish_bundle(args.out, bundle, overwrite=args.overwrite)
    except (OSError, ValueError, UnicodeError, ImportError, RuntimeError, zipfile.BadZipFile):
        print("screening-report-failed: invalid synthetic input or output environment")
        return 1
    print("Synthetic review bundle staged and published; SHA256=" + digest)
    print("Human review pending; no external, legal or regulatory authorization implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
