import math
import inspect
from pathlib import Path
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


@pytest.mark.parametrize(
    'value,unit,expected',
    [
        (0.0, 'NM', 0.0),
        (1.0, 'NM', 1852.0),
        (2.5, 'm', 2.5),
    ],
)
def test_area_buffer_units_are_converted_to_metres(value, unit, expected):
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        area_buffer_to_metres,
    )

    assert area_buffer_to_metres(value, unit) == expected


@pytest.mark.parametrize('value', [-1.0, math.inf, -math.inf, math.nan])
def test_area_buffer_conversion_rejects_invalid_values(value):
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        area_buffer_to_metres,
    )

    with pytest.raises(ValueError, match='Area buffer'):
        area_buffer_to_metres(value, 'NM')


def test_area_buffer_conversion_rejects_unknown_units():
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        area_buffer_to_metres,
    )

    with pytest.raises(ValueError, match='Unsupported area buffer unit'):
        area_buffer_to_metres(1.0, 'ft')


def test_area_buffer_is_last_backward_compatible_run_parameter():
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    parameters = list(
        inspect.signature(run_primary_area_assessment).parameters.values()
    )

    assert parameters[-1].name == 'area_buffer_m'
    assert parameters[-1].default == 0.0


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
