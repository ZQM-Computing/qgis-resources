"""Static repository contracts; QGIS runtime behavior needs a QGIS-enabled test job."""
import ast
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_required_resource_directories_exist():
    for name in ("expressions", "patterns", "processing", "pyqgis", "qfield", "styles", "examples", "notebooks"):
        assert (REPO_ROOT / name).is_dir(), f"{name}/ directory must exist"


def test_readme_and_license_exist():
    assert (REPO_ROOT / "README.md").is_file()
    assert (REPO_ROOT / "LICENSE").is_file()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "# qgis-resources" in readme
    assert "Coordinate reference system policy" in readme
    assert "Validation levels" in readme


def test_all_python_files_parse():
    files = sorted(REPO_ROOT.rglob("*.py"))
    assert files, "Expected Python resources"
    for path in files:
        if ".git" not in path.parts:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_numbered_examples_are_not_placeholder_scripts():
    examples = sorted((REPO_ROOT / "examples").glob("*/run.py"))
    assert len(examples) >= 6
    for path in examples:
        source = path.read_text(encoding="utf-8").lower()
        assert "print('hello')" not in source and 'print("hello")' not in source, path
        assert "def " in source or "expressions =" in source, path
        assert len(source.strip()) > 150, path


def test_notebooks_are_valid_and_have_real_lesson_content():
    notebooks = sorted((REPO_ROOT / "notebooks").glob("*.ipynb"))
    assert len(notebooks) >= 4
    for path in notebooks:
        notebook = json.loads(path.read_text(encoding="utf-8"))
        assert notebook.get("nbformat") == 4, path
        cells = notebook.get("cells", [])
        assert len(cells) >= 3, f"{path} needs explanatory and code cells"
        source = "\n".join("".join(cell.get("source", [])) for cell in cells)
        assert len(source) > 250, f"{path} appears to be a placeholder"
        assert "print('hello')" not in source and 'print("hello")' not in source
        code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
        assert code_cells, f"{path} needs executable lesson code"
        for index, cell in enumerate(code_cells):
            code = "".join(cell.get("source", []))
            assert not code.lstrip().startswith(("!", "%")), (
                f"{path} code cell {index} uses notebook-only shell/magic syntax"
            )
            ast.parse(code, filename=f"{path}:cell-{index}")
            assert cell.get("execution_count") is None, (
                f"{path} should not commit stale execution counts"
            )
            assert not cell.get("outputs"), f"{path} should not commit cell outputs"


def test_qml_styles_are_well_formed_xml():
    import xml.etree.ElementTree as ET
    styles = sorted((REPO_ROOT / "styles").glob("*.qml"))
    assert styles
    for path in styles:
        root = ET.parse(path).getroot()
        assert root.tag in {"qgis", "style", "qgis_style"}, f"Unexpected QML root in {path}"


def test_core_patterns_document_runtime_and_crs_contracts():
    expected = {
        "01_vector_analysis.py": ("import processing", "buffer_distance"),
        "02_raster_processing.py": ("target_crs", "gdal:warpreproject", "projected_boundary_layer = (", "projected_boundary_layer.crs() != target"),
        "03_spatial_joins.py": ("predicate", "points.crs()"),
        "04_crs_transforms.py": ("QgsCoordinateReferenceSystem", "target.isValid()"),
        "05_batch_processing.py": ("Path(folder)", "native:buffer", "math.isfinite", "input_paths = sorted"),
        "06_plugin_development.py": ("initGui", "unload"),
    }
    for filename, markers in expected.items():
        source = (REPO_ROOT / "patterns" / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in source, f"{filename} missing expected contract: {marker}"


def test_batch_buffer_processing_algorithm_declares_safety_contracts():
    source = (REPO_ROOT / "zqm_geospatial_tools" / "batch_buffer_algorithm.py").read_text(encoding="utf-8")
    for marker in (
        "class BatchBufferAlgorithm(QgsProcessingAlgorithm)",
        "QgsProcessingParameterMultipleLayers",
        "QgsProcessingParameterFolderDestination",
        "QgsProcessingOutputNumber",
        "os.replace(temporary_path, output_path)",
        "feature-count mismatch",
        "zero-distance buffers are not meaningful",
        "defaultValue=False",
        '"SUCCEEDED"', '"SKIPPED"', '"FAILED"',
    ):
        assert marker in source, f"Batch buffer algorithm missing contract: {marker}"
    plugin = REPO_ROOT / "zqm_geospatial_tools"
    assert (plugin / "__init__.py").is_file()
    assert (plugin / "plugin.py").is_file()
    assert (plugin / "provider.py").is_file()
    assert (plugin / "metadata.txt").is_file()
    entry = (plugin / "__init__.py").read_text(encoding="utf-8")
    provider = (plugin / "provider.py").read_text(encoding="utf-8")
    metadata = (plugin / "metadata.txt").read_text(encoding="utf-8")
    assert "def classFactory(iface)" in entry
    assert "ZqmProcessingProvider" in provider and "BatchBufferAlgorithm()" in provider
    assert "qgisMinimumVersion=3.28" in metadata
    docs = (plugin / "README.md").read_text(encoding="utf-8")
    assert "Processing provider" in docs
    assert "preserved by default" in docs


def test_documented_processing_script_path_exists():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "patterns/clip_and_reproject.py" in readme
    assert (REPO_ROOT / "patterns" / "clip_and_reproject.py").is_file()



def test_existing_examples_assert_results_not_just_execution():
    spatial_join = (REPO_ROOT / "examples" / "03-spatial-join" / "run.py").read_text(encoding="utf-8")
    assert "zone_name" in spatial_join
    assert "join_zone_name" in spatial_join
    assert "Unexpected join results" in spatial_join

    vector_example = (REPO_ROOT / "examples" / "02-processing-script" / "run.py").read_text(encoding="utf-8")
    assert "Could not add expected point attributes" in vector_example
    assert "Stored attributes do not match" in vector_example


def test_file_exports_stage_validate_and_protect_existing_outputs():
    gpkg_export = (REPO_ROOT / "pyqgis" / "batch_export_to_geopackage.py").read_text(encoding="utf-8")
    assert "TemporaryDirectory" in gpkg_export
    assert "Staged GeoPackage is missing or empty" in gpkg_export
    assert "Feature count mismatch" in gpkg_export
    assert "CRS mismatch" in gpkg_export
    assert "Geometry type mismatch" in gpkg_export
    assert "staged.replace(destination)" in gpkg_export

    pdf_export = (REPO_ROOT / "pyqgis" / "export_layout_pdf.py").read_text(encoding="utf-8")
    assert "overwrite: bool = False" in pdf_export
    assert "os.replace(temporary, destination)" in pdf_export
    assert "pdf_file.read(5) != b\"%PDF-\"" in pdf_export
    assert "FileExistsError" in pdf_export

    batch = (REPO_ROOT / "patterns" / "05_batch_processing.py").read_text(encoding="utf-8")
    assert "os.replace(staged_path, output_path)" in batch
    assert "CRS mismatch" in batch
    assert "finally:" in batch and "staged_path.unlink" in batch


def test_runtime_suite_covers_existing_exporters_and_plugin_lifecycle():
    runtime = (REPO_ROOT / "scripts" / "validate_qgis_runtime.py").read_text(encoding="utf-8")
    for marker in (
        "examples/01-expression-basics/run.py",
        "patterns/clip_and_reproject.py",
        "pyqgis/batch_export_to_geopackage.py",
        "pyqgis/export_layout_pdf.py",
        "Repeated initGui registered a second provider",
        "PDF exporter overwrote an existing file without consent",
    ):
        assert marker in runtime, f"QGIS runtime suite missing coverage: {marker}"


def test_documentation_link_checker_handles_fragments_and_rejects_escape(tmp_path):
    checker_path = REPO_ROOT / "scripts" / "check_docs.py"
    spec = importlib.util.spec_from_file_location("zqm_check_docs", checker_path)
    assert spec is not None and spec.loader is not None
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "docs" / "index.md").write_text(
        "[Guide](guide.md#section)\n[Escape](../../outside.md)\n", encoding="utf-8"
    )
    (tmp_path.parent / "outside.md").write_text("# Outside\n", encoding="utf-8")
    issues = checker.check_links(tmp_path)
    assert len(issues) == 1 and "Escape" in issues[0]
    assert "Guide" not in " ".join(issues)
