"""Initial SID integration with the shared ISA calculator dialog."""
import importlib
import sys
import types

import pytest


@pytest.fixture
def sid_dock_module(monkeypatch):
    qt_compat = types.ModuleType('Q_Pansopy.qt_compat')
    qt_compat.DOCK_FEATURES_DEFAULT = 0
    qt_compat.MLPM_LineLayer = 0
    qt_compat.Qgis_GeomType_Line = 1
    qt_compat.Qt_ALLOWED_DOCK_AREAS = 0
    qt_compat.preseed_active_layer = lambda *args: None
    monkeypatch.setitem(sys.modules, 'Q_Pansopy.qt_compat', qt_compat)
    from qgis.PyQt import uic

    class _Form:
        pass

    monkeypatch.setattr(uic, 'loadUiType', lambda *args: (_Form, None))
    sys.modules.pop(
        'Q_Pansopy.dockwidgets.departures.'
        'qpansopy_sid_initial_dockwidget', None)
    module = importlib.import_module(
        'Q_Pansopy.dockwidgets.departures.'
        'qpansopy_sid_initial_dockwidget')
    return module


class _SpinBox:
    def __init__(self, value, minimum=-50, maximum=50):
        self._value = value
        self._minimum = minimum
        self._maximum = maximum

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = round(value, 4)

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum


def _dock(metadata=None):
    return types.SimpleNamespace(
        adElevSpinBox=_SpinBox(123.4),
        isaVarSpinBox=_SpinBox(3),
        reference_temp_c=15.0,
        isa_calculation_metadata=metadata or {'method': 'manual'},
        _isa_updating=False,
        log=lambda message: None,
    )


@pytest.mark.parametrize('accepted', [True, False])
def test_calculator_uses_current_ad_elevation_and_honors_cancel(
        monkeypatch, sid_dock_module, accepted):
    captured = {}

    class _Dialog:
        def __init__(self, parent, fixed_elevation,
                     fixed_elevation_unit, reference_temperature_c):
            captured.update(
                parent=parent,
                elevation=fixed_elevation,
                unit=fixed_elevation_unit,
                temperature=reference_temperature_c,
            )

        @staticmethod
        def exec():
            return accepted

        @staticmethod
        def get_isa_variation():
            return 5.18315

        @staticmethod
        def get_calculation_metadata():
            return {
                'method': 'calculated',
                'elevation_original': 123.4,
                'elevation_unit': 'm',
                'temperature_reference': 21,
                'isa_variation_calculated': 5.18315,
            }

    dialog_module = types.ModuleType('Q_Pansopy.isa_calculator_dialog')
    dialog_module.ISACalculatorDialog = _Dialog
    monkeypatch.setitem(
        sys.modules, 'Q_Pansopy.isa_calculator_dialog', dialog_module)

    dock = _dock()
    sid_dock_module.QPANSOPYSIDInitialDockWidget._calculate_isa(dock)

    assert captured == {
        'parent': dock,
        'elevation': 123.4,
        'unit': 'm',
        'temperature': 15.0,
    }
    if accepted:
        assert dock.isaVarSpinBox.value() == pytest.approx(5.1832)
        assert dock.reference_temp_c == 21
        assert dock.isa_calculation_metadata['method'] == 'calculated'
        assert dock._isa_updating is False
    else:
        assert dock.isaVarSpinBox.value() == 3
        assert dock.reference_temp_c == 15
        assert dock.isa_calculation_metadata == {'method': 'manual'}


def test_out_of_range_result_preserves_isa_and_temperature(
        monkeypatch, sid_dock_module):
    dialog_module = types.ModuleType('Q_Pansopy.isa_calculator_dialog')

    class _Dialog:
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def exec():
            return True

        @staticmethod
        def get_isa_variation():
            return 51

    dialog_module.ISACalculatorDialog = _Dialog
    monkeypatch.setitem(
        sys.modules, 'Q_Pansopy.isa_calculator_dialog', dialog_module)
    messages = []
    dock = _dock()
    dock.log = messages.append

    sid_dock_module.QPANSOPYSIDInitialDockWidget._calculate_isa(dock)

    assert dock.isaVarSpinBox.value() == 3
    assert dock.reference_temp_c == 15
    assert dock.isa_calculation_metadata == {'method': 'manual'}
    assert 'outside the allowed range' in messages[0]


def test_get_parameters_uses_stored_dialog_temperature(sid_dock_module):
    dock = _dock({'method': 'calculated'})
    dock.derElevSpinBox = _SpinBox(120)
    dock.pdgSpinBox = _SpinBox(3.3)
    dock.iasSpinBox = _SpinBox(205)
    dock.altitudeSpinBox = _SpinBox(5000)
    dock.bankAngleSpinBox = _SpinBox(15)
    dock.windSpinBox = _SpinBox(30)
    dock.pilotTimeSpinBox = _SpinBox(11)
    dock.direction_reversed = False

    params = sid_dock_module.QPANSOPYSIDInitialDockWidget.get_parameters(
        dock)

    assert params['reference_temp_c'] == 15
    assert params['isa_source'] == 'calculated'
    assert 'tempSpinBox' not in vars(dock)
