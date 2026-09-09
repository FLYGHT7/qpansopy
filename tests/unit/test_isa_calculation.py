# -*- coding: utf-8 -*-
"""Regression tests for the shared ISA calculation used by issue #226."""
import importlib
import sys
import types

import pytest


def _isa_module():
    return importlib.import_module('Q_Pansopy.modules.isa')


@pytest.mark.parametrize(
    'elevation,unit,temperature,expected_isa,expected_delta',
    [
        (0, 'ft', 15, 15.0, 0.0),
        (0, 'ft', 25, 15.0, 10.0),
        (1000, 'ft', 20, 13.02, 6.98),
        (92.5, 'ft', 20, 14.81685, 5.18315),
        (1000, 'm', 14, 8.5039368, 5.4960632),
    ],
)
def test_calculate_isa_variation(
        elevation, unit, temperature, expected_isa, expected_delta):
    result = _isa_module().calculate_isa_variation(
        elevation, unit, temperature)

    assert result['method'] == 'calculated'
    assert result['elevation_original'] == elevation
    assert result['elevation_unit'] == unit
    assert result['temperature_reference'] == temperature
    assert result['isa_temperature'] == pytest.approx(expected_isa)
    assert result['isa_variation_calculated'] == pytest.approx(expected_delta)


def test_calculate_isa_variation_rejects_unknown_unit():
    with pytest.raises(ValueError, match='Unsupported elevation unit'):
        _isa_module().calculate_isa_variation(1000, 'yards', 15)


@pytest.fixture
def isa_dialog_module(monkeypatch):
    """Import the ISA dialog with small Qt compatibility stand-ins."""
    module_name = 'Q_Pansopy.isa_calculator_dialog'

    class _QtStandIn:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        sys.modules['qgis.PyQt.QtCore'],
        'QRegularExpression',
        _QtStandIn,
        raising=False,
    )
    monkeypatch.setattr(
        sys.modules['qgis.PyQt.QtGui'],
        'QRegularExpressionValidator',
        _QtStandIn,
        raising=False,
    )
    qt_compat = types.ModuleType('Q_Pansopy.qt_compat')
    qt_compat.Qt_AlignRight = 1
    qt_compat.Qt_AlignVCenter = 2

    base_module = types.ModuleType('Q_Pansopy.dockwidgets.base_dockwidget')
    base_module.load_base_qss = lambda: ''

    monkeypatch.setitem(sys.modules, 'Q_Pansopy.qt_compat', qt_compat)
    monkeypatch.setitem(
        sys.modules, 'Q_Pansopy.dockwidgets.base_dockwidget', base_module)
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    yield module
    sys.modules.pop(module_name, None)


def test_dialog_applies_and_locks_fixed_elevation(isa_dialog_module):
    calls = {}

    class _ElevationEdit:
        def setText(self, value):
            calls['elevation'] = value

        def setReadOnly(self, value):
            calls['read_only'] = value

        def setToolTip(self, value):
            calls['elevation_tooltip'] = value

    class _UnitCombo:
        def setCurrentText(self, value):
            calls['unit'] = value

        def setEnabled(self, value):
            calls['unit_enabled'] = value

        def setToolTip(self, value):
            calls['unit_tooltip'] = value

    dialog = types.SimpleNamespace(
        elevation_edit=_ElevationEdit(), elevation_unit_combo=_UnitCombo())

    isa_dialog_module.ISACalculatorDialog._apply_fixed_elevation(
        dialog, 1234.5, 'ft')

    assert calls['elevation'] == '1234.5'
    assert calls['unit'] == 'ft'
    assert calls['read_only'] is True
    assert calls['unit_enabled'] is False
    assert 'Circling' in calls['elevation_tooltip']
    assert 'Circling' in calls['unit_tooltip']


def test_dialog_rejects_unknown_fixed_elevation_unit(isa_dialog_module):
    dialog = types.SimpleNamespace()

    with pytest.raises(ValueError, match='Unsupported elevation unit'):
        isa_dialog_module.ISACalculatorDialog._apply_fixed_elevation(
            dialog, 1000, 'yards')


def test_dialog_calculation_uses_fixed_values_in_metadata(isa_dialog_module):
    accepted = []

    class _TextControl:
        def __init__(self, value):
            self._value = value

        def text(self):
            return self._value

    class _UnitControl:
        @staticmethod
        def currentText():
            return 'm'

    dialog = types.SimpleNamespace(
        elevation_edit=_TextControl('1000'),
        temperature_edit=_TextControl('14'),
        elevation_unit_combo=_UnitControl(),
        isa_variation=None,
        calculation_metadata={},
        accept=lambda: accepted.append(True),
    )

    isa_dialog_module.ISACalculatorDialog.calculate_isa(dialog)

    assert accepted == [True]
    assert dialog.isa_variation == pytest.approx(5.4960632)
    assert dialog.calculation_metadata['elevation_original'] == 1000
    assert dialog.calculation_metadata['elevation_unit'] == 'm'
    assert dialog.calculation_metadata['temperature_reference'] == 14
