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
