import hashlib
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ElementTree

import pytest


class _Crs:
    def __init__(self, identifier, valid=True, geographic=False):
        self.identifier = identifier
        self.valid = valid
        self.geographic = geographic

    def isValid(self):
        return self.valid

    def isGeographic(self):
        return self.geographic

    def __eq__(self, other):
        return self.identifier == other.identifier


class _Layer:
    def __init__(self, crs):
        self._crs = crs

    def crs(self):
        return self._crs


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


def test_all_analyzed_obstacles_style_is_small_orange_unlabelled():
    style_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/styles/all_analyzed_obstacles.qml'
    )
    root = ElementTree.parse(style_path).getroot()
    symbol = root.find('./renderer-v2/symbols/symbol')
    marker = symbol.find("./layer[@class='SimpleMarker']/Option")
    options = {
        option.get('name'): option.get('value')
        for option in marker.findall('./Option')
    }

    assert root.get('labelsEnabled') == '0'
    assert symbol.get('type') == 'marker'
    assert options['name'] == 'circle'
    assert options['color'].startswith('255,171,84,255,')
    assert options['size'] == '0.25'
    assert options['size_unit'] == 'MM'


def test_all_analyzed_obstacles_style_loads_visual_categories_only():
    from Q_Pansopy.modules.utilities import primary_area_assessment as module

    class Layer:
        StyleCategory = SimpleNamespace(AllVisualStyleCategories='visual')

        def __init__(self):
            self.loaded = []

        def loadNamedStyle(self, path, categories):
            self.loaded.append((Path(path).name, categories))
            return '', True

        def triggerRepaint(self):
            pass

    assessment = Layer()
    control = Layer()

    module._style_results(assessment, control)

    assert assessment.loaded == [('all_analyzed_obstacles.qml', 'visual')]
    assert control.loaded == [('control_obstacle_primary_style.qml', 'visual')]

    control_only = Layer()
    module._style_results(None, control_only)
    assert control_only.loaded == [
        ('control_obstacle_primary_style.qml', 'visual')
    ]


def test_all_analyzed_obstacles_style_failure_keeps_circle(monkeypatch):
    from Q_Pansopy.modules.utilities import primary_area_assessment as module

    class Layer:
        StyleCategory = SimpleNamespace(AllVisualStyleCategories='visual')

        def __init__(self, succeeds):
            self.succeeds = succeeds
            self.symbol = None

        def loadNamedStyle(self, path, categories):
            return '', self.succeeds

        def renderer(self):
            return self

        def setSymbol(self, symbol):
            self.symbol = symbol

        def triggerRepaint(self):
            pass

    monkeypatch.setattr(
        module,
        'QgsMarkerSymbol',
        SimpleNamespace(createSimple=lambda settings: settings),
    )
    assessment = Layer(False)

    module._style_results(assessment, Layer(True))

    assert assessment.symbol == {
        'name': 'circle',
        'color': '220,0,0,255',
        'outline_style': 'no',
        'size': '1.0',
    }


def test_evaluation_uses_each_records_tolerance():
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    evaluated, controls = evaluate_records(
        [_record('A', 100.0, 3.0), _record('B', 98.0, 7.0)],
        moc_m=75.0,
    )

    assert [item.oca_m for item in evaluated] == [178.0, 180.0]
    assert evaluated[0].oca_ft == round(178.0 / 0.3048, 3)
    assert evaluated[0].oca_pub_ft == 600
    assert [item.identifier for item in controls] == ['B']


@pytest.mark.parametrize(
    'increment,expected',
    [
        (1, 8285),
        (5, 8285),
        (10, 8290),
        (100, 8300),
    ],
)
def test_published_oca_rounds_up_to_selected_increment(increment, expected):
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    evaluated, _ = evaluate_records(
        [_record('A', 8284.121 * 0.3048, 0.0)],
        moc_m=0.0,
        oca_rounding_ft=increment,
    )

    assert evaluated[0].oca_ft == 8284.121
    assert evaluated[0].oca_pub_ft == expected


def test_published_oca_keeps_exact_increment_boundary():
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    evaluated, _ = evaluate_records(
        [_record('A', 8300.0 * 0.3048, 0.0)],
        moc_m=0.0,
        oca_rounding_ft=100,
    )

    assert evaluated[0].oca_pub_ft == 8300


@pytest.mark.parametrize('increment', [0, 2, 25, 1000, True, 1.0, '100'])
def test_evaluation_rejects_invalid_oca_rounding_increment(increment):
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    with pytest.raises(ValueError, match='OCA publication increment'):
        evaluate_records(
            [_record('A', 100.0, 0.0)],
            moc_m=0.0,
            oca_rounding_ft=increment,
        )


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
    'override,expected_applied,expected_oca,expected_control',
    [
        (None, [31.0, 20.0], [131.0, 140.0], 'survey'),
        (0.0, [31.0, 0.0], [131.0, 120.0], 'terrain'),
    ],
)
def test_survey_override_preserves_terrain_tolerance_and_control(
    override, expected_applied, expected_oca, expected_control,
):
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        _evaluate_control_records,
        evaluate_records,
    )

    records = [
        replace(
            _record('terrain', 100.0, 31.0),
            layer_type='DTM',
            obstacle_type='terrain',
        ),
        _record('survey', 120.0, 20.0),
    ]

    evaluated, controls = evaluate_records(
        records, moc_m=0.0, override_tolerance_m=override,
    )
    assessed_count, control_only = _evaluate_control_records(
        records, moc_m=0.0, override_tolerance_m=override,
    )

    assert [item.tolerance_m for item in evaluated] == [31.0, 20.0]
    assert [item.applied_tolerance_m for item in evaluated] == expected_applied
    assert [item.oca_m for item in evaluated] == expected_oca
    assert [item.identifier for item in controls] == [expected_control]
    assert assessed_count == len(evaluated)
    assert control_only == controls


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


@pytest.mark.parametrize(
    'value,unit,expected',
    [
        (2.0, 'NM', 3704.0),
        (250.0, 'm', 250.0),
        (0.0, 'NM', 0.0),
    ],
)
def test_area_buffer_units_are_converted_to_metres(value, unit, expected):
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        area_buffer_to_metres,
    )

    assert area_buffer_to_metres(value, unit) == expected


@pytest.mark.parametrize('value', [-1.0, math.inf, math.nan])
def test_area_buffer_conversion_rejects_invalid_values(value):
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        area_buffer_to_metres,
    )

    with pytest.raises(ValueError, match='Area buffer'):
        area_buffer_to_metres(value, 'NM')


def test_area_buffer_conversion_rejects_unknown_unit():
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        area_buffer_to_metres,
    )

    with pytest.raises(ValueError, match='Unsupported area buffer unit'):
        area_buffer_to_metres(1.0, 'ft')


def test_empty_evaluation_has_no_control_obstacle():
    from Q_Pansopy.modules.utilities.primary_area_assessment import evaluate_records

    assert evaluate_records([], moc_m=75.0) == ([], [])


def test_control_only_evaluation_matches_full_evaluation():
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        _evaluate_control_records,
        evaluate_records,
    )

    records = [
        _record('lower', 100.0, 0.0),
        _record('tie-a', 125.0, 0.0),
        _record('tie-b', 125.0 + 5e-10, 0.0),
    ]
    evaluated, expected_controls = evaluate_records(
        records, moc_m=10.0, override_tolerance_m=0.0
    )
    assessed_count, controls = _evaluate_control_records(
        records, moc_m=10.0, override_tolerance_m=0.0
    )

    assert assessed_count == len(evaluated)
    assert [item.identifier for item in controls] == [
        item.identifier for item in expected_controls
    ]
    assert [item.oca_m for item in controls] == [
        item.oca_m for item in expected_controls
    ]


@pytest.mark.parametrize(
    'role,valid,geographic',
    [
        ('assessment area', False, False),
        ('terrain', False, False),
        ('survey', False, False),
        ('assessment area', True, True),
        ('terrain', True, True),
        ('survey', True, True),
    ],
)
def test_crs_validation_requires_projected_inputs(role, valid, geographic):
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        CrsValidationError,
        _validate_crs,
    )

    projected = _Crs('EPSG:32616')
    invalid = _Crs('EPSG:4326', valid=valid, geographic=geographic)
    layers = {
        'assessment area': _Layer(invalid),
        'terrain': _Layer(invalid),
        'survey': _Layer(invalid),
    }

    with pytest.raises(CrsValidationError, match=role):
        _validate_crs(
            layers['assessment area'] if role == 'assessment area'
            else _Layer(projected),
            layers['terrain'] if role == 'terrain' else None,
            layers['survey'] if role == 'survey' else None,
        )


def test_crs_validation_rejects_different_projected_crs():
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        CrsValidationError,
        _validate_crs,
    )

    with pytest.raises(CrsValidationError, match='same CRS'):
        _validate_crs(
            _Layer(_Crs('EPSG:32616')),
            _Layer(_Crs('EPSG:32617')),
            None,
        )


def test_geographic_input_stops_before_mask_processing(monkeypatch):
    from Q_Pansopy.modules.utilities import primary_area_assessment as module

    mask_called = []
    monkeypatch.setattr(
        module,
        '_build_mask_geometry',
        lambda *args: mask_called.append(True),
    )

    with pytest.raises(module.CrsValidationError):
        module.run_primary_area_assessment(
            None,
            _Layer(_Crs('EPSG:32616')),
            obstacle_layer=_Layer(_Crs('EPSG:4326', geographic=True)),
        )

    assert not mask_called


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
    assert property_text('loadAllPointsCheckBox', 'checked') == 'false'
    assert property_text(
        'loadAllPointsCheckBox', 'text'
    ) == 'Load all analyzed points'
    assert property_text(
        'outputDescriptionLabel', 'text'
    ) == 'The control obstacle layer will be added to the project.'
    assert property_text(
        'areaBufferDoubleSpinBox', 'minimum'
    ) == '0.000000000000000'
    assert property_text(
        'areaBufferDoubleSpinBox', 'maximum'
    ) == '99999.000000000000000'
    assert property_text('areaBufferDoubleSpinBox', 'decimals') == '3'
    assert property_text(
        'areaBufferDoubleSpinBox', 'singleStep'
    ) == '0.100000000000000'
    assert property_text(
        'areaBufferDoubleSpinBox', 'value'
    ) == '0.000000000000000'
    assert property_text('mocDoubleSpinBox', 'value') == '75.000000000000000'
    assert property_text(
        'terrainToleranceDoubleSpinBox', 'value'
    ) == '50.000000000000000'
    rounding_combo = root.find(".//widget[@name='ocaRoundingComboBox']")
    rounding_label = root.find(".//widget[@name='ocaRoundingLabel']")
    params_form = root.find(".//layout[@name='paramsFormLayout']")
    rounding_rows = {
        item.find('./widget').get('name'): int(item.get('row'))
        for item in params_form.findall('./item')
        if item.find('./widget') is not None
        and item.find('./widget').get('name') in {
            'ocaRoundingLabel', 'ocaRoundingComboBox'
        }
    }

    assert rounding_label.find("./property[@name='text']/string").text == (
        'OCA publication increment (ft):'
    )
    assert rounding_rows == {
        'ocaRoundingLabel': 3,
        'ocaRoundingComboBox': 3,
    }
    assert [
        item.find("./property[@name='text']/string").text
        for item in rounding_combo.findall('./item')
    ] == ['1', '5', '10', '100']
    assert property_text('ocaRoundingComboBox', 'currentIndex') == '3'


def test_area_buffer_ui_is_before_terrain_and_defaults_to_nm():
    ui_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.ui'
    )
    root = ElementTree.parse(ui_path).getroot()
    form = root.find(".//layout[@name='inputFormLayout']")

    rows = {}
    for item in form.findall('./item'):
        widget = item.find('.//widget')
        if widget is not None:
            rows[widget.get('name')] = int(item.get('row'))

    unit_combo = root.find(".//widget[@name='areaBufferUnitComboBox']")
    units = [
        item.find('./property/string').text
        for item in unit_combo.findall('./item')
    ]

    assert rows['areaBufferLabel'] == 2
    assert rows['terrainLabel'] == 3
    assert rows['obstacleLabel'] == 4
    assert units == ['NM', 'm']


def test_field_mapping_group_uses_qgis_collapsible_widget():
    ui_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.ui'
    )
    root = ElementTree.parse(ui_path).getroot()
    group = root.find(".//widget[@name='fieldMappingGroup']")
    custom_widget = root.find(
        ".//customwidget/class[.='QgsCollapsibleGroupBoxBasic']/.."
    )

    assert group.get('class') == 'QgsCollapsibleGroupBoxBasic'
    assert custom_widget.find('./extends').text == 'QGroupBox'
    assert custom_widget.find('./header').text == 'qgis.gui'
    assert custom_widget.find('./container').text == '1'
    assert group.find("./property[@name='collapsed']/bool").text == 'false'


def test_dockwidget_uses_flat_bold_input_sections():
    ui_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.ui'
    )
    root = ElementTree.parse(ui_path).getroot()

    for group_name in ('inputGroup', 'fieldMappingGroup', 'paramsGroup'):
        group = root.find(f".//widget[@name='{group_name}']")
        assert group.find("./property[@name='flat']/bool").text == 'true'
        assert group.find(
            "./property[@name='alignment']/set"
        ).text == 'Qt::AlignLeading|Qt::AlignLeft|Qt::AlignVCenter'
        stylesheet = group.find("./property[@name='styleSheet']/string")
        assert 'font-weight: bold' in stylesheet.text

def test_dockwidget_labels_override_as_survey_obstacle_tolerance():
    ui_path = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.ui'
    )
    root = ElementTree.parse(ui_path).getroot()
    widget = root.find(
        ".//widget[@name='overrideToleranceCheckBox']"
    )
    text = widget.find("./property[@name='text']/string").text

    assert text == 'Override survey obstacle tolerance'


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


def test_dockwidget_hides_the_fixed_terrain_band():
    root = ElementTree.parse(
        Path(__file__).parents[2]
        / 'Q_Pansopy/ui/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.ui'
    ).getroot()
    dock_source = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/dockwidgets/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.py'
    ).read_text(encoding='utf-8')

    assert root.find(".//widget[@name='terrainBandLabel']") is None
    assert root.find(".//widget[@name='terrainBandSpinBox']") is None
    assert 'terrain_band=1,' in dock_source
    assert 'terrainBandSpinBox' not in dock_source


def test_dockwidget_shows_and_clears_processing_message():
    dock_source = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/dockwidgets/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.py'
    ).read_text(encoding='utf-8')

    assert 'self._show_processing_message()' in dock_source
    assert 'level=Qgis.Info' in dock_source
    assert 'duration=30' in dock_source
    assert 'Primary area assessment is in progress.' in dock_source
    assert 'This may take several minutes.' in dock_source
    assert 'self._processing_message = message_bar.currentItem()' in dock_source
    assert 'message_bar.popWidget(item)' in dock_source
    assert 'self._clear_processing_message()' in dock_source
    assert 'level=Qgis.Success' in dock_source


def test_dockwidget_passes_load_all_points_state():
    dock_source = (
        Path(__file__).parents[2]
        / 'Q_Pansopy/dockwidgets/utilities/'
        / 'qpansopy_primary_area_assessment_dockwidget.py'
    ).read_text(encoding='utf-8')

    assert 'load_all_points=self.loadAllPointsCheckBox.isChecked(),' in (
        dock_source
    )
