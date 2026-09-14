import hashlib
import math
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ElementTree

import pytest


def _record(identifier, elevation, tolerance):
    from Q_Pansopy.modules.utilities.primary_area_assessment import SourceRecord

    return SourceRecord(
        identifier=identifier,
        layer_type='survey',
        obstacle_type='building',
        coordinates='500000.000, 1600000.000',
        elevation_m=elevation,
        tolerance_m=tolerance,
        geometry=None,
    )


def test_evaluation_uses_each_records_tolerance():
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    evaluated, controls = evaluate_records(
        [_record('A', 100.0, 3.0), _record('B', 98.0, 7.0)],
        moc_m=75.0,
    )

    assert [item.oca_m for item in evaluated] == [178.0, 180.0]
    assert evaluated[0].oca_ft == round(178.0 / 0.3048, 3)
    assert [item.identifier for item in controls] == ['B']


def test_override_replaces_tolerance_and_keeps_all_tied_controls():
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    evaluated, controls = evaluate_records(
        [_record('A', 100.0, 20.0), _record('B', 100.0, 3.0)],
        moc_m=0.0,
        override_tolerance_m=0.0,
    )

    assert [item.applied_tolerance_m for item in evaluated] == [0.0, 0.0]
    assert [item.identifier for item in controls] == ['A', 'B']


@pytest.mark.parametrize(
    'moc,override,message',
    [
        (-1.0, None, 'MOC'),
        (0.0, -1.0, 'override'),
        (math.inf, None, 'MOC'),
    ],
)
def test_evaluation_rejects_invalid_global_values(moc, override, message):
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    with pytest.raises(ValueError, match=message):
        evaluate_records(
            [_record('A', 100.0, 3.0)],
            moc_m=moc,
            override_tolerance_m=override,
        )


def test_evaluation_rejects_invalid_source_tolerance():
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    with pytest.raises(ValueError, match='tolerance'):
        evaluate_records([_record('A', 100.0, -0.1)], moc_m=75.0)


def test_empty_evaluation_has_no_control_obstacle():
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    assert evaluate_records([], moc_m=75.0) == ([], [])


def test_dockwidget_defaults_match_generic_assessment_contract():
    ui_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.ui'
    )
    root = ElementTree.parse(ui_path).getroot()

    def property_text(widget_name, property_name):
        widget = root.find(f".//widget[@name='{widget_name}']")
        prop = widget.find(f"./property[@name='{property_name}']")
        return list(prop)[0].text

    assert property_text('useSelectedAreaCheckBox', 'checked') == 'true'
    assert property_text('mocDoubleSpinBox', 'value') == '75.000000000000000'
    assert property_text(
        'terrainToleranceDoubleSpinBox', 'value'
    ) == '50.000000000000000'


def test_dockwidget_scrolls_all_assessment_controls():
    ui_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.ui'
    )
    root = ElementTree.parse(ui_path).getroot()
    scroll_area = root.find(".//widget[@name='scrollArea']")

    assert scroll_area is not None
    assert scroll_area.find(
        "./property[@name='widgetResizable']/bool"
    ).text == 'true'
    assert scroll_area.find(
        "./property[@name='horizontalScrollBarPolicy']/enum"
    ).text == 'Qt::ScrollBarAsNeeded'
    assert scroll_area.find(
        "./property[@name='verticalScrollBarPolicy']/enum"
    ).text == 'Qt::ScrollBarAsNeeded'
    assert scroll_area.find(".//widget[@name='calculateButton']") is not None
    assert scroll_area.find(".//widget[@name='logTextEdit']") is not None


def test_control_obstacle_style_matches_provided_qml():
    style_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/styles/control_obstacle_primary_style.qml'
    )

    assert hashlib.sha256(style_path.read_bytes()).hexdigest() == (
        'c0790eea5b4be976750e255df81bb1930e8cb1eedd1a90e8f796807df89798f8'
    )
    root = ElementTree.parse(style_path).getroot()
    renderer = root.find('./renderer-v2')
    assert renderer.get('type') == 'singleSymbol'
    assert renderer.find(".//layer[@class='GeometryGenerator']") is not None
    assert renderer.find(".//layer[@class='SvgMarker']") is not None
    label = root.find("./labeling/settings/text-style")
    assert label is not None
    assert all(
        field in label.get('fieldName')
        for field in ('layer_type', 'elev', 'oca_ft')
    )


class _StyleLayer:
    StyleCategory = SimpleNamespace(AllVisualStyleCategories='visual')

    def __init__(self, style_loaded=True):
        self.style_loaded = style_loaded
        self.load_calls = []
        self.repaint_count = 0
        self.symbols = []
        self._renderer = SimpleNamespace(setSymbol=self.symbols.append)

    def renderer(self):
        return self._renderer

    def loadNamedStyle(self, *args, **kwargs):
        self.load_calls.append((args, kwargs))
        return '', self.style_loaded

    def triggerRepaint(self):
        self.repaint_count += 1


class _LegacyStyleLayer(_StyleLayer):
    AllVisualStyleCategories = 'visual'

    @property
    def StyleCategory(self):
        raise AttributeError


def test_control_style_loads_visual_categories_only(monkeypatch):
    from Q_Pansopy.modules.utilities import primary_area_assessment as module

    monkeypatch.setattr(
        module,
        'QgsMarkerSymbol',
        SimpleNamespace(createSimple=lambda properties: properties),
    )

    assessment = _StyleLayer()
    control = _StyleLayer()

    module._style_results(assessment, control)

    assert len(assessment.symbols) == 1
    assert control.symbols == []
    assert control.load_calls[0][0][0].endswith(
        'styles/control_obstacle_primary_style.qml'
    )
    assert control.load_calls[0][1] == {'categories': 'visual'}
    assert control.repaint_count == 1


def test_control_style_falls_back_when_qml_cannot_load(monkeypatch):
    from Q_Pansopy.modules.utilities import primary_area_assessment as module

    monkeypatch.setattr(
        module,
        'QgsMarkerSymbol',
        SimpleNamespace(createSimple=lambda properties: properties),
    )

    assessment = _StyleLayer()
    control = _StyleLayer(style_loaded=False)

    module._style_results(assessment, control)

    assert len(control.symbols) == 1
    assert control.repaint_count == 1


def test_control_style_supports_unscoped_qgis3_category(monkeypatch):
    from Q_Pansopy.modules.utilities import primary_area_assessment as module

    monkeypatch.setattr(
        module,
        'QgsMarkerSymbol',
        SimpleNamespace(createSimple=lambda properties: properties),
    )
    assessment = _StyleLayer()
    control = _LegacyStyleLayer()

    module._style_results(assessment, control)

    assert control.load_calls[0][1] == {'categories': 'visual'}
