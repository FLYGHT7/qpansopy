# -*- coding: utf-8 -*-
"""
Unit tests for departures/sid_initial_climb.py — pure-math functions.
No QGIS runtime required.
"""
import json
import math
import pathlib
import importlib
import pytest

_CASES = json.loads(
    (pathlib.Path(__file__).parent.parent / 'fixtures' / 'json' / 'sid_isa_cases.json')
    .read_text(encoding='utf-8')
)


def _sid():
    return importlib.import_module('Q_Pansopy.modules.departures.sid_initial_climb')


# ---------------------------------------------------------------------------
# Module smoke test
# ---------------------------------------------------------------------------

def test_sid_imports_cleanly():
    assert _sid() is not None


def test_sid_exposes_run_function():
    mod = _sid()
    assert hasattr(mod, 'run_sid_initial_climb')
    assert callable(mod.run_sid_initial_climb)


# ---------------------------------------------------------------------------
# calculate_isa_temperature — parametrized from JSON fixtures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_isa_temperature_from_json(case):
    mod = _sid()
    result = mod.calculate_isa_temperature(
        case["inputs"]["elev_m"],
        case["inputs"]["ref_temp_c"],
    )
    tol = case["expected"].get("tolerance", 0.05)

    if "temp_isa" in case["expected"]:
        assert abs(result["temp_isa"] - case["expected"]["temp_isa"]) <= tol, (
            f'{case["id"]}: temp_isa expected {case["expected"]["temp_isa"]}, '
            f'got {result["temp_isa"]:.3f}'
        )

    if "delta_isa" in case["expected"]:
        assert abs(result["delta_isa"] - case["expected"]["delta_isa"]) <= tol, (
            f'{case["id"]}: delta_isa expected {case["expected"]["delta_isa"]}, '
            f'got {result["delta_isa"]:.3f}'
        )


def test_isa_temp_decreases_with_altitude():
    """ISA temperature must decrease as elevation increases (lapse rate ~1.98°C/1000m)."""
    mod = _sid()
    prev_temp = None
    for elev in [0, 500, 1000, 2000, 3000]:
        r = mod.calculate_isa_temperature(elev, 15.0)
        if prev_temp is not None:
            assert r["temp_isa"] < prev_temp
        prev_temp = r["temp_isa"]


def test_isa_lapse_rate_per_1000m():
    """ISA lapse rate = 0.00198°C/m → 1.98°C per 1000 m."""
    mod = _sid()
    r0 = mod.calculate_isa_temperature(0, 15.0)
    r1 = mod.calculate_isa_temperature(1000, 15.0)
    assert abs((r0["temp_isa"] - r1["temp_isa"]) - 1.98) < 0.01


def test_isa_result_keys_present():
    mod = _sid()
    result = mod.calculate_isa_temperature(0, 15.0)
    for key in ("elevation", "temp_ref", "temp_isa", "delta_isa"):
        assert key in result, f'Missing key: {key}'


# ---------------------------------------------------------------------------
# calculate_tas_and_turn_parameters
# ---------------------------------------------------------------------------

def test_tas_and_turn_returns_dict():
    mod = _sid()
    result = mod.calculate_tas_and_turn_parameters(
        ias_kt=200, altitude_ft=5000, delta_isa=0, bank_angle_deg=25, wind_kt=30
    )
    assert isinstance(result, dict)


def test_tas_greater_than_ias():
    mod = _sid()
    ias = 180
    result = mod.calculate_tas_and_turn_parameters(ias, 5000, 0, 25, 30)
    assert result["tas_kt"] >= ias


def test_tas_increases_with_altitude():
    mod = _sid()
    low = mod.calculate_tas_and_turn_parameters(200, 2000, 0, 25, 30)
    high = mod.calculate_tas_and_turn_parameters(200, 10000, 0, 25, 30)
    assert high["tas_kt"] > low["tas_kt"]


def test_turn_radius_positive():
    mod = _sid()
    result = mod.calculate_tas_and_turn_parameters(200, 5000, 0, 25, 30)
    assert result["radius_of_turn_nm"] > 0


def test_rate_of_turn_does_not_exceed_3_deg_per_sec():
    """Rate of turn is capped at 3°/s per ICAO standard."""
    mod = _sid()
    result = mod.calculate_tas_and_turn_parameters(
        ias_kt=100, altitude_ft=1000, delta_isa=0, bank_angle_deg=45, wind_kt=0
    )
    assert result["rate_of_turn"] <= 3.0


# ---------------------------------------------------------------------------
# Departures smoke tests
# ---------------------------------------------------------------------------

def test_omnidirectional_sid_imports():
    mod = importlib.import_module('Q_Pansopy.modules.departures.omnidirectional_sid')
    assert mod is not None
    assert hasattr(mod, 'run_omnidirectional_sid')
