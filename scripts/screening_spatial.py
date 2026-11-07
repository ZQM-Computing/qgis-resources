#!/usr/bin/env python3
"""Conservative synthetic-only polygon screening using GDAL/OGR.

No remote fetches, writes, regulatory conclusions or customer deliverables.
A passed manifest is not proof of source coverage or reuse rights.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from screening_manifest import load_manifest, validate_manifest

# The first reproducible pilot uses a bounded geographic area of use and a
# global equal-area projection. It is NOT an unrestricted worldwide engine.
AREA_CRS = "EPSG:6933"
INPUT_CRS = "EPSG:4326"
MAX_FEATURES = 10000


class ScreeningError(ValueError):
    """Fail closed when spatial measurement evidence is incomplete."""


def _fixture_path(root: Path, ref: str) -> Path:
    """Restrict all input reads to local synthetic fixtures (no URLs or escapes)."""
    fixture_root = (root / "fixtures").resolve(strict=True)
    candidate = (root / ref).resolve(strict=True)
    if not candidate.is_relative_to(fixture_root) or candidate == fixture_root:
        raise ScreeningError("Fixture path escapes allowed directory")
    if not candidate.is_file() or candidate.suffix.casefold() != ".geojson":
        raise ScreeningError("Expected a local GeoJSON fixture")
    return candidate


def _spatial_reference(osr: Any, text: str) -> Any:
    srs = osr.SpatialReference()
    if srs.SetFromUserInput(text) != 0:
        raise ScreeningError("Unparseable coordinate reference system")
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def _collect_polygons(
    path: Path, declared_srs: Any, target_srs: Any, ogr: Any, osr: Any,
) -> Any:
    dataset = ogr.Open(str(path), 0)  # explicitly read only
    if dataset is None or dataset.GetLayerCount() != 1:
        raise ScreeningError("Expected one readable GeoJSON polygon layer")
    layer = dataset.GetLayerByIndex(0)
    actual_srs = layer.GetSpatialRef()
    if actual_srs is None or not bool(actual_srs.IsSame(declared_srs)):
        raise ScreeningError("Source CRS missing or different from manifest")
    operation = osr.CoordinateTransformation(declared_srs, target_srs)
    merged = None
    count = 0
    for feature in layer:
        count += 1
        if count > MAX_FEATURES:
            raise ScreeningError("Feature count exceeds synthetic pilot limit")
        geometry = feature.GetGeometryRef()
        if geometry is None or geometry.IsEmpty():
            raise ScreeningError("Missing or empty polygon geometry")
        if ogr.GT_Flatten(geometry.GetGeometryType()) not in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
            raise ScreeningError("Unsupported geometry type")
        if not bool(geometry.IsValid()):
            raise ScreeningError("Invalid polygon geometry")
        minx, maxx, miny, maxy = geometry.GetEnvelope()
        envelope = (minx, maxx, miny, maxy)
        if not all(math.isfinite(value) for value in envelope):
            raise ScreeningError("Non-finite geographic coordinate")
        # Blocks antimeridian/polar/large-footprint misuse of this pilot.
        if not (-170 <= minx <= maxx <= 170 and -80 <= miny <= maxy <= 80
                and maxx - minx <= 5 and maxy - miny <= 5):
            raise ScreeningError("Outside pilot geometry or projection limits")
        projected = geometry.Clone()
        if projected.Transform(operation) != 0 or not bool(projected.IsValid()):
            raise ScreeningError("Projection or projected geometry validation failed")
        if not math.isfinite(projected.GetArea()) or projected.GetArea() <= 0:
            raise ScreeningError("Non-positive projected polygon area")
        merged = projected if merged is None else merged.Union(projected)
        if merged is None or not bool(merged.IsValid()):
            raise ScreeningError("Polygon union failed")
    if count == 0:
        raise ScreeningError("Empty polygon layer cannot establish coverage")
    return merged


def analyze(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    """Measure clipped/dissolved overlay area; results are synthetic only."""
    problems = validate_manifest(manifest)
    if problems:
        raise ScreeningError("Invalid metadata contract: " + ", ".join(problems))
    from osgeo import ogr, osr

    source_srs = _spatial_reference(osr, INPUT_CRS)
    area_srs = _spatial_reference(osr, AREA_CRS)
    if not bool(_spatial_reference(osr, manifest["study_area"]["crs"]).IsSame(source_srs)):
        raise ScreeningError("Pilot study-area CRS must be EPSG:4326")
    aoi = _collect_polygons(
        _fixture_path(root, manifest["study_area"]["reference"]),
        source_srs, area_srs, ogr, osr,
    )
    aoi_area = aoi.GetArea()
    if aoi_area <= 0 or not math.isfinite(aoi_area):
        raise ScreeningError("Invalid study area")
    results = []
    if len(manifest["sources"]) > 32:
        raise ScreeningError("Too many source layers for synthetic pilot")
    for record in manifest["sources"]:
        entry: dict[str, Any] = {
            "source_id": record["id"],
            "declared_coverage": record["coverage_state"],
            "measured_intersection_area_m2": None,
            "measured_intersection_percent": None,
            "finding": "not-assessed",
        }
        if record["coverage_state"] not in {"verified", "partial"}:
            entry["finding"] = "coverage-unavailable-no-absence-inference"
        elif record["origin"] != "synthetic":
            entry["finding"] = "external-reference-not-fetched-no-inference"
        else:
            if not bool(_spatial_reference(osr, record["crs"]).IsSame(source_srs)):
                raise ScreeningError("Pilot source CRS must be EPSG:4326")
            overlays = _collect_polygons(
                _fixture_path(root, record["source_ref"]),
                source_srs, area_srs, ogr, osr,
            )
            intersection = aoi.Intersection(overlays)
            if intersection is None:
                raise ScreeningError("Polygon intersection failed")
            measured = intersection.GetArea()
            if not math.isfinite(measured) or measured < 0 or measured > aoi_area * (1 + 1e-10):
                raise ScreeningError("Invalid clipped area")
            ratio = 100.0 * measured / aoi_area
            entry["measured_intersection_area_m2"] = round(measured, 3)
            entry["measured_intersection_percent"] = round(ratio, 6)
            if record["coverage_state"] == "partial":
                entry["finding"] = "partial-source-measured-not-comprehensive"
            else:
                entry["finding"] = (
                    "synthetic-mapped-overlap" if measured > 0
                    else "synthetic-no-mapped-overlap-not-a-clearance"
                )
        results.append(entry)
    return {
        "schema_version": 1,
        "project_id": manifest["project_id"],
        "method": "OGR polygon union then intersection, projected planar area",
        "measurement_crs": AREA_CRS,
        "area_units": "square_metres",
        "study_area_m2": round(aoi_area, 3),
        "input_geometry": "synthetic-only",
        "human_review": "pending",
        "regulatory_determination": False,
        "source_results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        # The pilot deliberately resolves only the repository's fixture tree.
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(args.manifest)
        output = analyze(manifest, root)
    except (OSError, UnicodeError, ValueError, RuntimeError, ImportError):
        # Do not include raw exception messages or client filesystem paths.
        print("screening-failed: synthetic pilot inputs or environment invalid")
        return 1
    print(json.dumps(output, sort_keys=True, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
