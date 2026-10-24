"""Static repository contracts; QGIS runtime behavior needs a QGIS-enabled test job."""
import ast
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
        "02_raster_processing.py": ("target_crs", "gdal:warpreproject"),
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
    source = (REPO_ROOT / "patterns" / "batch_buffer_algorithm.py").read_text(encoding="utf-8")
    for marker in (
        "class BatchBufferAlgorithm(QgsProcessingAlgorithm)",
        "QgsProcessingParameterMultipleLayers",
        "QgsProcessingParameterFolderDestination",
        "QgsProcessingOutputNumber",
        "os.replace(temporary_path, output_path)",
        "feature-count mismatch",
        "defaultValue=False",
        '"SUCCEEDED"', '"SKIPPED"', '"FAILED"',
    ):
        assert marker in source, f"Batch buffer algorithm missing contract: {marker}"
    docs = (REPO_ROOT / "processing" / "README.md").read_text(encoding="utf-8")
    assert "patterns/batch_buffer_algorithm.py" in docs
    assert "preserved by default" in docs


def test_documented_processing_script_path_exists():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "patterns/clip_and_reproject.py" in readme
    assert (REPO_ROOT / "patterns" / "clip_and_reproject.py").is_file()
