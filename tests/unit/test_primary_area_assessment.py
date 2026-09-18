import math
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
    rounding_combo = root.find(".//widget[@name='ocaRoundingComboBox']")
    assert [
        item.find("./property[@name='text']/string").text
        for item in rounding_combo.findall('./item')
    ] == ['1', '5', '10', '100']
    assert property_text('ocaRoundingComboBox', 'currentIndex') == '3'


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
