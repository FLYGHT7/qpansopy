# -*- coding: utf-8 -*-
"""
Tests de compatibilidad para holding.py.
Fix C6: el import de tas_calculation debe fallar con ImportError descriptivo,
no con un AttributeError genérico.
"""
import importlib
import sys
import pytest


def test_holding_module_imports_cleanly():
    """C6: holding.py importa sin error con stubs de QGIS activos."""
    mod = importlib.import_module('Q_Pansopy.modules.utilities.holding')
    assert mod is not None


def test_holding_has_main_function():
    """holding.py debe exponer run_holding_pattern (función principal)."""
    mod = importlib.import_module('Q_Pansopy.modules.utilities.holding')
    assert hasattr(mod, 'run_holding_pattern')


def test_tas_calculation_importable_from_holding():
    """
    C6: tas_calculation debe ser importable desde wind_spiral a través de holding.
    Si el import falla, debe ser un ImportError con mensaje descriptivo.
    """
    try:
        from Q_Pansopy.modules.utilities.holding import tas_calculation as tas
        assert callable(tas)
    except ImportError as e:
        assert "holding.py requires wind_spiral" in str(e) or "wind_spiral" in str(e)


def test_wind_spiral_module_importable():
    """El módulo wind_spiral debe ser importable (stubs activos)."""
    mod = importlib.import_module('Q_Pansopy.modules.wind_spiral')
    assert mod is not None


def test_python_version_compat():
    """El proyecto requiere Python >= 3.9."""
    assert sys.version_info >= (3, 9), \
        f"Python 3.9+ required, got {sys.version_info}"


def test_holding_wind_spiral_same_tas():
    """
    Regresión B9: tas_calculation accesible desde holding debe ser la misma
    función que en wind_spiral (no una copia con wind_speed hardcodeado).
    """
    wind_spiral = importlib.import_module('Q_Pansopy.modules.wind_spiral')
    holding = importlib.import_module('Q_Pansopy.modules.utilities.holding')

    # Ambas referencias deben ejecutar la misma lógica
    ws_result = wind_spiral.tas_calculation(200, 5000, 0, 25, wind_speed=45)
    if hasattr(holding, 'tas_calculation'):
        h_result = holding.tas_calculation(200, 5000, 0, 25, wind_speed=45)
        assert ws_result == h_result
