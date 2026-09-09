# -*- coding: utf-8 -*-
"""Unit tests for the Circling Protection Area calculation engine.

Reference values are the numbers published by the PANS-OPS web calculator
(``html/calculators/circling_parameters.html``) for the scenario shown in its
screenshot: aerodrome elevation 92 ft, bank angle 20 deg, delta ISA 20 deg C,
protected height 1000 ft AGL, default per-category IAS.
"""
import importlib
import json

import pytest

MOD = 'Q_Pansopy.modules.utilities.circling'

# cat -> (ias_kt, expected k, expected TAS+25, expected R_used, expected r NM,
#         expected circling radius NM)
CASES = {
    'A': (100, 1.0511, 130.1099, 3.0000, 0.6903, 1.6805),
    'B': (135, 1.0511, 166.8983, 2.3827, 1.1148, 2.6296),
    'C': (180, 1.0511, 214.1978, 1.8565, 1.8362, 4.1725),
    'D': (205, 1.0511, 240.4753, 1.6537, 2.3144, 5.2288),
    'E': (240, 1.0511, 277.2637, 1.4343, 3.0767, 6.8534),
}


def _mod():
    return importlib.import_module(MOD)


def test_module_exposes_public_api():
    mod = _mod()
    assert hasattr(mod, 'calc_circling_category')
    assert hasattr(mod, 'build_circling_area')
    assert hasattr(mod, 'run_circling')
    assert mod.S_CONST == {'A': 0.3, 'B': 0.4, 'C': 0.5, 'D': 0.6, 'E': 0.7}
    assert mod.IAS_DEFAULTS == {'A': 100, 'B': 135, 'C': 180, 'D': 205, 'E': 240}


@pytest.mark.parametrize('cat', sorted(CASES))
def test_calc_circling_category_matches_web_calculator(cat):
    mod = _mod()
    ias, exp_k, exp_tpw, exp_rused, exp_r, exp_circ = CASES[cat]

    res = mod.calc_circling_category(
        ias_kt=ias, prot_height_ft=1000, elev_ft=92, bank_deg=20, delta_isa=20,
        s_const=mod.S_CONST[cat],
    )

    assert res['protected_height_ft'] == pytest.approx(1000.0)
    assert res['h1_ft'] == pytest.approx(1092.0)
    assert res['k_factor'] == pytest.approx(exp_k, abs=1e-4)
    assert res['tas_plus_wind_kt'] == pytest.approx(exp_tpw, abs=1e-3)
    assert res['rate_turn_used'] == pytest.approx(exp_rused, abs=1e-3)
    assert res['nominal_radius_nm'] == pytest.approx(exp_r, abs=1e-3)
    assert res['circling_radius_nm'] == pytest.approx(exp_circ, abs=1e-3)


def test_rate_of_turn_is_capped_at_three_deg_per_second():
    mod = _mod()
    # CAT A at these inputs has an uncapped rate above 3 deg/s.
    res = mod.calc_circling_category(100, 1000, 92, 20, 20, 0.3)
    assert res['rate_turn_calc'] > 3.0
    assert res['rate_turn_used'] == 3.0


def test_metres_elevation_is_converted_to_feet():
    mod = _mod()
    in_ft = mod.calc_circling_category(180, 1000, 500, 20, 15, 0.5)
    # 500 ft ~= 152.4 m; feeding the equivalent metres via _elev_to_ft must match.
    elev_ft_from_m = mod._elev_to_ft(152.4, 'm')
    assert elev_ft_from_m == pytest.approx(500.0, abs=1e-6)
    in_from_m = mod.calc_circling_category(180, 1000, elev_ft_from_m, 20, 15, 0.5)
    assert in_from_m['circling_radius_nm'] == pytest.approx(
        in_ft['circling_radius_nm'], abs=1e-9)


@pytest.mark.parametrize(
    'params,cat,expected',
    [
        ({'prot_height_ft_by_cat': {'A': 900, 'B': 1200}}, 'A', 900.0),
        ({'prot_height_ft_by_cat': {'A': 900, 'B': 1200}}, 'B', 1200.0),
        ({'prot_height_ft_by_cat': {'A': 900}}, 'C', 1000.0),
        ({'prot_height_ft': 850}, 'D', 850.0),
        ({}, 'E', 1000.0),
    ],
)
def test_protected_height_resolves_per_category_with_legacy_fallback(
        params, cat, expected):
    mod = _mod()

    assert mod._protected_height_for_category(params, cat) == expected


def test_invalid_category_height_identifies_the_category():
    mod = _mod()

    with pytest.raises(ValueError, match='Invalid protected height for CAT B'):
        mod._protected_height_for_category(
            {'prot_height_ft_by_cat': {'B': 'not-a-height'}}, 'B')


def test_category_height_changes_altitude_and_radius():
    mod = _mod()

    low = mod.calc_circling_category(180, 900, 28, 20, 15, 0.5)
    high = mod.calc_circling_category(180, 1400, 28, 20, 15, 0.5)

    assert low['protected_height_ft'] == 900
    assert high['protected_height_ft'] == 1400
    assert low['h1_ft'] == pytest.approx(928.0)
    assert high['h1_ft'] == pytest.approx(1428.0)
    assert high['k_factor'] > low['k_factor']
    assert high['circling_radius_nm'] > low['circling_radius_nm']


def test_manual_isa_provenance_contains_only_source():
    mod = _mod()

    assert mod._isa_provenance({}) == {'isa_source': 'manual'}
    assert mod._isa_provenance({
        'isa_calculation_metadata': {'method': 'manual'}
    }) == {'isa_source': 'manual'}


def test_calculated_isa_provenance_is_normalized_for_output():
    mod = _mod()
    params = {
        'isa_calculation_metadata': {
            'method': 'calculated',
            'elevation_original': 1000,
            'elevation_unit': 'm',
            'temperature_reference': 14,
            'isa_temperature': 8.5039368,
        }
    }

    assert mod._isa_provenance(params) == {
        'isa_source': 'calculated',
        'isa_source_elevation': 1000,
        'isa_source_elevation_unit': 'm',
        'isa_source_temp_ref': 14,
        'isa_temperature_c': 8.5039368,
    }


# --- run_circling selection-count guard (Issue #223) ---------------------

class _RecordingMessageBar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _FakeIface:
    def __init__(self):
        self._bar = _RecordingMessageBar()

    def messageBar(self):
        return self._bar


class _FakeThresholdLayer:
    """Minimal stand-in: run_circling only needs selectedFeatures() before the
    count guard rejects it."""

    def __init__(self, selected_count):
        self._selected = [object() for _ in range(selected_count)]

    def selectedFeatures(self):
        return list(self._selected)


@pytest.mark.parametrize('selected_count', [0, 1])
def test_run_circling_requires_at_least_two_thresholds(selected_count):
    mod = _mod()
    iface = _FakeIface()
    layer = _FakeThresholdLayer(selected_count)

    result = mod.run_circling(iface, layer, {'ias_by_cat': {'A': 100}})

    assert result is False
    assert iface.messageBar().messages, 'expected a warning to be pushed'
    text = ' '.join(
        str(part) for args, _ in iface.messageBar().messages for part in args
    ).lower()
    assert 'at least 2' in text


def test_run_circling_propagates_category_heights_to_output(monkeypatch):
    mod = _mod()
    message_bar = _RecordingMessageBar()
    built_radii = []

    class _MapCrs:
        @staticmethod
        def authid():
            return 'EPSG:32616'

        @staticmethod
        def isGeographic():
            return False

    class _MapSettings:
        @staticmethod
        def destinationCrs():
            return _MapCrs()

    class _MapCanvas:
        @staticmethod
        def mapSettings():
            return _MapSettings()

        @staticmethod
        def zoomToSelected(layer):
            return None

    class _Iface:
        @staticmethod
        def mapCanvas():
            return _MapCanvas()

        @staticmethod
        def messageBar():
            return message_bar

    class _ThresholdLayer:
        @staticmethod
        def selectedFeatures():
            return [object(), object()]

    class _Area:
        @staticmethod
        def isEmpty():
            return False

    class _Feature:
        def setGeometry(self, geometry):
            self.geometry = geometry

        def setAttributes(self, attributes):
            self.attributes = attributes

    class _Provider:
        def __init__(self):
            self.features = []

        @staticmethod
        def addAttributes(fields):
            return True

        def addFeatures(self, features):
            self.features.extend(features)
            return True

    class _VectorLayer:
        def __init__(self, *args):
            self.provider = _Provider()

        def dataProvider(self):
            return self.provider

        @staticmethod
        def updateFields():
            return None

        @staticmethod
        def updateExtents():
            return None

        @staticmethod
        def selectAll():
            return None

        @staticmethod
        def removeSelection():
            return None

    class _Project:
        added_layers = []

        @classmethod
        def instance(cls):
            return cls()

        def addMapLayer(self, layer):
            self.added_layers.append(layer)

    def _build_area(points, radius_m):
        built_radii.append(radius_m)
        return _Area()

    monkeypatch.setattr(mod, 'QgsProject', _Project)
    monkeypatch.setattr(mod, 'QgsVectorLayer', _VectorLayer)
    monkeypatch.setattr(mod, 'QgsFeature', _Feature)
    monkeypatch.setattr(
        mod, '_threshold_points_map_crs', lambda *args: [object(), object()])
    monkeypatch.setattr(mod, 'build_circling_area', _build_area)
    monkeypatch.setattr(mod, '_apply_categorized_style', lambda layer: None)
    monkeypatch.setattr(mod, 'register_parameters_action', lambda layer: None)

    result = mod.run_circling(
        _Iface(), _ThresholdLayer(), {
            'elev': 28,
            'elev_unit': 'ft',
            'bank_deg': 20,
            'delta_isa': 15,
            'ias_by_cat': {'A': 100, 'C': 180},
            'prot_height_ft_by_cat': {'A': 900, 'C': 1300},
            'isa_calculation_metadata': {
                'method': 'calculated',
                'elevation_original': 28,
                'elevation_unit': 'ft',
                'temperature_reference': 20,
                'isa_temperature': 14.94456,
            },
        })

    assert result['summary']['A']['protected_height_ft'] == 900
    assert result['summary']['C']['protected_height_ft'] == 1300
    assert result['summary']['A']['h1_ft'] == pytest.approx(928.0)
    assert result['summary']['C']['h1_ft'] == pytest.approx(1328.0)
    assert built_radii == pytest.approx([
        result['summary']['C']['circling_radius_nm'] * mod.NM2M,
        result['summary']['A']['circling_radius_nm'] * mod.NM2M,
    ])

    features = result['layer'].provider.features
    attributes_by_cat = {feature.attributes[0]: feature.attributes
                         for feature in features}
    assert attributes_by_cat['A'][2] == 900
    assert attributes_by_cat['C'][2] == 1300
    assert json.loads(attributes_by_cat['A'][15])['protected_height_ft'] == 900
    assert json.loads(attributes_by_cat['C'][15])['protected_height_ft'] == 1300
    stored = json.loads(attributes_by_cat['A'][15])
    assert stored['isa_source'] == 'calculated'
    assert stored['isa_source_elevation'] == 28
    assert stored['isa_source_elevation_unit'] == 'ft'
    assert stored['isa_source_temp_ref'] == 20
    assert stored['isa_temperature_c'] == pytest.approx(14.94456)
