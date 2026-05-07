# -*- coding: utf-8 -*-
"""
Import smoke tests for all PBN modules.
Verifies each module loads cleanly with QGIS stubs and exposes its main function.
No QGIS runtime required.
"""
import importlib
import pytest


_PBN_MODULES = [
    ('Q_Pansopy.modules.pbn.lnav_initial_approach',     'run_initial_approach'),
    ('Q_Pansopy.modules.pbn.lnav_final_approach',       'run_final_approach'),
    ('Q_Pansopy.modules.pbn.lnav_intermediate_approach','run_intermediate_approach'),
    ('Q_Pansopy.modules.pbn.lnav_missed_approach',      'run_missed_approach'),
    ('Q_Pansopy.modules.pbn.pbn_rnav1_arrival',         'run_rnav1_arrival'),
    ('Q_Pansopy.modules.pbn.gnss_waypoint',             'run_gnss_waypoint'),
    ('Q_Pansopy.modules.pbn.rnav_sid_missed',           'run_rnav_sid_missed'),
    # pbn_target is tested in test_pbn_target.py — added after feat/138 is merged
]


@pytest.mark.parametrize("module_path,main_fn", _PBN_MODULES,
                         ids=[m[0].split('.')[-1] for m in _PBN_MODULES])
def test_pbn_module_imports_cleanly(module_path, main_fn):
    mod = importlib.import_module(module_path)
    assert mod is not None


@pytest.mark.parametrize("module_path,main_fn", _PBN_MODULES,
                         ids=[m[0].split('.')[-1] for m in _PBN_MODULES])
def test_pbn_module_exposes_main_function(module_path, main_fn):
    mod = importlib.import_module(module_path)
    assert hasattr(mod, main_fn), f'{module_path} must expose {main_fn}()'
    assert callable(getattr(mod, main_fn))


# ---------------------------------------------------------------------------
# _lnav_common shared helpers
# ---------------------------------------------------------------------------

def test_lnav_common_imports_cleanly():
    mod = importlib.import_module('Q_Pansopy.modules.pbn._lnav_common')
    assert mod is not None


def test_lnav_common_resolve_routing_layer():
    mod = importlib.import_module('Q_Pansopy.modules.pbn._lnav_common')
    assert hasattr(mod, '_resolve_routing_layer')
    assert callable(mod._resolve_routing_layer)


def test_lnav_common_select_segment_features():
    mod = importlib.import_module('Q_Pansopy.modules.pbn._lnav_common')
    assert hasattr(mod, '_select_segment_features')
    assert callable(mod._select_segment_features)
