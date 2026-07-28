import importlib


def test_wind_spiral_copy_parameters_table_formats_header_and_rows():
    mod = importlib.import_module('Q_Pansopy.modules.wind_spiral')

    params = {
        'isaVar': 18.54984,
        'isa_source': 'calculated',
        'IAS': 205,
        'altitude': 800,
        'altitude_unit': 'ft',
        'bankAngle': 15,
        'w': 30,
        'turn_direction': 'R',
    }

    table = mod.copy_parameters_table(params)

    # Header
    assert "QPANSOPY WIND SPIRAL PARAMETERS" in table
    # Representative fields
    assert "ISA Variation" in table or "Isa Variation" in table
    assert "ISA Source" in table or "Isa Source" in table
    assert "IAS" in table or "Ias" in table
    assert "Altitude" in table
    assert "Wind Speed" in table


def test_wind_spiral_copy_parameters_table_reports_actual_isa_value():
    """Regression for issue #192: the table must show the ISA value that was
    actually used, not a value recomputed from stale adElev/tempRef defaults."""
    mod = importlib.import_module('Q_Pansopy.modules.wind_spiral')

    params = {'isaVar': 18.54984, 'isa_source': 'manual', 'IAS': 205, 'altitude': 800,
              'altitude_unit': 'ft', 'bankAngle': 15, 'w': 30, 'turn_direction': 'R'}

    table = mod.copy_parameters_table(params)

    assert "18.55" in table
    assert "Manual input" in table
