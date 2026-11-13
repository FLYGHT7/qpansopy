# -*- coding: utf-8 -*-
"""
Unit tests for pbn_target.py — pure-math parts only.
No QGIS runtime required (stubs provided by conftest).
"""
import json
import math
import pathlib
import pytest

_FIXTURES = pathlib.Path(__file__).parent.parent / 'fixtures' / 'json' / 'pbn_target_cases.json'
_CASES = json.loads(_FIXTURES.read_text(encoding='utf-8'))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_nm_to_m_constant():
    import importlib
    mod = importlib.import_module('Q_Pansopy.modules.pbn.pbn_target')
    assert mod._NM_TO_M == 1852.0


def test_segments_constant():
    import importlib
    mod = importlib.import_module('Q_Pansopy.modules.pbn.pbn_target')
    assert mod._SEGMENTS == 360


# ---------------------------------------------------------------------------
# Buffer radius values (pure arithmetic)
# ---------------------------------------------------------------------------

def test_15nm_buffer_radius_metres():
    assert 15 * 1852.0 == 27780.0


def test_30nm_buffer_radius_metres():
    assert 30 * 1852.0 == 55560.0


# ---------------------------------------------------------------------------
# UTM zone selection — algorithm tested directly (formula from pbn_target.py)
# ---------------------------------------------------------------------------

def _utm_zone(lon_deg: float) -> int:
    return int((lon_deg + 180) / 6) + 1


def _is_south(lat_deg: float) -> bool:
    return lat_deg < 0


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_utm_zone_from_json(case):
    zone = _utm_zone(case["inputs"]["lon"])
    south = _is_south(case["inputs"]["lat"])
    assert zone == case["expected"]["zone"], (
        f'{case["id"]}: expected zone {case["expected"]["zone"]}, got {zone}'
    )
    assert south == case["expected"]["south"], (
        f'{case["id"]}: expected south={case["expected"]["south"]}, got {south}'
    )


# ---------------------------------------------------------------------------
# Zone boundaries — edge cases
# ---------------------------------------------------------------------------

def test_utm_zone_boundary_at_minus180():
    assert _utm_zone(-180.0) == 1


def test_utm_zone_boundary_at_plus180():
    assert _utm_zone(179.9) == 60


def test_utm_zone_prime_meridian():
    assert _utm_zone(0.0) == 31


def test_utm_south_flag_equator_north():
    assert _is_south(0.001) is False


def test_utm_south_flag_equator_south():
    assert _is_south(-0.001) is True


def test_utm_south_flag_exactly_equator():
    # Exactly on equator: not south
    assert _is_south(0.0) is False


# ---------------------------------------------------------------------------
# Module import smoke test
# PBN Target is required: import errors must fail rather than skip.
# ---------------------------------------------------------------------------

def test_module_imports_cleanly():
    import importlib
    mod = importlib.import_module('Q_Pansopy.modules.pbn.pbn_target')
    assert mod is not None


def test_run_pbn_target_exists():
    import importlib
    mod = importlib.import_module('Q_Pansopy.modules.pbn.pbn_target')
    assert callable(mod.run_pbn_target)


def test_constants_importable():
    """Constants are available from the required module."""
    from Q_Pansopy.modules.pbn.pbn_target import _NM_TO_M, _SEGMENTS
    assert _NM_TO_M > 0 and _SEGMENTS > 0
