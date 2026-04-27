# -*- coding: utf-8 -*-
"""
Tests for pure-math calculation functions in wind_spiral.py.
No QGIS runtime required — stubs provided by conftest.
"""
import importlib
import math
import pytest


def _wind_spiral():
    return importlib.import_module('Q_Pansopy.modules.wind_spiral')


# ---------------------------------------------------------------------------
# ISA_temperature
# ---------------------------------------------------------------------------

def test_isa_temperature_sea_level_standard():
    """At sea level with standard temp (15°C) deviation should be 0."""
    mod = _wind_spiral()
    elev, ref, isa, delta = mod.ISA_temperature(0, 15)
    assert elev == 0
    assert ref == 15
    assert abs(isa - 15.0) < 0.01
    assert abs(delta) < 0.01


def test_isa_temperature_deviation_positive():
    """Warmer than ISA → positive deviation."""
    mod = _wind_spiral()
    _, _, isa, delta = mod.ISA_temperature(0, 25)
    assert delta > 0
    assert abs(delta - 10.0) < 0.01


def test_isa_temperature_deviation_negative():
    """Colder than ISA → negative deviation."""
    mod = _wind_spiral()
    _, _, isa, delta = mod.ISA_temperature(0, 5)
    assert delta < 0
    assert abs(delta + 10.0) < 0.01


def test_isa_temperature_lapse_rate():
    """ISA decreases with altitude at ~2°C per 1000 ft (0.00198/ft)."""
    mod = _wind_spiral()
    _, _, isa_0, _ = mod.ISA_temperature(0, 15)
    _, _, isa_1000, _ = mod.ISA_temperature(1000, 15)
    assert isa_1000 < isa_0
    assert abs((isa_0 - isa_1000) - 1.98) < 0.01


# ---------------------------------------------------------------------------
# tas_calculation
# ---------------------------------------------------------------------------

def test_tas_calculation_returns_five_values():
    mod = _wind_spiral()
    result = mod.tas_calculation(ias=200, altitude=5000, var=0, bank_angle=25)
    assert len(result) == 5


def test_tas_default_wind_speed_is_30():
    """Fix B9: default wind_speed must still be 30 for backward compat."""
    mod = _wind_spiral()
    k, tas, rot, radius, w = mod.tas_calculation(200, 5000, 0, 25)
    assert w == 30


def test_tas_explicit_wind_speed():
    """Fix B9: wind_speed parameter is used when passed."""
    mod = _wind_spiral()
    _, _, _, _, w = mod.tas_calculation(200, 5000, 0, 25, wind_speed=45)
    assert w == 45


def test_tas_greater_than_ias():
    """TAS must always be >= IAS (density effect)."""
    mod = _wind_spiral()
    ias = 180
    _, tas, _, _, _ = mod.tas_calculation(ias, altitude=10000, var=0, bank_angle=25)
    assert tas >= ias


def test_tas_increases_with_altitude():
    """Higher altitude → higher TAS for same IAS."""
    mod = _wind_spiral()
    _, tas_low, _, _, _ = mod.tas_calculation(200, 2000, 0, 25)
    _, tas_high, _, _, _ = mod.tas_calculation(200, 10000, 0, 25)
    assert tas_high > tas_low


@pytest.mark.parametrize("ias,alt,var,bank", [
    (180, 2000, 0, 15),
    (205, 5000, 10, 25),
    (250, 8000, -5, 30),
])
def test_tas_calculation_parametrized(ias, alt, var, bank):
    """Smoke test: tas_calculation should return positive values."""
    mod = _wind_spiral()
    k, tas, rot, radius, w = mod.tas_calculation(ias, alt, var, bank)
    assert k > 0
    assert tas > 0
    assert rot > 0
    assert radius > 0
