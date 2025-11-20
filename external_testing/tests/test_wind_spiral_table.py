import importlib


def test_wind_spiral_copy_parameters_table_formats_header_and_rows():
    mod = importlib.import_module('Q_Pansopy.modules.wind_spiral')

    params = {
        'adElev': 0,
        'adElev_unit': 'ft',
        'tempRef': 15,
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
    assert "Aerodrome Elevation" in table
    assert "Temperature Reference" in table
    assert "ISA Calculated" in table
    assert "ISA Variation" in table
    assert "IAS" in table
    assert "Altitude" in table
    assert "Wind Speed" in table