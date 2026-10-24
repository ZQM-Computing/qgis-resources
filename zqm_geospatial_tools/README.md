# ZQM Geospatial Tools QGIS plugin

This plugin registers the **ZQM Geospatial Tools** Processing provider and the **Batch buffer selected layers** algorithm.

## Install for local testing

1. Copy the complete `zqm_geospatial_tools/` directory into your QGIS profile's Python plugins directory.
2. Restart QGIS or refresh the plugin list.
3. Enable **ZQM Geospatial Tools** in Plugins → Manage and Install Plugins → Installed.
4. Open Processing Toolbox and search for **ZQM — Batch buffer selected layers**.

For development, the directory can be symlinked into the active profile's plugins directory where the operating system supports it. Do not copy only one Python file: the plugin entry point and provider are required for registration.

## Batch buffer behavior

- Accepts one or more spatial vector layers.
- Writes one GeoPackage per layer.
- All selected layers must share a valid CRS; mixed-CRS batches are rejected instead of being processed with inconsistent units. Distance uses that CRS's units. Geographic CRSs trigger a warning because distances are angular, not metres.
- Existing output files are preserved by default. Explicit overwrite writes to a temporary GeoPackage, validates it, then replaces the destination.
- Reports successes, skips, and failures separately.

## Validation boundary

Static CI can check Python syntax and repository contracts, but it cannot prove that the plugin loads in every QGIS build. Test installation, provider registration, cancellation, GeoPackage writing, and overwrite behavior in the target QGIS version before using production data. Keep a backup of source data and test outputs first.
