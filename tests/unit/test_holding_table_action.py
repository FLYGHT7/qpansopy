"""Holding table rows shared by the dock and the layer action."""

import importlib


def test_holding_table_values_use_existing_dock_precision():
    holding = importlib.import_module('Q_Pansopy.modules.utilities.holding')
    summary = {
        'IAS_kt': 195, 'Altitude_ft': 10000.4, 'ISA_var_C': -1.25,
        'Bank_deg': 25, 'Leg_min': 1.234, 'Leg_nm': 3.456,
        'Turn': 'R', 'TAS_kt': 247.891, 'Rate_deg_s': 2.34567,
        'Radius_nm': 0.98765,
    }
    assert holding.format_holding_table_parameters(summary) == {
        'IAS_kt': '195.0', 'Altitude_ft': '10000', 'ISA_var_C': '-1.2',
        'Bank_deg': '25.0', 'Leg_min': '1.23', 'Leg_nm': '3.46',
        'Turn': 'R', 'TAS_kt': '247.89', 'Rate_deg_s': '2.346',
        'Radius_nm': '0.988',
    }
