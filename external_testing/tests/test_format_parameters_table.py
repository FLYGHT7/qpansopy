from Q_Pansopy.utils import format_parameters_table


def test_format_parameters_table_nested_sections():
    params = {
        'airport_data': {
            'aerodrome_elevation': {'value': 1500, 'unit': 'm'},
            'temperature_reference': {'value': 15, 'unit': '°C'},
            'isa_calculated': {'value': 4.8, 'unit': '°C'},
            'isa_variation': {'value': -10.2, 'unit': '°C'},
        },
        'flight_params': {
            'IAS': {'value': 205, 'unit': 'kt'},
            'altitude': {'value': 8000, 'unit': 'ft'},
            'bank_angle': {'value': 15, 'unit': '°'},
        },
        'wind_data': {
            'wind_speed': {'value': 30, 'unit': 'kt'},
            'turn_direction': {'value': 'R', 'unit': ''},
        },
    }
    sections = {
        'aerodrome_elevation': 'Airport Data',
        'temperature_reference': 'Airport Data',
        'isa_calculated': 'Airport Data',
        'isa_variation': 'Airport Data',
        'IAS': 'Flight Parameters',
        'altitude': 'Flight Parameters',
        'bank_angle': 'Flight Parameters',
        'wind_speed': 'Wind Data',
        'turn_direction': 'Wind Data',
    }

    out = format_parameters_table("QPANSOPY WIND SPIRAL PARAMETERS", params, sections)
    # Header
    assert "QPANSOPY WIND SPIRAL PARAMETERS" in out
    # Sections
    assert "Airport Data" in out
    assert "Flight Parameters" in out
    assert "Wind Data" in out
    # Representative rows
    assert "Aerodrome Elevation" in out
    assert "Temperature Reference" in out
    assert "IAS" in out
    assert "Wind Speed" in out