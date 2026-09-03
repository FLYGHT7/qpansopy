# -*- coding: utf-8 -*-
"""Regression tests for issue #224's complete Circling results table."""
import importlib
import pathlib
import sys
import types
import xml.etree.ElementTree as ElementTree  # nosec B405 - trusted local UI

import pytest


def _circling_module():
    return importlib.import_module('Q_Pansopy.modules.utilities.circling')


@pytest.fixture
def dockwidget_module(monkeypatch):
    """Import the dockwidget without pulling the full qt_compat widget set."""
    module_name = 'Q_Pansopy.dockwidgets.utilities.qpansopy_circling_dockwidget'
    qt_compat = types.ModuleType('Q_Pansopy.qt_compat')
    qt_compat.MLPM_PointLayer = object()
    qt_compat.Qgis_GeomType_Point = object()
    qt_compat.preseed_active_layer = lambda *args, **kwargs: None

    class _Form:
        pass

    uic = sys.modules['qgis.PyQt.uic']
    monkeypatch.setattr(uic, 'loadUiType', lambda *args, **kwargs: (_Form, None))
    monkeypatch.setitem(sys.modules, 'Q_Pansopy.qt_compat', qt_compat)
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    yield module
    sys.modules.pop(module_name, None)


def _summary(categories=('A', 'B', 'C', 'D', 'E')):
    mod = _circling_module()
    defaults = mod.IAS_DEFAULTS
    return {
        cat: mod.calc_circling_category(
            defaults[cat], 1000, 28, 20, 15, mod.S_CONST[cat])
        for cat in categories
    }


def _params():
    return {
        'bank_deg': 20,
        'delta_isa': 15,
        'prot_height_ft': 1000,
    }


def test_complete_table_matches_web_layout_and_precision():
    mod = _circling_module()

    html, text = mod.format_circling_complete_table(_summary(), _params())

    assert '<th' in html
    assert 'background:#0c2240' in html
    assert html.count('<th') == 6
    assert '<b>Bank Angle [°]</b>' in html
    assert '<b>Circling Radius = 2r + S [NM]</b>' in html
    assert 'Parameters\tCAT A\tCAT B\tCAT C\tCAT D\tCAT E' in text
    assert text.splitlines() == [
        'Parameters\tCAT A\tCAT B\tCAT C\tCAT D\tCAT E',
        'Bank Angle [°]\t20.0\t20.0\t20.0\t20.0\t20.0',
        'ΔT ISA [°C]\t15.0\t15.0\t15.0\t15.0\t15.0',
        'IAS [KT]\t100\t135\t180\t205\t240',
        'Protected Height [ft AGL]\t1000\t1000\t1000\t1000\t1000',
        'Altitude (h1) [ft]\t1028.0000\t1028.0000\t1028.0000\t1028.0000\t1028.0000',
        'K Factor\t1.0415\t1.0415\t1.0415\t1.0415\t1.0415',
        'TAS + 25KT\t129.1481\t165.6000\t212.4666\t238.5037\t274.9555',
        'Rate of Turn (R) calculated [°/s]\t3.0792\t2.4014\t1.8717\t1.6673\t1.4463',
        'Rate of Turn (R) used [°/s]\t3.0000\t2.4014\t1.8717\t1.6673\t1.4463',
        'Nominal Radius (r) [NM]\t0.6852\t1.0975\t1.8067\t2.2766\t3.0257',
        'Straight Segment (S) [NM]\t0.3\t0.4\t0.5\t0.6\t0.7',
        'Circling Radius = 2r + S [NM]\t1.6703\t2.5951\t4.1134\t5.1532\t6.7514',
    ]


def test_complete_table_keeps_disabled_category_columns_with_dashes():
    mod = _circling_module()

    html, text = mod.format_circling_complete_table(
        _summary(categories=('A', 'C')), _params())

    assert 'CAT B' in html
    assert 'CAT E' in html
    for row in text.splitlines()[1:]:
        cells = row.split('\t')
        assert len(cells) == 6
        assert cells[2] == '—'
        assert cells[4] == '—'
        assert cells[5] == '—'


def test_complete_table_uses_each_category_protected_height():
    mod = _circling_module()
    heights = {'A': 900, 'B': 1000, 'C': 1100, 'D': 1200, 'E': 1300}
    summary = {
        cat: mod.calc_circling_category(
            mod.IAS_DEFAULTS[cat], heights[cat], 28, 20, 15,
            mod.S_CONST[cat])
        for cat in mod.CATEGORIES
    }

    _, text = mod.format_circling_complete_table(summary, _params())
    rows = {row.split('\t', 1)[0]: row.split('\t')[1:]
            for row in text.splitlines()[1:]}

    assert rows['Protected Height [ft AGL]'] == [
        '900', '1000', '1100', '1200', '1300']
    assert rows['Altitude (h1) [ft]'] == [
        '928.0000', '1028.0000', '1128.0000', '1228.0000', '1328.0000']


def test_complete_table_supports_legacy_summary_height():
    mod = _circling_module()
    summary = _summary(categories=('A',))
    del summary['A']['protected_height_ft']

    _, text = mod.format_circling_complete_table(summary, _params())
    height_row = next(
        row for row in text.splitlines()
        if row.startswith('Protected Height [ft AGL]'))

    assert height_row.split('\t')[1:] == ['1000', '—', '—', '—', '—']


def test_complete_table_rejects_incomplete_calculation_data():
    mod = _circling_module()
    incomplete = {'A': {'ias_kt': 100}}

    with pytest.raises(
            ValueError, match='Cannot format Circling table value for h1_ft'):
        mod.format_circling_complete_table(incomplete, _params())


def test_circling_ui_declares_complete_table_button():
    ui_path = (
        pathlib.Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/qpansopy_circling_dockwidget.ui'
    )

    ui_text = ui_path.read_text(encoding='utf-8')

    assert 'name="copyCompleteTableButton"' in ui_text
    assert '<string>Copy Complete Table</string>' in ui_text


def test_circling_ui_declares_speed_and_height_per_category():
    ui_path = (
        pathlib.Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/qpansopy_circling_dockwidget.ui'
    )

    root = ElementTree.fromstring(  # nosec B314 - trusted repository file
        ui_path.read_text(encoding='utf-8'))
    widgets = {widget.attrib['name']: widget for widget in root.iter('widget')}
    layouts = {layout.attrib['name']: layout for layout in root.iter('layout')}

    assert 'protHeightSpinBox' not in widgets
    assert layouts['categoryGridLayout'].find(
        "property[@name='columnStretch']") is None
    assert widgets['iasHeaderLabel'].find("property[@name='text']/string").text == (
        'Speed (kt)')
    assert widgets['heightHeaderLabel'].find(
        "property[@name='text']/string").text == 'Height (ft AGL)'

    for cat in 'ABCDE':
        widget = widgets['protHeight{0}SpinBox'.format(cat)]
        assert float(widget.find("property[@name='minimum']/double").text) == 0
        assert float(widget.find("property[@name='maximum']/double").text) == 5000
        assert float(widget.find("property[@name='value']/double").text) == 1000


def test_category_grid_stretch_uses_integer_columns(dockwidget_module):
    dock_mod = dockwidget_module
    calls = []

    class _GridLayout:
        @staticmethod
        def setColumnStretch(column, stretch):
            calls.append((column, stretch))

    class _FakeDock:
        categoryGridLayout = _GridLayout()

    dock_mod.QPANSOPYCirclingDockWidget._configure_category_grid(_FakeDock())

    assert calls == [(1, 1), (2, 1)]
    assert all(isinstance(value, int) for call in calls for value in call)


def test_category_inputs_collect_aligned_values_for_enabled_categories(
        dockwidget_module):
    dock_mod = dockwidget_module

    class _CheckBox:
        def __init__(self, checked):
            self._checked = checked

        def isChecked(self):
            return self._checked

    class _SpinBox:
        def __init__(self, value):
            self._value = value

        def value(self):
            return self._value

    class _FakeDock:
        pass

    dock = _FakeDock()
    enabled = {'A': True, 'B': False, 'C': True, 'D': False, 'E': True}
    speeds = {'A': 100, 'B': 135, 'C': 180, 'D': 205, 'E': 240}
    heights = {'A': 900, 'B': 1000, 'C': 1100, 'D': 1200, 'E': 1300}
    for cat in 'ABCDE':
        setattr(dock, 'cat{0}CheckBox'.format(cat), _CheckBox(enabled[cat]))
        setattr(dock, 'ias{0}SpinBox'.format(cat), _SpinBox(speeds[cat]))
        setattr(
            dock, 'protHeight{0}SpinBox'.format(cat), _SpinBox(heights[cat]))

    ias_by_cat, height_by_cat = (
        dock_mod.QPANSOPYCirclingDockWidget._category_inputs(dock))

    assert ias_by_cat == {'A': 100, 'C': 180, 'E': 240}
    assert height_by_cat == {'A': 900, 'C': 1100, 'E': 1300}


def test_calculate_passes_category_heights_to_engine(
        monkeypatch, dockwidget_module):
    dock_mod = dockwidget_module
    circling_mod = _circling_module()
    captured = {}

    class _ValueControl:
        def __init__(self, value):
            self._value = value

        def value(self):
            return self._value

        def currentText(self):
            return self._value

        def isChecked(self):
            return self._value

        def text(self):
            return self._value

    class _Layer:
        @staticmethod
        def selectedFeatureCount():
            return 2

    class _LayerControl:
        @staticmethod
        def currentLayer():
            return _Layer()

    def _run_circling(iface, layer, params):
        captured['params'] = params
        return {'summary': {}, 'kml_path': None}

    class _FakeDock:
        thresholdLayerComboBox = _LayerControl()
        elevSpinBox = _ValueControl(28)
        elevUnitCombo = _ValueControl('ft')
        bankSpinBox = _ValueControl(20)
        isaSpinBox = _ValueControl(15)
        exportKmlCheckBox = _ValueControl(False)
        outputFolderLineEdit = _ValueControl('test-output')
        iface = object()

        @staticmethod
        def _category_inputs():
            return ({'A': 100, 'C': 180}, {'A': 900, 'C': 1300})

        @staticmethod
        def log(message):
            captured.setdefault('logs', []).append(message)

        @staticmethod
        def _log_summary(summary):
            captured['summary'] = summary

    monkeypatch.setattr(circling_mod, 'run_circling', _run_circling)
    dock = _FakeDock()

    dock_mod.QPANSOPYCirclingDockWidget.calculate(dock)

    assert captured['params']['ias_by_cat'] == {'A': 100, 'C': 180}
    assert captured['params']['prot_height_ft_by_cat'] == {
        'A': 900, 'C': 1300}
    assert 'prot_height_ft' not in captured['params']
    assert dock.last_params == {'bank_deg': 20, 'delta_isa': 15}


def test_copy_complete_table_sets_html_and_plain_text(
        monkeypatch, dockwidget_module):
    dock_mod = dockwidget_module
    captured = {}

    class _FakeMimeData:
        def setHtml(self, value):
            captured['html'] = value

        def setText(self, value):
            captured['text'] = value

    class _FakeClipboard:
        def setMimeData(self, mime):
            captured['mime'] = mime

    class _FakeApplication:
        @staticmethod
        def clipboard():
            return _FakeClipboard()

    class _FakeMessageBar:
        def pushMessage(self, *args, **kwargs):
            captured['message'] = (args, kwargs)

    class _FakeIface:
        @staticmethod
        def messageBar():
            return _FakeMessageBar()

    class _FakeDock:
        last_summary = _summary()
        last_params = _params()
        iface = _FakeIface()

        @staticmethod
        def log(message):
            captured['log'] = message

    monkeypatch.setattr(dock_mod, 'QMimeData', _FakeMimeData)
    monkeypatch.setattr(dock_mod.QtWidgets, 'QApplication', _FakeApplication)

    dock_mod.QPANSOPYCirclingDockWidget.copy_complete_table(_FakeDock())

    assert '<table' in captured['html']
    assert captured['text'].startswith('Parameters\tCAT A')
    assert captured['mime'] is not None
    assert captured['log'] == 'Complete Circling table copied to clipboard for Word.'
    assert captured['message'][0][1] == 'Complete Circling table copied to clipboard'


def test_copy_complete_table_requires_a_successful_calculation(
        monkeypatch, dockwidget_module):
    dock_mod = dockwidget_module
    messages = []

    class _ForbiddenApplication:
        @staticmethod
        def clipboard():
            raise AssertionError('clipboard must not be accessed')

    class _FakeDock:
        last_summary = None
        last_params = None

        @staticmethod
        def log(message):
            messages.append(message)

    monkeypatch.setattr(dock_mod.QtWidgets, 'QApplication', _ForbiddenApplication)

    dock_mod.QPANSOPYCirclingDockWidget.copy_complete_table(_FakeDock())

    assert messages == ['Error: No calculation available to copy']


def test_copy_complete_table_reports_clipboard_failure(
        monkeypatch, dockwidget_module):
    dock_mod = dockwidget_module
    messages = []

    class _FailingMimeData:
        def setHtml(self, value):
            raise RuntimeError('clipboard unavailable')

    class _FakeDock:
        last_summary = _summary()
        last_params = _params()

        @staticmethod
        def log(message):
            messages.append(message)

    monkeypatch.setattr(dock_mod, 'QMimeData', _FailingMimeData)

    dock_mod.QPANSOPYCirclingDockWidget.copy_complete_table(_FakeDock())

    assert messages == [
        'Error copying complete Circling table: clipboard unavailable']
