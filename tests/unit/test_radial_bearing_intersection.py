"""Numerical checks for radial/bearing intersection fix tolerance."""

import importlib.util
import math
import sys
from pathlib import Path

import pytest


@pytest.fixture
def intersection():
    path = (Path(__file__).resolve().parents[2] / 'Q_Pansopy' / 'modules' /
            'conv' / 'radial_bearing_intersection.py')
    spec = importlib.util.spec_from_file_location('radial_bearing_intersection_test', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(spec.name, None)


@pytest.mark.parametrize('kind,tracking,crossing', [
    ('VOR', 5.2, 4.5),
    ('ILS', 2.4, 1.4),
    ('NDB', 6.9, 6.2),
])
def test_table_has_distinct_accuracies_for_each_role(intersection, kind, tracking, crossing):
    assert intersection.ACCURACY_DEGREES[kind] == (tracking, crossing)


def test_perpendicular_vor_crossing_has_expected_limits(intersection):
    result = intersection.build_intersection_tolerance(
        (0, 0), (10000, -10000), (10000, 0), 'VOR', 'VOR', 'outbound')
    expected_nm = 10000 * math.tan(math.radians(4.5)) / 1852
    assert result.early_nm == pytest.approx(expected_nm)
    assert result.late_nm == pytest.approx(expected_nm)
    assert result.ring[0] == result.ring[-1]
    assert len(result.ring) == 5
    assert result.area_m2 > 0


def test_intersecting_type_controls_along_track_tolerance(intersection):
    vor = intersection.build_intersection_tolerance(
        (0, 0), (10000, -10000), (10000, 0), 'VOR', 'VOR', 'outbound')
    ndb = intersection.build_intersection_tolerance(
        (0, 0), (10000, -10000), (10000, 0), 'VOR', 'NDB', 'outbound')
    assert ndb.early_nm > vor.early_nm
    assert ndb.late_nm > vor.late_nm
    assert ndb.track_angle_deg == vor.track_angle_deg == 5.2
    assert ndb.cross_angle_deg == 6.2


def test_tracking_type_changes_polygon_width(intersection):
    vor = intersection.build_intersection_tolerance(
        (0, 0), (10000, -10000), (10000, 0), 'VOR', 'VOR', 'outbound')
    ils = intersection.build_intersection_tolerance(
        (0, 0), (10000, -10000), (10000, 0), 'ILS', 'VOR', 'outbound')
    assert vor.area_m2 > ils.area_m2
    assert ils.track_angle_deg == 2.4
    assert ils.cross_angle_deg == 4.5


def test_inbound_reverses_early_and_late_for_oblique_crossing(intersection):
    inputs = ((0, 0), (13000, -9000), (10000, 0), 'VOR', 'NDB')
    outbound = intersection.build_intersection_tolerance(*inputs, 'outbound')
    inbound = intersection.build_intersection_tolerance(*inputs, 'inbound')
    assert outbound.early_nm != pytest.approx(outbound.late_nm)
    assert inbound.early_nm == pytest.approx(outbound.late_nm)
    assert inbound.late_nm == pytest.approx(outbound.early_nm)
    assert inbound.ring == outbound.ring


def test_construction_has_no_ten_nm_distance_limit(intersection):
    result = intersection.build_intersection_tolerance(
        (0, 0), (50000, -50000), (50000, 0), 'VOR', 'VOR', 'outbound')
    assert result.early_nm > 0
    assert result.late_nm > 0
    assert result.area_m2 > 0


@pytest.mark.parametrize('tracking,crossing,fix,track_type,cross_type,direction', [
    ((0, 0), (0, 0), (10000, 0), 'VOR', 'VOR', 'outbound'),
    ((0, 0), (10000, -10000), (0, 0), 'VOR', 'VOR', 'outbound'),
    ((0, 0), (10000, -10000), (10000, -10000), 'VOR', 'VOR', 'outbound'),
    ((0, 0), (10000, -10000), (10000, 0), 'DME', 'VOR', 'outbound'),
    ((0, 0), (10000, -10000), (10000, 0), 'VOR', 'DME', 'outbound'),
    ((0, 0), (10000, -10000), (10000, 0), 'VOR', 'VOR', 'sideways'),
    ((0, 0), (10000, 0), (20000, 0), 'VOR', 'VOR', 'outbound'),
    ((0, 0), (10000, -100), (20000, 0), 'VOR', 'VOR', 'outbound'),
    ((math.nan, 0), (10000, -10000), (10000, 0), 'VOR', 'VOR', 'outbound'),
])
def test_invalid_constructions_raise_value_error(
        intersection, tracking, crossing, fix, track_type, cross_type, direction):
    with pytest.raises(ValueError):
        intersection.build_intersection_tolerance(
            tracking, crossing, fix, track_type, cross_type, direction)
