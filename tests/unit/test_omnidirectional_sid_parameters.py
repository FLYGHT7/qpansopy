# -*- coding: utf-8 -*-
"""
Regression tests for issue #177: OMNI SID output features must carry the
input parameters used to generate them (previously only recoverable from
the PDG baked into the layer name).
"""
import importlib
import json


def test_build_omni_parameters_json_round_trips_all_keys():
    mod = importlib.import_module('Q_Pansopy.modules.departures.omnidirectional_sid')

    params = {'der_elevation_unit': 'm', 'cwy_distance_unit': 'm'}
    parameters_json = mod._build_omni_parameters_json(
        params, der_elevation_m=39.92, pdg_percent=3.3, tna_ft=600, msa_ft=1800,
        cwy_distance_m=60, allow_turns_before_der='NO',
        include_construction_points='NO', reverse_direction='YES',
    )
    parsed = json.loads(parameters_json)

    assert parsed['der_elevation_m'] == 39.92
    assert parsed['der_elevation_unit'] == 'm'
    assert parsed['pdg'] == 3.3
    assert parsed['TNA_ft'] == 600
    assert parsed['msa_ft'] == 1800
    assert parsed['cwy_distance_m'] == 60
    assert parsed['cwy_distance_unit'] == 'm'
    assert parsed['allow_turns_before_der'] == 'NO'
    assert parsed['include_construction_points'] == 'NO'
    assert parsed['reverse_direction'] == 'YES'
    assert parsed['calculation_type'] == 'Omnidirectional SID'
    assert 'calculation_date' in parsed


def test_create_polygon_surface_stores_parameters_json(monkeypatch):
    mod = importlib.import_module('Q_Pansopy.modules.departures.omnidirectional_sid')

    class _FakeFeature:
        def __init__(self):
            self.attributes = None
            self._geom = object()

        def setGeometry(self, geom):
            pass

        def setAttributes(self, attrs):
            self.attributes = attrs

        def geometry(self):
            return self._geom

    created = []

    def _fake_feature_factory():
        feature = _FakeFeature()
        created.append(feature)
        return feature

    monkeypatch.setattr(mod, 'QgsFeature', _fake_feature_factory)

    class _FakeProvider:
        def addFeatures(self, feats):
            pass

    class _FakeLayer:
        def dataProvider(self):
            return _FakeProvider()

    surfaces_dict = {}
    parameters_json = '{"pdg": 3.3}'

    mod.create_polygon_surface(
        'Area 1', [1, 2, 3], _FakeLayer(), surfaces_dict, parameters_json,
        distance_m=1234.5678
    )

    assert len(created) == 1
    assert created[0].attributes == ['Area 1', 1234.5678, parameters_json]
    assert surfaces_dict['Area 1'] is created[0].geometry()


def test_create_polygon_surface_distance_none_when_not_applicable(monkeypatch):
    mod = importlib.import_module('Q_Pansopy.modules.departures.omnidirectional_sid')

    class _FakeFeature:
        def __init__(self):
            self.attributes = None

        def setGeometry(self, geom):
            pass

        def setAttributes(self, attrs):
            self.attributes = attrs

        def geometry(self):
            return object()

    created = []
    monkeypatch.setattr(mod, 'QgsFeature', lambda: created.append(_FakeFeature()) or created[-1])

    class _FakeLayer:
        def dataProvider(self):
            class _P:
                def addFeatures(self, feats):
                    pass
            return _P()

    parameters_json = '{"pdg": 3.3}'
    mod.create_polygon_surface(
        'Before DER', [1, 2, 3], _FakeLayer(), {}, parameters_json
    )

    assert created[0].attributes == ['Before DER', None, parameters_json]
