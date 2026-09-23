"""QGIS runtime checks for the overhead facility tool."""

import pytest

pytest.importorskip('qgis')

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)

from Q_Pansopy.modules.conv.overhead_tolerance import run_overhead_tolerance  # noqa: E402


class _Bar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _Canvas:
    def __init__(self, crs):
        self._crs = crs

    def mapSettings(self):
        return self

    def destinationCrs(self):
        return self._crs


class _Iface:
    def __init__(self, crs):
        self.canvas = _Canvas(crs)
        self.bar = _Bar()

    def mapCanvas(self):
        return self.canvas

    def messageBar(self):
        return self.bar


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
def selected_layers():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    point = QgsVectorLayer('Point?crs=EPSG:32616', 'navaid', 'memory')
    station = QgsFeature()
    station.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000, 1600000)))
    point.dataProvider().addFeatures([station])
    point.selectByIds([next(point.getFeatures()).id()])
    line = QgsVectorLayer('LineString?crs=EPSG:32616', 'track', 'memory')
    track = QgsFeature()
    track.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(490000, 1600000), QgsPointXY(500000, 1600000)]))
    line.dataProvider().addFeatures([track])
    line.selectByIds([next(line.getFeatures()).id()])
    project.addMapLayer(point)
    project.addMapLayer(line)
    yield point, line
    project.removeAllMapLayers()


@pytest.mark.parametrize('navaid_type', ['VOR', 'NDB'])
def test_main_layer_and_optional_outputs(selected_layers, tmp_path, navaid_type):
    iface = _Iface(QgsCoordinateReferenceSystem('EPSG:32616'))
    point, line = selected_layers
    assert run_overhead_tolerance(iface, point, line, {
        'navaid_type': navaid_type,
        'aircraft_altitude_ft': 8000,
        'station_elevation_ft': 1500,
    })
    output = [layer for layer in QgsProject.instance().mapLayers().values()
              if 'Overhead_Tolerance' in layer.name()]
    assert len(output) == 1
    assert output[0].featureCount() == 1
    assert next(output[0].getFeatures()).geometry().isGeosValid()

    assert run_overhead_tolerance(iface, point, line, {
        'navaid_type': navaid_type,
        'aircraft_altitude_ft': 8000,
        'station_elevation_ft': 1500,
        'include_cone': True,
        'include_points': True,
        'export_kml': True,
        'output_dir': str(tmp_path),
    })
    assert len(list(tmp_path.glob('*.kml'))) == 3
    assert len([layer for layer in QgsProject.instance().mapLayers().values()
                if 'Construction_Points' in layer.name()]) == 1
    construction = next(layer for layer in QgsProject.instance().mapLayers().values()
                        if 'Construction_Points' in layer.name())
    assert construction.labelsEnabled()


def test_invalid_crs_leaves_project_unchanged(selected_layers):
    iface = _Iface(QgsCoordinateReferenceSystem('EPSG:4326'))
    point, line = selected_layers
    with pytest.raises(ValueError, match='projected CRS in metres'):
        run_overhead_tolerance(iface, point, line, {
            'aircraft_altitude_ft': 8000,
            'station_elevation_ft': 1500,
        })
    assert len(QgsProject.instance().mapLayers()) == 2


def test_source_crs_transform_and_failed_kml_keep_layers(selected_layers, tmp_path):
    _, line = selected_layers
    project = QgsProject.instance()
    wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
    utm = QgsCoordinateReferenceSystem('EPSG:32616')
    to_wgs84 = QgsCoordinateTransform(utm, wgs84, project)
    station_wgs84 = to_wgs84.transform(QgsPointXY(500000, 1600000))
    other_point = QgsVectorLayer('Point?crs=EPSG:4326', 'wgs84 station', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPointXY(station_wgs84))
    other_point.dataProvider().addFeatures([feature])
    other_point.selectByIds([next(other_point.getFeatures()).id()])
    project.addMapLayer(other_point)
    iface = _Iface(utm)
    assert run_overhead_tolerance(iface, other_point, line, {
        'aircraft_altitude_ft': 8000,
        'station_elevation_ft': 1500,
        'export_kml': True,
        'output_dir': str(tmp_path / 'missing'),
    })
    output = next(layer for layer in project.mapLayers().values()
                  if 'Overhead_Tolerance' in layer.name())
    assert output.crs() == utm
    assert output.featureCount() == 1
    assert any('Layers created, but' in args[1] for args, _ in iface.bar.messages)
