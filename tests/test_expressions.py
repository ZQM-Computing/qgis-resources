"""
Tests for QGIS resources repository structure and content.
"""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_expressions_directory_exists():
    """Verify the expressions directory exists."""
    assert (REPO_ROOT / "examples").is_dir(), "expressions/ directory must exist"


def test_processing_directory_exists():
    """Verify the processing directory exists."""
    assert (REPO_ROOT / "processing").is_dir(), "processing/ directory must exist"


def test_styles_directory_exists():
    """Verify the styles directory exists."""
    assert (REPO_ROOT / "styles").is_dir(), "styles/ directory must exist"


def test_examples_directory_exists():
    """Verify the examples directory exists."""
    assert (REPO_ROOT / "examples").is_dir(), "examples/ directory must exist"


def test_readme_exists():
    """Verify README.md exists."""
    assert (REPO_ROOT / "README.md").is_file(), "README.md must exist"


def test_license_exists():
    """Verify LICENSE file exists."""
    assert (REPO_ROOT / "LICENSE").is_file(), "LICENSE must exist"


def test_at_least_one_example():
    """Verify at least one example directory exists."""
    examples_dir = REPO_ROOT / "examples"
    examples = [d for d in examples_dir.iterdir() if d.is_dir()]
    assert len(examples) > 0, "Must have at least one example"


def test_readme_has_content():
    """Verify README has meaningful content."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert len(readme) > 100, "README must have substantial content"
    assert "QGIS" in readme or "qgis" in readme.lower(), "README should mention QGIS"
