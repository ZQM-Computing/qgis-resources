"""Verify CRS text is rejected before crossing the native parser boundary."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from screening_spatial import ScreeningError, _collect_polygons, _spatial_reference

UNSUPPORTED = (
    "/tmp/untrusted-crs", "file:///tmp/untrusted-crs",
    "https://example.invalid/crs", "EPSG:4326\n", "EPSG:3857",
    'GEOGCS["WGS 84"]', "urn:ogc:def:crs:EPSG::4326",
)


@pytest.mark.parametrize("text", UNSUPPORTED)
def test_rejects_crs_before_native_construction(text):
    """File paths, URLs and unsupported representations never reach GDAL."""
    osr = SimpleNamespace(SpatialReference=Mock())
    with pytest.raises(ScreeningError, match="Unsupported pilot"):
        _spatial_reference(osr, text)
    osr.SpatialReference.assert_not_called()


@pytest.mark.parametrize("text", UNSUPPORTED)
def test_fixture_rejects_crs_before_native_read(tmp_path, text):
    """Metadata rejection precedes both CRS construction and OGR file open."""
    path = tmp_path / "input.geojson"
    path.write_text(json.dumps({"crs": {"properties": {"name": text}}}))
    osr = SimpleNamespace(SpatialReference=Mock())
    ogr = SimpleNamespace(Open=Mock())
    with pytest.raises(ScreeningError, match="Unsupported pilot"):
        _collect_polygons(path, object(), object(), ogr, osr)
    osr.SpatialReference.assert_not_called()
    ogr.Open.assert_not_called()


@pytest.mark.parametrize("text, code", [("EPSG:4326", 4326), ("EPSG:6933", 6933)])
def test_supported_crs_uses_only_fixed_epsg_codes(text, code):
    """The supported CRS path uses authority lookup and GIS axis order."""
    srs = Mock()
    srs.ImportFromEPSG.return_value = 0
    osr = SimpleNamespace(SpatialReference=Mock(return_value=srs),
                          OAMS_TRADITIONAL_GIS_ORDER=0)
    assert _spatial_reference(osr, text) is srs
    srs.ImportFromEPSG.assert_called_once_with(code)
    srs.SetAxisMappingStrategy.assert_called_once_with(0)
    srs.SetFromUserInput.assert_not_called()
