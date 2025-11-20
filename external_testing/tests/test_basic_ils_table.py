import importlib


def test_basic_ils_copy_parameters_table_formats_header_and_rows():
    mod = importlib.import_module('Q_Pansopy.modules.basic_ils')

    params = {
        'thr_elev': 1500,
        'thr_elev_unit': 'm',
    }

    table = mod.copy_parameters_table(params)

    # Header
    assert "QPANSOPY BASIC ILS PARAMETERS" in table
    # Row exists
    assert "Threshold Elevation" in table