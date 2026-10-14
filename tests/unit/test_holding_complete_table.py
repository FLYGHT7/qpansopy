"""Regression tests for the full Doc 8168 Holding parameter table."""

import importlib
import re

import pytest


def _holding():
    return importlib.import_module('Q_Pansopy.modules.utilities.holding')


def _summary(bank=25.0):
    mod = _holding()
    k, tas, rate, radius, _wind = mod.tas_calculation(220, 10000, 15, bank)
    return {
        'IAS_kt': 220.0,
        'Altitude_ft': 10000.0,
        'ISA_var_C': 15.0,
        'Bank_deg': bank,
        'Leg_min': 1.0,
        'Turn': 'R',
        'TAS_kt': tas,
        'Rate_deg_s': rate,
        'Radius_nm': radius,
        'K_factor': k,
    }


def test_complete_table_has_all_33_reference_lines_and_sample_values():
    mod = _holding()
    html, plain = mod.format_holding_complete_table(_summary())

    calculation_table = re.search(
        r'<table class="holding-calculations".*?</table>', html, re.DOTALL
    ).group()
    calculation_rows = re.findall(r'<tr>(.*?)</tr>', calculation_table)
    assert len(calculation_rows) == 34
    assert re.findall(r'<th[^>]*>(.*?)</th>', calculation_rows[0]) == [
        'Line', 'Parameter', 'Calculations using non-SI units',
    ]
    assert all(
        len(re.findall(r'<td[^>]*>', row)) == 3
        for row in calculation_rows[1:]
    )
    data_table = re.search(
        r'<table class="holding-data".*?</table>', html, re.DOTALL
    ).group()
    data_rows = re.findall(r'<tr>(.*?)</tr>', data_table)
    assert len(data_rows) == 7
    assert re.findall(r'<th[^>]*>(.*?)</th>', data_rows[0]) == ['DATA']
    assert re.findall(r'<th[^>]*>(.*?)</th>', data_rows[1]) == [
        'Input', 'Non-SI Units',
    ]
    assert all(len(re.findall(r'<td[^>]*>', row)) == 2 for row in data_rows[2:])

    for label in ('K', 'V', 'v', 'R', 'r', 'h', 'w', "w′", 'E₄₅',
                  'g₁ = g₃', 'W₁ = W₃', 'XE', 'YE'):
        assert label in calculation_table
    assert 'Calculations using SI units' not in html
    assert 'Calculations using non-SI units' in html
    assert 'SI Formula' not in plain
    assert 'SI Value' not in plain
    assert ' km/h' not in html
    assert ' km/s' not in html
    assert ' km' not in html
    assert '263.07 kt' in html
    assert '2.16 NM' in html
    assert '13.28 NM' in html
    assert '6.94 NM' in html
    assert 'V = K × IAS' not in html
    assert 'XE = ' not in html
    assert 'Input\tNon-SI Units' in plain
    assert 'Line\tParameter\tValue' in plain
    assert 'V = K × IAS' not in plain
    assert 'XE = ' not in plain
    assert plain.count('\n') == 41

    plain_rows = plain.splitlines()
    assert len(plain_rows[2].split('\t')) == 2
    assert all(len(row.split('\t')) == 2 for row in plain_rows[2:7])
    assert all(len(row.split('\t')) == 3 for row in plain_rows[9:])


def test_table_uses_actual_bank_angle_without_rate_cap():
    mod = _holding()
    html_25, _ = mod.format_holding_complete_table(_summary(25.0))
    html_35, _ = mod.format_holding_complete_table(_summary(45.0))

    assert '25.0°' in html_25
    assert '45.0°' in html_35
    assert _summary(45.0)['Rate_deg_s'] > 3.0
    assert 'whichever is less' not in html_35
    assert 'Calculations using SI units' not in html_35


def test_view_builder_returns_complete_then_short_views():
    mod = _holding()
    views = mod.build_holding_table_views(_summary())

    assert [name for name, _content in views] == ['Complete', 'Short']
    assert 'XE' in views[0][1].html
    assert 'IAS_kt' in views[1][1].html


def test_layer_snapshot_is_versioned_and_keeps_numeric_inputs():
    mod = _holding()
    snapshot = mod.build_holding_feature_parameters(_summary())

    assert snapshot['calculation_type'] == 'Holding Pattern'
    assert snapshot['schema_version'] == 2
    assert snapshot['summary']['TAS_kt'] == pytest.approx(263.0674, abs=0.001)
