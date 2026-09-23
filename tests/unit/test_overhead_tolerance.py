"""Numerical checks for ICAO overhead VOR/NDB construction."""

import importlib.util
import math
from pathlib import Path

import pytest


@pytest.fixture
def overhead():
    """Load the module after the per-test QGIS stubs are installed."""
    path = (Path(__file__).resolve().parents[2] / 'Q_Pansopy' / 'modules'
            / 'conv' / 'overhead_tolerance.py')
    spec = importlib.util.spec_from_file_location('overhead_tolerance_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('navaid,cone_angle,entry_angle', [
    ('VOR', 50, 5), ('NDB', 40, 15),
])
def test_radius_offsets_and_intersections(overhead, navaid, cone_angle, entry_angle):
    station = (100000.0, 200000.0)
    area, cone, points, radius_nm, q_nm = overhead.build_overhead_coordinates(
        station, (1, 0), 5000, navaid)
    expected_radius = 0.164 * 5 * math.tan(math.radians(cone_angle))
    assert radius_nm == pytest.approx(expected_radius)
    assert q_nm == pytest.approx(expected_radius * math.sin(math.radians(entry_angle)))
    prefix = 'V' if navaid == 'VOR' else 'N'
    assert points['Station'] == station
    assert points[prefix + '2'][1] - station[1] == pytest.approx(q_nm * 1852)
    assert points[prefix + '4'][1] - station[1] == pytest.approx(-q_nm * 1852)
    for label in ('1', '2', '3', '4'):
        x, y = points[prefix + label]
        assert math.hypot(x - station[0], y - station[1]) == pytest.approx(
            radius_nm * 1852)
    assert points[prefix + '1'][0] > points[prefix + '2'][0]
    assert points[prefix + '3'][0] > points[prefix + '4'][0]
    assert area[0] == area[-1]
    assert cone[0] == pytest.approx(cone[-1])


def test_ndb_has_wider_entry_offset_than_vor_at_same_radius_fraction(overhead):
    vor = overhead.build_overhead_coordinates((0, 0), (1, 0), 5000, 'VOR')
    ndb = overhead.build_overhead_coordinates((0, 0), (1, 0), 5000, 'NDB')
    assert ndb[4] / ndb[3] > vor[4] / vor[3]


def test_inbound_nearest_endpoint_and_reverse(overhead):
    vertices = [(0, 0), (100, 0)]
    assert overhead.inbound_from_track((90, 0), vertices) == ((100, 0), False)
    assert overhead.inbound_from_track((90, 0), vertices, True) == ((-100, 0), False)
    assert overhead.inbound_from_track((10, 0), vertices) == ((-100, 0), False)
    assert overhead.inbound_from_track((50, 0), vertices) == ((100, 0), True)


@pytest.mark.parametrize('height,navaid', [
    (0, 'VOR'), (-100, 'NDB'), (float('nan'), 'VOR'), (1000, 'ILS'),
])
def test_invalid_construction_inputs(overhead, height, navaid):
    with pytest.raises(ValueError):
        overhead.build_overhead_coordinates((0, 0), (1, 0), height, navaid)


def test_zero_length_direction_rejected(overhead):
    with pytest.raises(ValueError):
        overhead.build_overhead_coordinates((0, 0), (0, 0), 1000, 'VOR')
