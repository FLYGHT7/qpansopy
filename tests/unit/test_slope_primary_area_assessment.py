"""Numerical contracts for the generic sloping assessment."""

from dataclasses import replace

import pytest


def _record(elevation=1106.0, tolerance=0.0, layer_type='survey'):
    from Q_Pansopy.modules.utilities.primary_area_assessment import SourceRecord

    return SourceRecord('A', layer_type, 'building', elevation, tolerance, None)


def test_video_example_preserves_unrounded_clearance():
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import evaluate_point

    result = evaluate_point(_record(), 4679.075, 1008.0, 1.88)

    assert result.surface_z == pytest.approx(1161.585820458, abs=1e-9)
    assert result.clearance == pytest.approx(55.585820458, abs=1e-9)
    assert result.penetrates == 'clear'


@pytest.mark.parametrize('elevation,status,clearance', [
    (102.0, 'penetrates', -2.0),
    (100.0, 'clear', 0.0),
    (99.9999999999, 'clear', 1e-10),
    (100.0000000001, 'penetrates', -1e-10),
])
def test_classification_uses_raw_clearance(elevation, status, clearance):
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import evaluate_point

    result = evaluate_point(_record(elevation), 500.0, 100.0, 0.0)

    assert result.clearance == pytest.approx(clearance, abs=1e-13)
    assert result.penetrates == status


def test_negative_slope_and_negative_start_elevation_are_supported():
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import evaluate_point

    result = evaluate_point(_record(-115.0), 100.0, -10.0, -45.0)

    assert result.surface_z == pytest.approx(-110.0)
    assert result.clearance == pytest.approx(5.0)


def test_override_changes_survey_tolerance_only():
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import evaluate_point

    survey = _record(100.0, 3.0)
    terrain = replace(survey, layer_type='DTM', obstacle_type='terrain')
    survey_result = evaluate_point(survey, 0.0, 110.0, 0.0, 12.0)
    terrain_result = evaluate_point(terrain, 0.0, 110.0, 0.0, 12.0)

    assert survey_result.applied_tolerance_m == 12.0
    assert survey_result.clearance == -2.0
    assert survey_result.source.tolerance_m == 3.0
    assert terrain_result.applied_tolerance_m == 3.0
    assert terrain_result.clearance == 7.0


@pytest.mark.parametrize('distance,base,angle,override', [
    (-1.0, 0.0, 0.0, None),
    (float('nan'), 0.0, 0.0, None),
    (float('inf'), 0.0, 0.0, None),
    (0.0, float('inf'), 0.0, None),
    (0.0, float('nan'), 0.0, None),
    (0.0, 0.0, -90.0, None),
    (0.0, 0.0, 90.0, None),
    (0.0, 0.0, 91.0, None),
    (0.0, 0.0, float('nan'), None),
    (0.0, 0.0, 0.0, -1.0),
    (0.0, 0.0, 0.0, float('inf')),
])
def test_invalid_parameters_are_rejected(distance, base, angle, override):
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import evaluate_point

    with pytest.raises(ValueError):
        evaluate_point(_record(), distance, base, angle, override)


@pytest.mark.parametrize('elevation,tolerance', [
    (float('nan'), 0.0), (float('inf'), 0.0),
    (0.0, -1.0), (0.0, float('inf')),
])
def test_invalid_source_values_are_rejected(elevation, tolerance):
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import evaluate_point

    with pytest.raises(ValueError):
        evaluate_point(_record(elevation, tolerance), 0.0, 0.0, 0.0)
