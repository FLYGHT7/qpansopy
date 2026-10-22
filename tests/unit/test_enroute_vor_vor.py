"""Numerical contracts for the simplified straight VOR/VOR criteria."""

import math

import pytest


@pytest.mark.parametrize('distance,case', [
    (1000.0, 1), (99.6 * 1852 - 0.001, 1),
    (99.6 * 1852, 1), (99.6 * 1852 + 0.001, 2),
])
def test_case_uses_the_unrounded_nm_threshold(distance, case):
    from Q_Pansopy.modules.conv.enroute_vor_vor import calculate_profile

    assert calculate_profile(distance).case == case


def test_case_one_uses_exact_kilometre_widths_everywhere():
    from Q_Pansopy.modules.conv.enroute_vor_vor import calculate_profile

    profile = calculate_profile(99.6 * 1852)
    for position in (0.0, profile.distance_m / 2, profile.distance_m):
        assert profile.half_widths(position) == (9300.0, 18500.0)


def test_case_two_has_percent_splays_and_a_perpendicular_margin():
    from Q_Pansopy.modules.conv.enroute_vor_vor import calculate_profile

    profile = calculate_profile(200000.0)
    primary, exterior = profile.half_widths(100000.0)
    assert primary == 10000.0
    assert exterior == pytest.approx(19747.06071474696, abs=1e-9)
    assert (exterior - 0.16 * 100000) / math.hypot(1, 0.16) == pytest.approx(3700.0)
    assert profile.half_widths(0) == (9300.0, 18500.0)
    assert profile.half_widths(200000) == (9300.0, 18500.0)


def test_small_splays_do_not_shrink_or_force_widening_of_the_base_corridor():
    from Q_Pansopy.modules.conv.enroute_vor_vor import calculate_profile

    profile = calculate_profile(185000.0)
    assert profile.case == 2
    primary, exterior = profile.half_widths(92500.0)
    assert primary == 9300.0
    assert exterior > 18500.0
    assert profile.half_widths(1000) == (9300.0, 18500.0)


@pytest.mark.parametrize('position', [0, 30000, 92000, 110000, 150000])
def test_profile_is_symmetric_between_stations(position):
    from Q_Pansopy.modules.conv.enroute_vor_vor import calculate_profile

    profile = calculate_profile(300000.0)
    assert profile.half_widths(position) == profile.half_widths(300000 - position)


@pytest.mark.parametrize('distance', [0, -1, float('nan'), float('inf')])
def test_invalid_station_separations_are_rejected(distance):
    from Q_Pansopy.modules.conv.enroute_vor_vor import calculate_profile

    with pytest.raises(ValueError):
        calculate_profile(distance)


@pytest.mark.parametrize('position', [-1, 200001, float('nan'), float('inf')])
def test_profile_rejects_positions_outside_the_station_segment(position):
    from Q_Pansopy.modules.conv.enroute_vor_vor import calculate_profile

    with pytest.raises(ValueError):
        calculate_profile(200000).half_widths(position)
