# QGIS Resources

QGIS resources for GIS analysts. What ships today is a QField field-data-collection guide, plus the validation scripts and tests that check this repository.

## What ships

- [QField field-data-collection guide](https://github.com/ZQM-Computing/qgis-resources/blob/main/qfield/README.md) — offline GeoPackage packaging, form configuration, a pre-flight checklist, and failure modes. It lives in `qfield/` at the repository root.
- [Validation scripts](https://github.com/ZQM-Computing/qgis-resources/tree/main/scripts) — documentation and link checks (`check_docs.py`), run by CI.
- [Tests](https://github.com/ZQM-Computing/qgis-resources/tree/main/tests) — validation tests for the shipped resources (`test_expressions.py`).

## Planned, not yet shipped

The following are planned and do **not** exist in the repository yet, so they are listed here as plain text, not links: `expressions/`, `pyqgis/`, `processing/`, `styles/`, and `examples/`. Do not link to them until the content lands. See the main [README](https://github.com/ZQM-Computing/qgis-resources/blob/main/README.md) for the same statement.

## Contributing

Issues and pull requests are welcome — especially resources you have used in production and can document honestly: what it does, the QGIS version, the layer/field assumptions, and any sharp edges. See [CONTRIBUTING.md](https://github.com/ZQM-Computing/qgis-resources/blob/main/CONTRIBUTING.md).

## License

MIT — see [LICENSE](https://github.com/ZQM-Computing/qgis-resources/blob/main/LICENSE).
