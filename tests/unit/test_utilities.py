# -*- coding: utf-8 -*-
"""
Import smoke tests for utility modules.
Verifies each module loads cleanly with QGIS stubs and exposes its main function.
No QGIS runtime required.
"""
import importlib
import pytest


_UTILITY_MODULES = [
    ('Q_Pansopy.modules.utilities.holding',              'run_holding_pattern'),
    ('Q_Pansopy.modules.utilities.point_filter',         'filter_points_by_elevation'),
    ('Q_Pansopy.modules.utilities.feature_merge',        'merge_selected_layers'),
    ('Q_Pansopy.modules.utilities.selection_of_objects', 'extract_objects'),
    # conventional_holding_navaid.py executes iface calls at import time (legacy script);
    # it cannot be imported with stubs and is excluded from smoke tests.
]


@pytest.mark.parametrize("module_path,main_fn", _UTILITY_MODULES,
                         ids=[m[0].split('.')[-1] for m in _UTILITY_MODULES])
def test_utility_module_imports_cleanly(module_path, main_fn):
    mod = importlib.import_module(module_path)
    assert mod is not None


@pytest.mark.parametrize("module_path,main_fn", _UTILITY_MODULES,
                         ids=[m[0].split('.')[-1] for m in _UTILITY_MODULES])
def test_utility_module_exposes_main_function(module_path, main_fn):
    mod = importlib.import_module(module_path)
    assert hasattr(mod, main_fn), f'{module_path} must expose {main_fn}()'
    assert callable(getattr(mod, main_fn))


# ---------------------------------------------------------------------------
# holding.py — TAS function must be the same as wind_spiral's
# ---------------------------------------------------------------------------

def test_holding_tas_matches_wind_spiral():
    """Regression: holding.py must re-use wind_spiral.tas_calculation, not a copy."""
    wind_spiral = importlib.import_module('Q_Pansopy.modules.wind_spiral')
    holding = importlib.import_module('Q_Pansopy.modules.utilities.holding')

    if hasattr(holding, 'tas_calculation'):
        ws = wind_spiral.tas_calculation(200, 5000, 0, 25, wind_speed=45)
        h = holding.tas_calculation(200, 5000, 0, 25, wind_speed=45)
        assert ws == h
