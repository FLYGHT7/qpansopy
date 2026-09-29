"""Numeric and geometric checks for the Holding Point E construction."""

import importlib
import math

import pytest


@pytest.fixture
def holding():
    return importlib.import_module('Q_Pansopy.modules.utilities.holding')


def _summary(holding, ias=220, altitude_ft=10000, isa_var=15, leg_min=1):
    k, tas, rate, radius, _wind = holding.tas_calculation(
        ias, altitude_ft, isa_var, 25)
    return {
        'IAS_kt': ias, 'Altitude_ft': altitude_ft,
        'ISA_var_C': isa_var, 'Bank_deg': 25, 'Leg_min': leg_min,
        'Turn': 'R', 'K_factor': k, 'TAS_kt': tas,
        'Rate_deg_s': rate, 'Radius_nm': radius,
    }


def test_entry_offsets_match_reference_table_and_change_with_inputs(holding):
    xe, ye = holding.calculate_holding_entry_offsets_nm(_summary(holding))
    assert xe == pytest.approx(13.2813687475)
    assert ye == pytest.approx(6.9395972753)
    faster_xe, faster_ye = holding.calculate_holding_entry_offsets_nm(
        _summary(holding, ias=240))
    assert faster_xe > xe
    assert faster_ye > ye


def test_zip_placement_and_eight_construction_lines_for_right_turn(holding):
    # Inbound track east; local lateral axis points south for a right turn.
    outline = [(-1000, 2000), (5000, 2000), (5000, -3000), (-1000, -3000)]
    construction = holding.build_point_e_construction(
        outline, origin=(0, 0), azimuth=90, turn='R',
        xe_nm=2, ye_nm=1)
    # x_min = -1000 m; local y_min = -2000 m (northern edge).
    assert construction.point == pytest.approx((2704, 148))
    assert set(construction.lines) == {
        'MIN_LONGITUDINAL', 'MAX_LONGITUDINAL',
        'MIN_LATERAL', 'MAX_LATERAL', 'x-AXIS', 'y-AXIS',
        'E_OFFSET_X', 'E_OFFSET_Y',
    }
    e_x_line = construction.lines['E_OFFSET_X']
    e_y_line = construction.lines['E_OFFSET_Y']
    assert e_x_line[0][0] == pytest.approx(2704)
    assert e_x_line[1][0] == pytest.approx(2704)
    assert e_y_line[0][1] == pytest.approx(148)
    assert e_y_line[1][1] == pytest.approx(148)
    assert construction.bounds == pytest.approx((-1000, 5000, -2000, 3000))


def test_left_turn_mirrors_lateral_axis_and_point_e(holding):
    right_outline = [(-1000, 2000), (5000, 2000), (5000, -3000), (-1000, -3000)]
    left_outline = [(x, -y) for x, y in right_outline]
    right = holding.build_point_e_construction(
        right_outline, (0, 0), 90, 'R', 2, 1)
    left = holding.build_point_e_construction(
        left_outline, (0, 0), 90, 'L', 2, 1)
    assert left.point == pytest.approx((right.point[0], -right.point[1]))
    assert left.bounds == pytest.approx(right.bounds)


def test_rotating_track_rotates_e_and_lines_without_changing_distances(holding):
    outline = [(-1000, 2000), (5000, 2000), (5000, -3000), (-1000, -3000)]
    east = holding.build_point_e_construction(outline, (0, 0), 90, 'R', 2, 1)
    # Rotate all input points 90 degrees counterclockwise, then translate.
    rotated = [(10000 - y, 20000 + x) for x, y in outline]
    north = holding.build_point_e_construction(
        rotated, (10000, 20000), 0, 'R', 2, 1)
    assert north.point == pytest.approx((10000 - east.point[1],
                                         20000 + east.point[0]))
    assert north.bounds == pytest.approx(east.bounds)
    for name, (start, end) in east.lines.items():
        rotated_start = (10000 - start[1], 20000 + start[0])
        rotated_end = (10000 - end[1], 20000 + end[0])
        actual_start, actual_end = north.lines[name]
        assert actual_start == pytest.approx(rotated_start)
        assert actual_end == pytest.approx(rotated_end)


def test_offset_lines_reach_point_e_outside_template_bounds(holding):
    outline = [(0, 0), (1000, 0), (1000, -1000), (0, -1000)]
    construction = holding.build_point_e_construction(
        outline, (0, 0), 90, 'R', 3, 2)
    ex, ey = construction.point
    x_line = construction.lines['E_OFFSET_X']
    y_line = construction.lines['E_OFFSET_Y']
    assert min(point[1] for point in x_line) <= ey <= max(point[1] for point in x_line)
    assert min(point[0] for point in y_line) <= ex <= max(point[0] for point in y_line)


@pytest.mark.parametrize('outline,turn,xe,ye', [
    ([], 'R', 1, 1),
    ([(0, 0)], 'R', 1, 1),
    ([(0, 0), (1, 0), (1, 1)], 'X', 1, 1),
    ([(0, 0), (1, 0), (1, 1)], 'R', math.nan, 1),
    ([(0, 0), (1, 0), (1, 1)], 'R', 1, -1),
])
def test_invalid_point_e_inputs_are_rejected(holding, outline, turn, xe, ye):
    with pytest.raises(ValueError):
        holding.build_point_e_construction(outline, (0, 0), 90, turn, xe, ye)
