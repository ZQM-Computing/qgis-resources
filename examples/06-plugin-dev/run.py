"""Validate the plugin lifecycle contract without pretending to run QGIS UI."""
from pathlib import Path
import ast


def main():
    source = Path(__file__).parents[2] / "patterns" / "06_plugin_development.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    plugin = next((node for node in module.body
                   if isinstance(node, ast.ClassDef) and node.name == "MyPlugin"), None)
    if plugin is None:
        raise SystemExit("MyPlugin class not found")
    methods = {node.name for node in plugin.body if isinstance(node, ast.FunctionDef)}
    required = {"__init__", "initGui", "run", "unload"}
    missing = required - methods
    if missing:
        raise SystemExit(f"MyPlugin is missing lifecycle methods: {sorted(missing)}")
    print("Plugin lifecycle contract found. Load the plugin in QGIS to validate UI integration.")


if __name__ == "__main__":
    main()
