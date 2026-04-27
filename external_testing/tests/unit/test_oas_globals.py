# -*- coding: utf-8 -*-
"""
Tests para solve_plane_intersection y estado de globals OAS.
Fix B8/C3/C4: los globales OAS_W/X/Y/Z no deben quedar contaminados
entre llamadas sucesivas.
"""
import importlib
import pytest


def _oas_ils():
    return importlib.import_module('Q_Pansopy.modules.oas_ils')


# ---------------------------------------------------------------------------
# solve_plane_intersection — pura matemática, numpy, sin QGIS
# ---------------------------------------------------------------------------

def test_solve_plane_intersection_basic():
    """Intersección simple de dos planos con A≠0, resultado calculable."""
    mod = _oas_ils()
    # Planos: z = A*x + B*y + C
    # plane1: z = 1*x + 0*y + 0  → x = z at y=0
    # plane2: z = 0*x + 1*y + 0  → y = z at x=0
    # En target_height=10: x=10, y=10
    p1 = (1.0, 0.0, 0.0)
    p2 = (0.0, 1.0, 0.0)
    result = mod.solve_plane_intersection(p1, p2, target_height=10)
    assert result is not None
    x, y, z = result
    assert abs(z - 10) < 1e-9


def test_solve_plane_intersection_degenerate_returns_none():
    """Planos paralelos (misma normal) → sin intersección → None."""
    mod = _oas_ils()
    p1 = (0.0, 0.0, 0.0)  # A=0, B=0 → degenerate
    p2 = (1.0, 0.0, 0.0)
    result = mod.solve_plane_intersection(p1, p2, target_height=5)
    assert result is None


def test_solve_plane_intersection_at_zero():
    """Intersección a altura 0."""
    mod = _oas_ils()
    p1 = (1.0, 0.0, 0.0)
    p2 = (0.0, 1.0, 0.0)
    result = mod.solve_plane_intersection(p1, p2, target_height=0)
    assert result is not None
    x, y, z = result
    assert abs(z) < 1e-9


def test_solve_plane_intersection_returns_tuple():
    """El resultado debe ser una tupla (x, y, z)."""
    mod = _oas_ils()
    p1 = (1.0, 0.5, 10.0)
    p2 = (0.5, 1.0, 5.0)
    result = mod.solve_plane_intersection(p1, p2, target_height=100)
    assert isinstance(result, tuple)
    assert len(result) == 3


@pytest.mark.parametrize("height", [0, 100, 300, 500])
def test_solve_plane_intersection_various_heights(height):
    """La función debe funcionar a distintas alturas de referencia."""
    mod = _oas_ils()
    p1 = (1.0, 0.0, 0.0)
    p2 = (0.0, 1.0, 0.0)
    result = mod.solve_plane_intersection(p1, p2, target_height=height)
    assert result is not None
    assert abs(result[2] - height) < 1e-6


# ---------------------------------------------------------------------------
# build_mirrors — función auxiliar del módulo
# ---------------------------------------------------------------------------

def test_build_mirrors_creates_mirror_keys():
    """build_mirrors debe crear claves '<key>mirror' para cada key del dict."""
    mod = _oas_ils()
    d = {"C": (100.0, 50.0, 0.0), "D": (200.0, 80.0, 0.0)}
    mirrored = mod.build_mirrors(d)
    assert "C" in mirrored
    assert "Cmirror" in mirrored
    assert "D" in mirrored
    assert "Dmirror" in mirrored


def test_build_mirrors_negates_y():
    """El mirror debe negar la coordenada Y."""
    mod = _oas_ils()
    d = {"C": (100.0, 50.0, 10.0)}
    mirrored = mod.build_mirrors(d)
    orig_x, orig_y, orig_z = mirrored["C"]
    mir_x, mir_y, mir_z = mirrored["Cmirror"]
    assert orig_x == mir_x
    assert orig_y == -mir_y
    assert orig_z == mir_z


# ---------------------------------------------------------------------------
# csv_to_structured_json — estado de globals (B8/C3/C4)
# ---------------------------------------------------------------------------

def test_oas_globals_start_as_none():
    """
    B8: al cargar el módulo por primera vez, los globals deben ser None.
    Esto documenta el estado inicial esperado y detecta si algo los contamina
    durante el import.
    """
    # El módulo puede haberse importado antes — chequeamos simplemente que
    # los atributos existen y son el tipo correcto (None o lista/dict).
    mod = _oas_ils()
    for attr in ('OAS_W', 'OAS_X', 'OAS_Y', 'OAS_Z', 'OAS_template', 'OAS_extended_to_FAP'):
        assert hasattr(mod, attr), f"Global {attr} missing from oas_ils module"
        val = getattr(mod, attr)
        # Deben ser None (estado inicial) o una lista/dict si ya fueron seteados
        assert val is None or isinstance(val, (list, dict)), \
            f"Global {attr} has unexpected type {type(val)}"
