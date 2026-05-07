import pytest
import importlib


@pytest.mark.skip(reason="Q_Pansopy.modules.selection_of_objects eliminado en Fase 0 (era un duplicado de utilities/selection_of_objects.py que no tiene copy_parameters_table)")
def test_selection_of_objects_copy_parameters_table_header_and_rows():
    mod = importlib.import_module('Q_Pansopy.modules.selection_of_objects')

    params = {
        'marker_size': 4,
        'point_layer_name': 'Obstacles',
        'surface_layer_name': 'OAS Area',
    }

    table = mod.copy_parameters_table(params)

    assert "QPANSOPY OBJECT SELECTION PARAMETERS" in table
    assert "Visualization" in table
    assert "Input Layers" in table
    assert "Marker Size" in table
    assert "Point Layer" in table
    assert "Surface Layer" in table