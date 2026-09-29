"""QGIS output checks for Holding Point E and its construction lines."""

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProject, QgsVectorLayer,
)

from Q_Pansopy.modules.utilities import holding  # noqa: E402


class _Iface:
    def __init__(self, crs='EPSG:32616'):
        self.crs = QgsCoordinateReferenceSystem(crs)
        self.messages = []

    def mapCanvas(self):
        return self

    def mapSettings(self):
        return self

    def destinationCrs(self):
        return self.crs

    def messageBar(self):
        return self

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


@pytest.fixture
def routing():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    layer = QgsVectorLayer('LineString?crs=EPSG:32616', 'route', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(500000, 1600000), QgsPointXY(501000, 1600000)]))
    layer.dataProvider().addFeatures([feature])
    layer.selectByIds([next(layer.getFeatures()).id()])
    yield layer
    project.removeAllMapLayers()


def _run(routing, turn='R', show_circles=False, iface=None):
    return holding.run_holding_pattern(iface or _Iface(), routing, {
        'IAS': 220, 'altitude': 10000, 'altitude_unit': 'ft',
        'isa_var': 15, 'bank_angle': 25, 'leg_time_min': 1,
        'turn': turn, 'show_circles': show_circles,
    })


def test_point_e_and_construction_layers_use_actual_table_values(routing):
    result = _run(routing, show_circles=False)
    assert result
    point_layer = result['point_e_layer']
    construction_layer = result['construction_layer']
    assert point_layer.name() == 'Point_E'
    assert construction_layer.name() == 'Axis_Bounding_Box'
    assert point_layer.featureCount() == 1
    assert construction_layer.featureCount() == 8
    assert point_layer.crs() == routing.crs()
    assert point_layer.labelsEnabled()
    assert all(layer.name() != 'HoldingWindCircles'
               for layer in QgsProject.instance().mapLayers().values())

    point = next(point_layer.getFeatures())
    xe_nm, ye_nm = holding.calculate_holding_entry_offsets_nm(result['summary'])
    assert point['point'] == 'E'
    assert point['XE_nm'] == pytest.approx(xe_nm)
    assert point['YE_nm'] == pytest.approx(ye_nm)
    assert point['x'] == pytest.approx(result['point_e'].x())
    assert point['y'] == pytest.approx(result['point_e'].y())
    assert point.geometry().asPoint() == result['point_e']
    assert {feature['type'] for feature in construction_layer.getFeatures()} == {
        'MIN_LONGITUDINAL', 'MAX_LONGITUDINAL',
        'MIN_LATERAL', 'MAX_LATERAL', 'x-AXIS', 'y-AXIS',
        'E_OFFSET_X', 'E_OFFSET_Y',
    }
    assert all(feature['length_m'] > 0 and
               feature['length_nm'] == pytest.approx(feature['length_m'] / 1852)
               for feature in construction_layer.getFeatures())
    offsets = {feature['type']: feature.geometry()
               for feature in construction_layer.getFeatures()
               if feature['type'].startswith('E_OFFSET')}
    assert offsets['E_OFFSET_X'].intersects(point.geometry())
    assert offsets['E_OFFSET_Y'].intersects(point.geometry())


def test_left_turn_mirrors_point_e_across_inbound_track(routing):
    right = _run(routing, turn='R', show_circles=True)
    right_point = QgsPointXY(right['point_e'])
    left = _run(routing, turn='L', show_circles=False)
    left_point = left['point_e']
    assert right_point.y() < 1600000
    assert left_point.y() > 1600000
    assert next(left['point_e_layer'].getFeatures())['XE_nm'] == pytest.approx(
        next(right['point_e_layer'].getFeatures())['XE_nm'])
    assert left['point_e_layer'].featureCount() == 1


def test_missing_basic_area_keeps_nominal_without_point_e(routing, monkeypatch):
    monkeypatch.setattr(holding, '_build_wind_circles', lambda *args: [])
    result = _run(routing)
    assert result
    assert result['layer'].featureCount() == 4
    assert result['point_e'] is None
    assert result['point_e_layer'] is None
    assert result['construction_layer'] is None
    names = {layer.name() for layer in QgsProject.instance().mapLayers().values()}
    assert 'Point_E' not in names
    assert 'Axis_Bounding_Box' not in names


def test_mismatched_canvas_crs_skips_point_e_with_warning(routing):
    iface = _Iface('EPSG:3857')
    result = _run(routing, iface=iface)
    assert result
    assert result['point_e'] is None
    assert result['point_e_layer'] is None
    assert result['construction_layer'] is None
    assert any('Point E requires' in args[1] for args, _ in iface.messages)
