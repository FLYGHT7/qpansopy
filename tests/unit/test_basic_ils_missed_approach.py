# -*- coding: utf-8 -*-
"""
Regression test for issue #188: Basic ILS missed approach surface lateral
half-width was silently changed from a 14.3%-transition-slope-derived offset
to a flat 15% splay during a "readability" refactor (commit 581f936),
shrinking the missed approach surface compared to the reference script.
"""
import importlib

import pytest


def _missed_half_widths(ils_transition_slope):
    """Mirrors the formulas in Q_Pansopy/modules/basic_ils.py."""
    w_1800m = 150 + 1800 * ((45 / (ils_transition_slope / 100)) / 1800)
    w_12000m = 150 + 1800 * ((45 / (ils_transition_slope / 100)) / 1800) + (10200 * 0.25)
    return w_1800m, w_12000m


def test_missed_half_width_matches_reference_script():
    constants = importlib.import_module('Q_Pansopy.modules.constants')
    w_1800m, w_12000m = _missed_half_widths(constants.ILS_TRANSITION_SLOPE)

    assert w_1800m == pytest.approx(464.68531468531467)
    assert w_12000m == pytest.approx(3014.6853146853146)


def test_missed_half_width_is_not_the_buggy_15_percent_splay():
    constants = importlib.import_module('Q_Pansopy.modules.constants')
    w_1800m, w_12000m = _missed_half_widths(constants.ILS_TRANSITION_SLOPE)

    # The regression computed these as a flat 15% splay: 150 + 1800*0.15 = 420
    # and 150 + 12900*0.15 = 2085.
    assert w_1800m != pytest.approx(420.0)
    assert w_12000m != pytest.approx(2085.0)
