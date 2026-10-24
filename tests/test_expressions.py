"""
Tests for QGIS resources repository structure and content.

Current scope (2026-10-24): only qfield/, scripts/, and tests/ ship.
expressions/, pyqgis/, processing/, styles/, and examples/ are planned,
not yet shipped — see README.md. Tests for those folders are skipped
with that reason below, and must be re-enabled when the content lands.
"""
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

PLANNED_FOLDERS = ["expressions", "pyqgis", "processing", "styles", "examples"]
PLANNED_REASON = (
    "Planned, not yet shipped (see README.md): "
    + ", ".join(f"{f}/" for f in PLANNED_FOLDERS)
    + " do not exist in this tree yet."
)


def test_qfield_directory_exists():
    """Verify the QField guide directory exists."""
    assert (REPO_ROOT / "qfield").is_dir(), "qfield/ directory must exist"


def test_qfield_guide_exists():
    """Verify the QField guide itself exists."""
    assert (REPO_ROOT / "qfield" / "README.md").is_file(), "qfield/README.md must exist"


def test_scripts_directory_exists():
    """Verify the validation scripts directory exists."""
    assert (REPO_ROOT / "scripts").is_dir(), "scripts/ directory must exist"


def test_tests_directory_exists():
    """Verify the tests directory exists."""
    assert (REPO_ROOT / "tests").is_dir(), "tests/ directory must exist"


@pytest.mark.skip(reason=PLANNED_REASON)
def test_planned_resource_directories_exist():
    """Planned folders only — skipped until the content ships."""
    for folder in PLANNED_FOLDERS:
        assert (REPO_ROOT / folder).is_dir(), f"{folder}/ directory must exist"


@pytest.mark.skip(reason=PLANNED_REASON)
def test_at_least_one_example():
    """Planned examples only — skipped until examples/ ships."""
    examples_dir = REPO_ROOT / "examples"
    examples = [d for d in examples_dir.iterdir() if d.is_dir()]
    assert len(examples) > 0, "Must have at least one example"


def test_readme_exists():
    """Verify README.md exists."""
    assert (REPO_ROOT / "README.md").is_file(), "README.md must exist"


def test_license_exists():
    """Verify LICENSE file exists."""
    assert (REPO_ROOT / "LICENSE").is_file(), "LICENSE must exist"


def test_readme_has_content():
    """Verify README has meaningful content."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert len(readme) > 100, "README must have substantial content"
    assert "QGIS" in readme or "qgis" in readme.lower(), "README should mention QGIS"
