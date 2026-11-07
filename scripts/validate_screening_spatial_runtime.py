"""Execute real GDAL/OGR spatial assertions on synthetic parcel-screening fixtures.

Invoked in the existing QGIS runtime workflow after system GDAL installation.
This is stronger than static tests; it still does not validate real datasets.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import shutil
import tempfile
from xml.etree import ElementTree
import zipfile

from osgeo import ogr, osr
from screening_manifest import load_manifest
from screening_spatial import ScreeningError, analyze, main
from screening_report import ARCHIVE_FILES, build_bundle, publish_bundle

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "fixtures" / "screening-manifest.json"


def reference_ellipsoid_rectangle_area(
    west: float, south: float, east: float, north: float
) -> float:
    """Independent analytic area of an axis-aligned WGS84 lon/lat rectangle.

    This is a runtime fixture oracle, NOT an arbitrary-polygon area algorithm.
    It uses the ellipsoid surface-area integral rather than EPSG:6933 or OGR.
    """
    semi_major = 6378137.0
    flattening = 1 / 298.257223563
    eccentricity_sq = flattening * (2 - flattening)
    eccentricity = math.sqrt(eccentricity_sq)

    def integral(latitude_degrees: float) -> float:
        """Evaluate the WGS84 ellipsoid area antiderivative at a latitude in degrees."""
        sine = math.sin(math.radians(latitude_degrees))
        return (
            sine / (2 * (1 - eccentricity_sq * sine**2))
            + math.atanh(eccentricity * sine) / (2 * eccentricity)
        )

    return (
        semi_major**2 * (1 - eccentricity_sq) * math.radians(east - west)
        * (integral(north) - integral(south))
    )


def must_fail(manifest: dict, root: Path) -> None:
    """Assert that invalid screening evidence raises the expected domain error."""
    try:
        analyze(manifest, root)
    except ScreeningError:
        return
    raise AssertionError("An invalid or unsupported screening operation unexpectedly succeeded")


def main_test() -> None:
    """Exercise spatial oracles, rejected inputs, reproducibility, and atomic report output."""
    manifest = load_manifest(SAMPLE)
    before = {
        path.name: path.read_bytes()
        for path in (REPO / "fixtures").glob("*.geojson")
    }
    output = analyze(manifest, REPO)
    assert output["measurement_crs"] == "EPSG:6933"
    assert output["human_review"] == "pending"
    assert output["input_geometry"] == "synthetic-only"
    assert output["regulatory_determination"] is False
    assert 4.9e10 < output["study_area_m2"] < 5.0e10, output
    # Independent WGS84 ellipsoid reference avoids testing projected area
    # solely against hard-coded values derived from that same projection.
    expected_aoi = reference_ellipsoid_rectangle_area(0, 0, 2, 2)
    expected_overlap = reference_ellipsoid_rectangle_area(1, 1, 2, 2)
    assert math.isclose(output["study_area_m2"], expected_aoi, rel_tol=1e-8), output
    wetland, unavailable = output["source_results"]
    assert wetland["finding"] == "synthetic-mapped-overlap", wetland
    assert math.isclose(
        wetland["measured_intersection_percent"], 24.9962937243,
        rel_tol=0, abs_tol=0.0001
    ), wetland
    assert 1.22e10 < wetland["measured_intersection_area_m2"] < 1.24e10
    assert math.isclose(
        wetland["measured_intersection_area_m2"], expected_overlap, rel_tol=1e-8
    ), wetland
    assert math.isclose(
        wetland["measured_intersection_percent"],
        round(100 * expected_overlap / expected_aoi, 6),
        abs_tol=0.000001,
    ), wetland
    assert unavailable["finding"] == "coverage-unavailable-no-absence-inference"
    assert unavailable["measured_intersection_area_m2"] is None
    assert unavailable["measured_intersection_percent"] is None
    assert output == analyze(manifest, REPO)
    assert main([str(SAMPLE)]) == 0
    assert before == {
        path.name: path.read_bytes()
        for path in (REPO / "fixtures").glob("*.geojson")
    }, "Read-only analysis modified a source fixture"
    with tempfile.TemporaryDirectory(prefix="zqm-spatial-pilot-") as dirname:
        root = Path(dirname)
        fixtures = root / "fixtures"
        fixtures.mkdir()
        for name in ("screening-aoi.geojson", "synthetic-wetlands.geojson"):
            shutil.copyfile(REPO / "fixtures" / name, fixtures / name)
        # Duplicate overlay polygons must not change unioned area.
        collection = json.loads((fixtures / "synthetic-wetlands.geojson").read_text())
        collection["features"].append(deepcopy(collection["features"][0]))
        (fixtures / "synthetic-wetlands.geojson").write_text(json.dumps(collection))
        repeated = analyze(manifest, root)
        assert repeated["source_results"][0]["measured_intersection_area_m2"] == wetland["measured_intersection_area_m2"]
        # Partial coverage is measured but never presented as comprehensive.
        partial = deepcopy(manifest)
        partial["sources"][0]["coverage_state"] = "partial"
        assert analyze(partial, root)["source_results"][0]["finding"] == "partial-source-measured-not-comprehensive"
        # No overlap is not a no-constraints conclusion.
        collection = json.loads((fixtures / "synthetic-wetlands.geojson").read_text())
        for feature in collection["features"]:
            feature["geometry"]["coordinates"] = [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]]
        (fixtures / "synthetic-wetlands.geojson").write_text(json.dumps(collection))
        nothing = analyze(manifest, root)["source_results"][0]
        assert nothing["measured_intersection_area_m2"] == 0
        assert nothing["finding"] == "synthetic-no-mapped-overlap-not-a-clearance"
        # Geometry failures: self-crossing, empty, CRS mismatch and wrong geom type.
        collection["features"][0]["geometry"]["coordinates"] = [
            [[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]
        ]
        (fixtures / "synthetic-wetlands.geojson").write_text(json.dumps(collection))
        must_fail(manifest, root)
        collection["features"] = []
        (fixtures / "synthetic-wetlands.geojson").write_text(json.dumps(collection))
        must_fail(manifest, root)
        collection["features"] = [{
            "type": "Feature", "properties": {"id": "wrong-geometry"},
            "geometry": {"type": "Point", "coordinates": [0, 0]}
        }]
        (fixtures / "synthetic-wetlands.geojson").write_text(json.dumps(collection))
        must_fail(manifest, root)
        # The study boundary must never silently assume a missing CRS.
        aoi_path = fixtures / "screening-aoi.geojson"
        study = json.loads(aoi_path.read_text())
        study["crs"] = {"type": "name", "properties": {"name": "EPSG:3857"}}
        aoi_path.write_text(json.dumps(study))
        must_fail(manifest, root)
        # Missing source file and manifest/source CRS disagreement fail closed.
        (fixtures / "synthetic-wetlands.geojson").unlink()
        must_fail(manifest, root)
        invalid_declared = deepcopy(manifest)
        invalid_declared["study_area"]["crs"] = "EPSG:3857"
        must_fail(invalid_declared, REPO)
        invalid_layer = deepcopy(manifest)
        invalid_layer["sources"][0]["crs"] = "EPSG:3857"
        must_fail(invalid_layer, REPO)
    # Reproducible evidence is one atomic ZIP; no mixed-generation files.
    package = build_bundle(manifest, REPO)
    assert package == build_bundle(manifest, REPO), "Bundle bytes are not deterministic"
    with zipfile.ZipFile(BytesIO(package), "r") as archive:
        assert tuple(sorted(archive.namelist())) == ARCHIVE_FILES
        assert archive.testzip() is None
        parsed = json.loads(archive.read("report.json"))
        assert parsed["status"] == "synthetic-review-only"
        assert parsed["screening_triage"]["decision"] == "REVIEW"
        assert parsed["screening_triage"]["priority"] == "mapped-constraint-and-gaps"
        assert parsed["screening_triage"]["mapped_constraint_sources"] == ["synthetic-wetland-inventory"]
        assert parsed["screening_triage"]["coverage_gap_sources"] == ["synthetic-flood-absent"]
        assert parsed["screening_triage"]["financial_liability_estimate"] is None
        assert parsed["screening_triage"]["human_review_required"] is True
        assert parsed["measurement"]["human_review"] == "pending"
        assert parsed["measurement"]["source_results"][0]["measured_intersection_percent"] == wetland["measured_intersection_percent"]
        assert parsed["constraint_matrix"][1]["intersected_area_m2"] is None
        assert parsed["source_register"][0]["fixture_sha256"] == sha256((REPO / "fixtures" / "synthetic-wetlands.geojson").read_bytes()).hexdigest()
        assert parsed["source_register"][1]["fixture_sha256"] is None
        text = archive.read("constraints.md").decode("utf-8")
        assert "Not assessed" in text and "no real-world absence" in text
        svg = archive.read("map.svg").decode("utf-8")
        assert "NO DATA - not mapped" in svg
        assert "SYNTHETIC ONLY" in svg
        ElementTree.fromstring(svg)
    with tempfile.TemporaryDirectory(prefix="zqm-report-bundle-") as directory:
        destination = Path(directory) / "screening.zip"
        digest = publish_bundle(destination, package)
        assert digest == sha256(package).hexdigest()
        assert destination.read_bytes() == package
        try:
            publish_bundle(destination, package)
        except ScreeningError:
            pass
        else:
            raise AssertionError("Second publication overwrote without permission")
        assert destination.read_bytes() == package
        invalid = deepcopy(manifest)
        invalid["sources"][0]["coverage_state"] = "unavailable"
        try:
            build_bundle(invalid, REPO)
        except ScreeningError:
            pass
        else:
            raise AssertionError("Invalid source was published as a valid report")
        assert destination.read_bytes() == package, "Failed analysis changed last good bundle"
        assert publish_bundle(destination, package, overwrite=True) == digest
        assert not list(Path(directory).glob(".zqm-screening-*"))
    print(json.dumps({"status": "passed", "case": "synthetic report package",
                      "files": list(ARCHIVE_FILES), "archive_sha256": sha256(package).hexdigest()}, sort_keys=True))
    print(json.dumps({
        "status": "passed", "case": "synthetic polygon clipping/dissolve",
        "measured_percent": wetland["measured_intersection_percent"],
        "not_real_world": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main_test()
