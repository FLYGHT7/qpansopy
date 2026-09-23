"""Lifecycle tests for QPANSOPY live rubber-band previews."""
import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest


def _load_preview_docks(monkeypatch):
    """Import preview docks with the lightweight QGIS stubs from conftest."""
    gui = sys.modules['qgis.gui']
    monkeypatch.setattr(gui, 'QgsRubberBand', type('QgsRubberBand', (), {}), raising=False)
    core = sys.modules['qgis.core']
    dummy_qgis_type = type('QgisType', (), {})
    for name in (
        'QgsDistanceArea', 'QgsProject', 'QgsCoordinateTransform', 'QgsGeometry',
        'QgsPoint', 'QgsPolygon', 'QgsLineString',
    ):
        monkeypatch.setattr(core, name, dummy_qgis_type, raising=False)
    qt_core = sys.modules['qgis.PyQt.QtCore']
    qt_gui = sys.modules['qgis.PyQt.QtGui']
    uic = sys.modules['qgis.PyQt.uic']
    monkeypatch.setattr(
        qt_core, 'QRegularExpression', type('QRegularExpression', (), {}), raising=False
    )
    monkeypatch.setattr(
        qt_gui,
        'QRegularExpressionValidator',
        type('QRegularExpressionValidator', (), {}),
        raising=False,
    )
    monkeypatch.setattr(
        uic,
        'loadUiType',
        lambda *args: (type('FormClass', (), {}), None),
    )

    qt_compat = types.ModuleType('Q_Pansopy.qt_compat')
    qt_compat.MLPM_PointLayer = object()
    qt_compat.MLPM_LineLayer = object()
    qt_compat.preseed_active_layer = lambda *args: None
    qt_compat.Qgis_GeomType_Point = 0
    qt_compat.Qgis_GeomType_Line = 1
    qt_compat.Qgis_GeomType_Polygon = 2
    qt_compat.DOCK_FEATURES_DEFAULT = 0
    qt_compat.Qt_ALLOWED_DOCK_AREAS = 0
    qt_compat.Qt_AlignLeft = 0
    qt_compat.Qt_AlignRight = 0
    qt_compat.Qt_AlignVCenter = 0
    monkeypatch.setitem(sys.modules, 'Q_Pansopy.qt_compat', qt_compat)

    tolerance = types.ModuleType('Q_Pansopy.modules.conv.dme_tolerance')
    tolerance.build_tolerance_geometry = MagicMock()
    monkeypatch.setitem(sys.modules, 'Q_Pansopy.modules.conv.dme_tolerance', tolerance)

    modules = (
        'Q_Pansopy.dockwidgets.conv.qpansopy_dme_tolerance_dockwidget',
        'Q_Pansopy.dockwidgets.departures.qpansopy_omnidirectional_dockwidget',
        'Q_Pansopy.dockwidgets.utilities.qpansopy_wind_spiral_dockwidget',
    )
    loaded = []
    for name in modules:
        sys.modules.pop(name, None)
        loaded.append(importlib.import_module(name))
    return loaded


@pytest.fixture
def preview_docks(monkeypatch):
    return _load_preview_docks(monkeypatch)


def _dock_class(module):
    return next(
        value for value in module.__dict__.values()
        if isinstance(value, type) and value.__module__ == module.__name__
    )


@pytest.mark.parametrize('dock_index,clear_method,update_method', [
    (0, '_clear_preview', '_update_preview'),
    (1, '_clear_der_marker', '_update_der_marker'),
    (2, '_clear_preview', '_update_preview'),
])
def test_visibility_change_clears_on_hide_and_refreshes_on_show(
    preview_docks, dock_index, clear_method, update_method
):
    dock_class = _dock_class(preview_docks[dock_index])
    dock = object.__new__(dock_class)
    setattr(dock, clear_method, MagicMock())
    setattr(dock, update_method, MagicMock())

    dock_class._on_visibility_changed(dock, False)
    getattr(dock, clear_method).assert_called_once_with()
    getattr(dock, update_method).assert_not_called()

    dock_class._on_visibility_changed(dock, True)
    getattr(dock, update_method).assert_called_once_with()


@pytest.mark.parametrize('dock_index,update_method,band_name,geometry_type', [
    (0, '_update_preview', '_preview_band', 2),
    (1, '_update_der_marker', '_der_marker_band', 2),
    (2, '_update_preview', '_preview_band', 1),
])
def test_hidden_dock_updates_clear_rubberband_without_recomputing(
    preview_docks, dock_index, update_method, band_name, geometry_type
):
    dock_class = _dock_class(preview_docks[dock_index])
    dock = object.__new__(dock_class)
    band = MagicMock()
    setattr(dock, band_name, band)
    if dock_index == 1:
        dock._der_line_band = MagicMock()
        dock.runwayLayerComboBox = MagicMock()
    elif dock_index == 0:
        dock.pointLayerComboBox = MagicMock()
        dock.fixLayerComboBox = MagicMock()
    else:
        dock.pointLayerComboBox = MagicMock()
        dock.referenceLayerComboBox = MagicMock()
    dock.isVisible = MagicMock(return_value=False)

    getattr(dock_class, update_method)(dock)

    if dock_index == 1:
        band.reset.assert_called_once_with(geometry_type)
        dock._der_line_band.reset.assert_called_once_with(1)
    else:
        band.reset.assert_called_once_with(geometry_type)
    dock.isVisible.assert_called_once_with()
    for combo_name in (
        'pointLayerComboBox', 'fixLayerComboBox', 'runwayLayerComboBox',
        'referenceLayerComboBox',
    ):
        combo = getattr(dock, combo_name, None)
        if combo is not None:
            combo.currentLayer.assert_not_called()
