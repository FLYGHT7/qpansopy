# -*- coding: utf-8 -*-
"""Regression tests for issue #224's complete Circling results table."""
import importlib
import pathlib
import sys
import types

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
    assert 'background-color:#000000' in html
    assert html.count('<th') == 6
    assert html.count('width:35%') == 1
    assert html.count('width:13%') == 5
    assert '<b style="color:#000000">Bank Angle [°]</b>' in html
    assert (
        '<b style="color:#000000">Circling Radius = 2r + S [NM]</b>'
        in html
    )
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


def test_show_table_copy_action_uses_complete_matrix(
        monkeypatch, dockwidget_module):
    """The inspector's Copy to Word action must not copy one table per CAT."""
    dock_mod = dockwidget_module
    inspector_mod = importlib.import_module(
        'Q_Pansopy.parameters_inspector_dialog')
    captured = {}

    def _capture_popup(title, sections, table_content=None):
        captured['title'] = title
        captured['sections'] = sections
        captured['table_content'] = table_content

    class _FakeDock:
        last_summary = _summary()
        last_params = _params()

        @staticmethod
        def log(message):
            captured['log'] = message

    monkeypatch.setattr(inspector_mod, 'show_web_popup', _capture_popup)

    dock_mod.QPANSOPYCirclingDockWidget.show_parameters_table(_FakeDock())

    content = captured['table_content']
    assert content is not None
    assert content.html.count('<table') == 1
    assert content.html.count('<th') == 6
    assert content.text.startswith(
        'Parameters\tCAT A\tCAT B\tCAT C\tCAT D\tCAT E')
    # Custom content replaces the generic per-category cards in the popup.
    assert captured['sections'] == []


def test_show_table_requires_complete_calculation_snapshot(
        monkeypatch, dockwidget_module):
    """A partial cached result must not open a popup or raise unexpectedly."""
    dock_mod = dockwidget_module
    inspector_mod = importlib.import_module(
        'Q_Pansopy.parameters_inspector_dialog')
    messages = []

    class _FakeDock:
        last_summary = _summary()
        last_params = None

        @staticmethod
        def log(message):
            messages.append(message)

    monkeypatch.setattr(
        inspector_mod,
        'show_web_popup',
        lambda *args, **kwargs: pytest.fail('popup must not be opened'),
    )

    dock_mod.QPANSOPYCirclingDockWidget.show_parameters_table(_FakeDock())

    assert messages == ['Error: No calculation available to show']


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
