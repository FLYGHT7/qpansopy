# -*- coding: utf-8 -*-
"""Unit tests for the Circling Protection Area calculation engine.

Reference values are the numbers published by the PANS-OPS web calculator
(``html/calculators/circling_parameters.html``) for the scenario shown in its
screenshot: aerodrome elevation 92 ft, bank angle 20 deg, delta ISA 20 deg C,
protected height 1000 ft AGL, default per-category IAS.
"""
import importlib

import pytest

MOD = 'Q_Pansopy.modules.utilities.circling'

# cat -> (ias_kt, expected k, expected TAS+25, expected R_used, expected r NM,
#         expected circling radius NM)
CASES = {
    'A': (100, 1.0511, 130.1099, 3.0000, 0.6903, 1.6805),
    'B': (135, 1.0511, 166.8983, 2.3827, 1.1148, 2.6296),
    'C': (180, 1.0511, 214.1978, 1.8565, 1.8362, 4.1725),
    'D': (205, 1.0511, 240.4753, 1.6537, 2.3144, 5.2288),
    'E': (240, 1.0511, 277.2637, 1.4343, 3.0767, 6.8534),
}


def _mod():
    return importlib.import_module(MOD)


def test_module_exposes_public_api():
    mod = _mod()
    assert hasattr(mod, 'calc_circling_category')
    assert hasattr(mod, 'build_circling_area')
    assert hasattr(mod, 'run_circling')
    assert mod.S_CONST == {'A': 0.3, 'B': 0.4, 'C': 0.5, 'D': 0.6, 'E': 0.7}
    assert mod.IAS_DEFAULTS == {'A': 100, 'B': 135, 'C': 180, 'D': 205, 'E': 240}


@pytest.mark.parametrize('cat', sorted(CASES))
def test_calc_circling_category_matches_web_calculator(cat):
    mod = _mod()
    ias, exp_k, exp_tpw, exp_rused, exp_r, exp_circ = CASES[cat]

    res = mod.calc_circling_category(
        ias_kt=ias, prot_height_ft=1000, elev_ft=92, bank_deg=20, delta_isa=20,
        s_const=mod.S_CONST[cat],
    )

    assert res['h1_ft'] == pytest.approx(1092.0)
    assert res['k_factor'] == pytest.approx(exp_k, abs=1e-4)
    assert res['tas_plus_wind_kt'] == pytest.approx(exp_tpw, abs=1e-3)
    assert res['rate_turn_used'] == pytest.approx(exp_rused, abs=1e-3)
    assert res['nominal_radius_nm'] == pytest.approx(exp_r, abs=1e-3)
    assert res['circling_radius_nm'] == pytest.approx(exp_circ, abs=1e-3)


def test_rate_of_turn_is_capped_at_three_deg_per_second():
    mod = _mod()
    # CAT A at these inputs has an uncapped rate above 3 deg/s.
    res = mod.calc_circling_category(100, 1000, 92, 20, 20, 0.3)
    assert res['rate_turn_calc'] > 3.0
    assert res['rate_turn_used'] == 3.0


def test_metres_elevation_is_converted_to_feet():
    mod = _mod()
    in_ft = mod.calc_circling_category(180, 1000, 500, 20, 15, 0.5)
    # 500 ft ~= 152.4 m; feeding the equivalent metres via _elev_to_ft must match.
    elev_ft_from_m = mod._elev_to_ft(152.4, 'm')
    assert elev_ft_from_m == pytest.approx(500.0, abs=1e-6)
    in_from_m = mod.calc_circling_category(180, 1000, elev_ft_from_m, 20, 15, 0.5)
    assert in_from_m['circling_radius_nm'] == pytest.approx(
        in_ft['circling_radius_nm'], abs=1e-9)


# --- run_circling selection-count guard (Issue #223) ---------------------

class _RecordingMessageBar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _FakeIface:
    def __init__(self):
        self._bar = _RecordingMessageBar()

    def messageBar(self):
        return self._bar


class _FakeThresholdLayer:
    """Minimal stand-in: run_circling only needs selectedFeatures() before the
    count guard rejects it."""

    def __init__(self, selected_count):
        self._selected = [object() for _ in range(selected_count)]

    def selectedFeatures(self):
        return list(self._selected)


@pytest.mark.parametrize('selected_count', [0, 1])
def test_run_circling_requires_at_least_two_thresholds(selected_count):
    mod = _mod()
    iface = _FakeIface()
    layer = _FakeThresholdLayer(selected_count)

    result = mod.run_circling(iface, layer, {'ias_by_cat': {'A': 100}})

    assert result is False
    assert iface.messageBar().messages, 'expected a warning to be pushed'
    text = ' '.join(
        str(part) for args, _ in iface.messageBar().messages for part in args
    ).lower()
    assert 'at least 2' in text
