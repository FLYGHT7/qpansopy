import importlib


def test_vss_straight_copy_parameters_table_header_and_rows():
    mod = importlib.import_module('Q_Pansopy.modules.vss_straight')
    params = {
        'rwy_width': 45,
        'thr_elev': 1500,
        'thr_elev_unit': 'm',
        'strip_width': 140,
        'OCH': 100,
        'OCH_unit': 'm',
        'RDH': 15,
        'RDH_unit': 'm',
        'VPA': 3.0,
    }
    table = mod.copy_parameters_table(params)
    assert "QPANSOPY VSS STRAIGHT PARAMETERS" in table
    assert "Runway Data" in table
    assert "Approach Parameters" in table
    assert "Thr Elev" in table or "Threshold Elevation" in table


def test_vss_loc_copy_parameters_table_header_and_rows():
    mod = importlib.import_module('Q_Pansopy.modules.vss_loc')
    params = {
        'rwy_width': 45,
        'thr_elev': 1500,
        'thr_elev_unit': 'm',
        'strip_width': 140,
        'OCH': 100,
        'OCH_unit': 'm',
        'RDH': 15,
        'RDH_unit': 'm',
        'VPA': 3.0,
    }
    table = mod.copy_parameters_table(params)
    assert "QPANSOPY VSS LOC PARAMETERS" in table
    assert "Runway Data" in table
    assert "Approach Data" in table
    assert "Threshold Elevation" in table