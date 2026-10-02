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
    assert "THR Elev" in table
    assert "Reverse Direction" in table
    assert "NO" in table


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
    assert "Reverse Direction" in table
    assert "NO" in table


def test_vss_parameter_tables_show_reversed_direction():
    params = {'reverse_direction': 'YES'}
    for module_name in ('vss_straight', 'vss_loc'):
        mod = importlib.import_module(f'Q_Pansopy.modules.{module_name}')
        table = mod.copy_parameters_table(params)
        assert "Reverse Direction" in table
        assert "YES" in table
