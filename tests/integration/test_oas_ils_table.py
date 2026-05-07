import importlib


def test_oas_ils_copy_parameters_table_includes_expected_rows():
    mod = importlib.import_module('Q_Pansopy.modules.oas_ils')

    params = {
        'THR_elev': 100.0,
        'delta': 0.0,
        'FAP_elev': 2000.0,
        'MOC_intermediate': 150.0,
        'oas_type': 'Both',
    }

    table = mod.copy_parameters_table(params)

    # Header
    assert "QPANSOPY OAS ILS PARAMETERS" in table
    # Sections and rows
    assert "Airport Data" in table
    assert "Approach Data" in table
    assert "Configuration" in table
    assert "Threshold Elevation" in table
    assert "Fap Elevation" in table or "FAP Elevation" in table