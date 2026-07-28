# -*- coding: utf-8 -*-
"""
Regression tests for issue #192: the Wind Spiral output feature's stored
'parameters' JSON must match the values actually used for the calculation,
and must record whether the ISA Variation was typed in manually or produced
by the ISA Calculator dialog.
"""
import importlib
import json


def _mod():
    return importlib.import_module('Q_Pansopy.modules.wind_spiral')


def test_altitude_unit_is_always_stored_as_feet():
    """altitude is normalised to feet by the caller before this is built --
    the stored unit must always say 'ft' regardless of what the user typed,
    since storing anything else would silently disagree with the number."""
    mod = _mod()
    parameters_json = mod._build_wind_spiral_parameters_json(
        IAS=250, altitude_ft=2624.67, bankAngle=25, w=30, isa_var=0,
        turn_direction='L', isa_calculation_metadata={'method': 'manual'}
    )
    parsed = json.loads(parameters_json)

    assert parsed['altitude'] == '2624.67'
    assert parsed['altitude_unit'] == 'ft'


def test_manual_isa_source_recorded_without_extra_fields():
    mod = _mod()
    parameters_json = mod._build_wind_spiral_parameters_json(
        IAS=250, altitude_ft=5000, bankAngle=25, w=30, isa_var=18.54984,
        turn_direction='L', isa_calculation_metadata={'method': 'manual'}
    )
    parsed = json.loads(parameters_json)

    assert parsed['isa_var'] == '18.55'
    assert parsed['isa_source'] == 'manual'
    assert 'isa_source_elevation' not in parsed


def test_calculated_isa_source_includes_provenance():
    mod = _mod()
    metadata = {
        'method': 'calculated',
        'elevation_original': 39.92,
        'elevation_unit': 'ft',
        'temperature_reference': 15.0,
    }
    parameters_json = mod._build_wind_spiral_parameters_json(
        IAS=250, altitude_ft=5000, bankAngle=25, w=30, isa_var=18.54984,
        turn_direction='L', isa_calculation_metadata=metadata
    )
    parsed = json.loads(parameters_json)

    assert parsed['isa_var'] == '18.55'
    assert parsed['isa_source'] == 'calculated'
    assert parsed['isa_source_elevation'] == 39.92
    assert parsed['isa_source_elevation_unit'] == 'ft'
    assert parsed['isa_source_temp_ref'] == 15.0


def test_missing_isa_calculation_metadata_defaults_to_manual():
    """No metadata at all (e.g. an older caller) must not crash and must
    default to 'manual' rather than silently claiming 'calculated'."""
    mod = _mod()
    parameters_json = mod._build_wind_spiral_parameters_json(
        IAS=250, altitude_ft=5000, bankAngle=25, w=30, isa_var=0,
        turn_direction='L', isa_calculation_metadata=None
    )
    parsed = json.loads(parameters_json)

    assert parsed['isa_source'] == 'manual'
