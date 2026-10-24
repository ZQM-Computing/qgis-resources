#!/usr/bin/env python3
"""Audit existing QGIS resources for empty implementations and missing safety contracts.

This complements syntax/docs tests: it checks the substance of pre-existing
Python examples, QML styles, and lesson notebooks without requiring QGIS.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(
    r"\b(TODO|FIXME|TBD|your code here|implementation pending|not implemented yet)\b",
    re.IGNORECASE,
)


def _function_is_empty(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    return len(body) == 1 and (
        isinstance(body[0], ast.Pass)
        or (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and body[0].value.value is Ellipsis)
        or (
            isinstance(body[0], ast.Raise)
            and isinstance(body[0].exc, ast.Call)
            and isinstance(body[0].exc.func, ast.Name)
            and body[0].exc.func.id == "NotImplementedError"
        )
    )


def audit_python() -> list[str]:
    issues = []
    paths = sorted(p for folder in ("patterns", "pyqgis", "examples", "scripts", "zqm_geospatial_tools")
                   for p in (ROOT / folder).rglob("*.py") if p.is_file())
    if not paths:
        return ["No Python resources found"]
    for path in paths:
        rel = path.relative_to(ROOT)
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(rel))
        except SyntaxError as exc:
            issues.append(f"{rel}: syntax error at line {exc.lineno}: {exc.msg}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _function_is_empty(node):
                issues.append(f"{rel}:{node.lineno}: empty implementation {node.name}()")
        # Attach parent links so we can distinguish executable literals from comments.
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent
        for node in ast.walk(tree):
            if path.resolve() == Path(__file__).resolve():
                break
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            parent = getattr(node, "parent", None)
            if isinstance(parent, ast.Expr) and isinstance(parent.value, ast.Constant) and parent.value is node:
                # Module/class/function docstrings are documentation, not executable placeholders.
                if isinstance(getattr(parent, "parent", None), (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
            if PLACEHOLDER.search(node.value):
                issues.append(f"{rel}: placeholder marker in string literal: {PLACEHOLDER.search(node.value).group(0)}")
    return issues


def audit_qml() -> list[str]:
    issues = []
    paths = sorted((ROOT / "styles").glob("*.qml"))
    if not paths:
        return ["styles/: no QML styles found"]
    for path in paths:
        rel = path.relative_to(ROOT)
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            issues.append(f"{rel}: malformed XML: {exc}")
            continue
        if root.tag != "qgis":
            issues.append(f"{rel}: expected <qgis> root, got <{root.tag}>")
        renderer = root.find("renderer-v2")
        if renderer is None:
            issues.append(f"{rel}: missing renderer-v2")
        elif renderer.get("type") not in {"singleSymbol", "categorizedSymbol", "graduatedSymbol", "RuleRenderer", "invertedPolygonRenderer", "pointDisplacement"}:
            issues.append(f"{rel}: unsupported or missing renderer type {renderer.get('type')!r}")
        symbols = root.findall(".//renderer-v2/symbols/symbol")
        if not symbols:
            issues.append(f"{rel}: renderer has no symbols")
        for symbol in symbols:
            if not symbol.findall("layer"):
                issues.append(f"{rel}: symbol {symbol.get('name')!r} has no symbol layer")
    return issues


def audit_notebooks() -> list[str]:
    issues = []
    paths = sorted((ROOT / "notebooks").glob("*.ipynb"))
    if not paths:
        return ["notebooks/: no notebooks found"]
    for path in paths:
        rel = path.relative_to(ROOT)
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(f"{rel}: invalid JSON: {exc}")
            continue
        if notebook.get("nbformat") != 4:
            issues.append(f"{rel}: expected notebook format 4")
        cells = notebook.get("cells", [])
        markdown = [c for c in cells if c.get("cell_type") == "markdown" and "".join(c.get("source", [])).strip()]
        code = [c for c in cells if c.get("cell_type") == "code" and "".join(c.get("source", [])).strip()]
        if not markdown:
            issues.append(f"{rel}: missing explanatory markdown")
        if not code:
            issues.append(f"{rel}: missing executable code")
        for index, cell in enumerate(cells):
            if cell.get("cell_type") == "code":
                if cell.get("execution_count") is not None or cell.get("outputs"):
                    issues.append(f"{rel}: code cell {index} commits execution state/output")
                source = "".join(cell.get("source", []))
                if source.strip():
                    try:
                        ast.parse(source, filename=f"{rel}:cell-{index}")
                    except SyntaxError as exc:
                        issues.append(f"{rel}: code cell {index} syntax error: {exc.msg}")
    return issues


def audit_existing_pyqgis_contracts() -> list[str]:
    """Assert that each existing console utility handles its primary failure mode."""
    contracts = {
        "pyqgis/add_basemaps.py": ("QgsRasterLayer", "isValid()", "addMapLayer"),
        "pyqgis/batch_export_to_geopackage.py": ("FileExistsError", "writeAsVectorFormatV3", "NoError", "exported"),
        "pyqgis/export_layout_pdf.py": ("layoutByName", "exportToPdf", "temporary.stat().st_size"),
        "patterns/01_vector_analysis.py": ("native:buffer", "native:dissolve", "area"),
        "patterns/02_raster_processing.py": ("gdal:warpreproject", "cliprasterbymasklayer", "target.isValid()"),
        "patterns/03_spatial_joins.py": ("native:joinattributesbylocation", "points.crs() != polygons.crs()"),
        "patterns/04_crs_transforms.py": ("native:reprojectlayer", "result.crs() != target"),
        "patterns/05_batch_processing.py": ("math.isfinite", "input_paths = sorted", "overwrite"),
        "patterns/06_plugin_development.py": ("initGui", "unload"),
        "patterns/clip_and_reproject.py": ("native:reprojectlayer", "isValid"),
    }
    issues = []
    for filename, markers in contracts.items():
        path = ROOT / filename
        if not path.is_file():
            issues.append(f"{filename}: required existing resource missing")
            continue
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in source:
                issues.append(f"{filename}: missing expected operational contract {marker!r}")
    return issues


def main() -> int:
    checks = (
        ("Python implementation audit", audit_python),
        ("QML style audit", audit_qml),
        ("Notebook audit", audit_notebooks),
        ("Existing-resource contracts", audit_existing_pyqgis_contracts),
    )
    issues = []
    for label, check in checks:
        found = check()
        if found:
            print(f"FAIL: {label}")
            for issue in found:
                print(f"  - {issue}")
            issues.extend(found)
        else:
            print(f"PASS: {label}")
    if issues:
        print(f"Resource audit failed with {len(issues)} issue(s).")
        return 1
    print("Resource audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
