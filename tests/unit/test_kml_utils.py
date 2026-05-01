# -*- coding: utf-8 -*-
"""
Tests for fix_kml_altitude_mode() in utils.py.
Uses temporary files — no QGIS runtime needed beyond stubs.
"""
import importlib
import textwrap
from pathlib import Path

import pytest


def _utils():
    return importlib.import_module('Q_Pansopy.utils')


KML_CLAMP = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <Polygon>
            <altitudeMode>clampToGround</altitudeMode>
            <outerBoundaryIs>
              <LinearRing>
                <coordinates>0,0,0 1,0,100 1,1,100 0,0,0</coordinates>
              </LinearRing>
            </outerBoundaryIs>
          </Polygon>
        </Placemark>
      </Document>
    </kml>
""")

KML_NO_ALTITUDE = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <Polygon>
            <outerBoundaryIs>
              <LinearRing>
                <coordinates>0,0,0 1,0,100 1,1,100 0,0,0</coordinates>
              </LinearRing>
            </outerBoundaryIs>
          </Polygon>
        </Placemark>
      </Document>
    </kml>
""")


def test_fix_kml_changes_clamp_to_absolute(tmp_path: Path):
    """clampToGround → absolute."""
    kml = tmp_path / "test.kml"
    kml.write_text(KML_CLAMP, encoding="utf-8")

    result = _utils().fix_kml_altitude_mode(str(kml))

    assert result is True
    content = kml.read_text(encoding="utf-8")
    assert "absolute" in content
    assert "clampToGround" not in content


def test_fix_kml_adds_altitude_when_missing(tmp_path: Path):
    """When no altitudeMode exists, it should be added as absolute."""
    kml = tmp_path / "test.kml"
    kml.write_text(KML_NO_ALTITUDE, encoding="utf-8")

    result = _utils().fix_kml_altitude_mode(str(kml))

    assert result is True
    content = kml.read_text(encoding="utf-8")
    assert "absolute" in content


def test_fix_kml_returns_false_on_missing_file(tmp_path: Path):
    """Non-existent file → returns False without raising."""
    result = _utils().fix_kml_altitude_mode(str(tmp_path / "nonexistent.kml"))
    assert result is False


def test_fix_kml_idempotent(tmp_path: Path):
    """Running fix twice leaves the file valid and absolute."""
    kml = tmp_path / "test.kml"
    kml.write_text(KML_CLAMP, encoding="utf-8")

    _utils().fix_kml_altitude_mode(str(kml))
    result = _utils().fix_kml_altitude_mode(str(kml))

    assert result is True
    content = kml.read_text(encoding="utf-8")
    assert "absolute" in content
    assert "clampToGround" not in content


def test_fix_kml_relative_to_ground(tmp_path: Path):
    """relativeToGround should also be converted."""
    kml_text = KML_CLAMP.replace("clampToGround", "relativeToGround")
    kml = tmp_path / "test.kml"
    kml.write_text(kml_text, encoding="utf-8")

    _utils().fix_kml_altitude_mode(str(kml))

    content = kml.read_text(encoding="utf-8")
    assert "absolute" in content
    assert "relativeToGround" not in content
