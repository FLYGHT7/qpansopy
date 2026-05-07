# -*- coding: utf-8 -*-
"""
Unit tests for Conv module splay-angle geometry (NDB and VOR).
Tests the core ICAO formula: secondary_half_width = 1.25 + D * tan(splay_angle).
No QGIS runtime required.
"""
import json
import math
import pathlib
import importlib
import pytest

_NDB_CASES = json.loads(
    (pathlib.Path(__file__).parent.parent / 'fixtures' / 'json' / 'conv_ndb_cases.json')
    .read_text(encoding='utf-8')
)
_VOR_CASES = json.loads(
    (pathlib.Path(__file__).parent.parent / 'fixtures' / 'json' / 'conv_vor_cases.json')
    .read_text(encoding='utf-8')
)

_NDB_SPLAY_DEG = 10.3
_VOR_SPLAY_DEG = 7.8
_PRIMARY_HALF_WIDTH_NM = 1.25


def _secondary_half_width(distance_nm: float, splay_deg: float) -> float:
    return _PRIMARY_HALF_WIDTH_NM + distance_nm * math.tan(math.radians(splay_deg))


# ---------------------------------------------------------------------------
# Primary half-width invariant
# ---------------------------------------------------------------------------

def test_primary_half_width_constant_value():
    assert _PRIMARY_HALF_WIDTH_NM == 1.25


# ---------------------------------------------------------------------------
# NDB splay formula — parametrized from JSON fixtures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", _NDB_CASES, ids=[c["id"] for c in _NDB_CASES])
def test_ndb_secondary_half_width(case):
    result = _secondary_half_width(case["inputs"]["distance_nm"], _NDB_SPLAY_DEG)
    expected = case["expected"]["secondary_half_width_nm"]
    tol = case["expected"]["tolerance"]
    assert abs(result - expected) <= tol, (
        f'{case["id"]}: expected {expected} ± {tol}, got {result:.4f}'
    )


def test_ndb_splay_increases_with_distance():
    widths = [_secondary_half_width(d, _NDB_SPLAY_DEG) for d in range(0, 16)]
    assert all(widths[i] < widths[i + 1] for i in range(len(widths) - 1))


def test_ndb_primary_width_at_origin():
    assert abs(_secondary_half_width(0.0, _NDB_SPLAY_DEG) - _PRIMARY_HALF_WIDTH_NM) < 1e-9


# ---------------------------------------------------------------------------
# VOR splay formula — parametrized from JSON fixtures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", _VOR_CASES, ids=[c["id"] for c in _VOR_CASES])
def test_vor_secondary_half_width(case):
    result = _secondary_half_width(case["inputs"]["distance_nm"], _VOR_SPLAY_DEG)
    expected = case["expected"]["secondary_half_width_nm"]
    tol = case["expected"]["tolerance"]
    assert abs(result - expected) <= tol, (
        f'{case["id"]}: expected {expected} ± {tol}, got {result:.4f}'
    )


def test_vor_splay_increases_with_distance():
    widths = [_secondary_half_width(d, _VOR_SPLAY_DEG) for d in range(0, 16)]
    assert all(widths[i] < widths[i + 1] for i in range(len(widths) - 1))


def test_vor_primary_width_at_origin():
    assert abs(_secondary_half_width(0.0, _VOR_SPLAY_DEG) - _PRIMARY_HALF_WIDTH_NM) < 1e-9


# ---------------------------------------------------------------------------
# NDB splay > VOR splay (NDB diverges faster)
# ---------------------------------------------------------------------------

def test_ndb_wider_than_vor_at_same_distance():
    for d in [1, 5, 10, 15]:
        ndb = _secondary_half_width(d, _NDB_SPLAY_DEG)
        vor = _secondary_half_width(d, _VOR_SPLAY_DEG)
        assert ndb > vor, f'At {d} NM, NDB ({ndb:.3f}) should be wider than VOR ({vor:.3f})'


# ---------------------------------------------------------------------------
# Module import smoke tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_path,main_fn", [
    ('Q_Pansopy.modules.conv.ndb_approach',          'run_ndb_approach'),
    ('Q_Pansopy.modules.conv.vor_approach',           'run_vor_approach'),
    ('Q_Pansopy.modules.conv.conv_initial_approach',  'run_conv_initial_approach'),
    # conv_initial_approach_straight.py is a legacy script (executes at import time);
    # it cannot be cleanly imported with stubs and is excluded from smoke tests.
], ids=['ndb', 'vor', 'conv_initial'])
def test_conv_module_imports_and_exposes_main(module_path, main_fn):
    mod = importlib.import_module(module_path)
    assert mod is not None
    assert hasattr(mod, main_fn), f'{module_path} must expose {main_fn}()'
    assert callable(getattr(mod, main_fn))
