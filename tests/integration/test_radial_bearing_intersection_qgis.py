"""QGIS runtime checks for radial/bearing intersection fix tolerance."""

import math

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.PyQt.QtWidgets import QMainWindow  # noqa: E402

from Q_Pansopy.dockwidgets.conv.qpansopy_radial_bearing_intersection_dockwidget import (  # noqa: E402
    QPANSOPYRadialBearingIntersectionDockWidget,
)
from Q_Pansopy.modules.conv.radial_bearing_intersection import (  # noqa: E402
    run_radial_bearing_intersection,
)


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

    def mainWindow(self):
        return QMainWindow()

    def activeLayer(self):
        return None


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


def _point_layer(name, coordinates, crs='EPSG:32616'):
    layer = QgsVectorLayer('Point?crs={0}'.format(crs), name, 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*coordinates)))
    layer.dataProvider().addFeatures([feature])
    layer.selectByIds([next(layer.getFeatures()).id()])
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def points():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    tracking = _point_layer('tracking', (500000, 1600000))
    crossing = _point_layer('crossing', (510000, 1590000))
    fix = _point_layer('fix', (510000, 1600000))
    yield tracking, crossing, fix
    project.removeAllMapLayers()


def _outputs():
    return [layer for layer in QgsProject.instance().mapLayers().values()
            if 'Radial_Bearing_Tolerance' in layer.name()]


def test_polygon_attributes_and_kml(points, tmp_path):
    iface = _Iface(QgsCoordinateReferenceSystem('EPSG:32616'))
    reported = []
    assert run_radial_bearing_intersection(iface, *points, {
        'tracking_type': 'VOR', 'crossing_type': 'NDB',
        'flight_direction': 'outbound', 'on_result': reported.append,
        'export_kml': True, 'output_dir': str(tmp_path),
    })
    outputs = _outputs()
    assert len(outputs) == 1
    assert outputs[0].featureCount() == 1
    feature = next(outputs[0].getFeatures())
    assert feature.geometry().isGeosValid()
    assert feature['TrackType'] == 'VOR'
    assert feature['CrossType'] == 'NDB'
    assert feature['TrackDeg'] == pytest.approx(5.2)
    assert feature['CrossDeg'] == pytest.approx(6.2)
    expected_nm = 10000 * math.tan(math.radians(6.2)) / 1852
    assert feature['EarlyNM'] == pytest.approx(expected_nm)
    assert feature['LateNM'] == pytest.approx(expected_nm)
    assert reported[0].early_nm == pytest.approx(expected_nm)
    assert len(list(tmp_path.glob('*.kml'))) == 1


def test_invalid_crs_and_parallel_facilities_create_no_output(points):
    with pytest.raises(ValueError, match='projected CRS in metres'):
        run_radial_bearing_intersection(
            _Iface(QgsCoordinateReferenceSystem('EPSG:4326')), *points)
    assert _outputs() == []
    project = QgsProject.instance()
    project.removeMapLayer(points[1])
    parallel = _point_layer('parallel', (505000, 1600000))
    with pytest.raises(ValueError, match='too close to parallel'):
        run_radial_bearing_intersection(
            _Iface(QgsCoordinateReferenceSystem('EPSG:32616')),
            points[0], parallel, points[2])
    assert _outputs() == []


def test_source_crs_transform_and_kml_failure_keep_layer(points, tmp_path):
    project = QgsProject.instance()
    utm = QgsCoordinateReferenceSystem('EPSG:32616')
    wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
    transformed = QgsCoordinateTransform(utm, wgs84, project).transform(
        QgsPointXY(510000, 1590000))
    project.removeMapLayer(points[1])
    crossing = _point_layer('crossing_wgs84', (transformed.x(), transformed.y()),
                            'EPSG:4326')
    iface = _Iface(utm)
    assert run_radial_bearing_intersection(iface, points[0], crossing, points[2], {
        'export_kml': True, 'output_dir': str(tmp_path / 'missing'),
    })
    assert len(_outputs()) == 1
    assert _outputs()[0].crs() == utm
    assert any('Layer created, but' in args[1] for args, _ in iface.bar.messages)


def test_multiple_selected_features_are_rejected(points):
    extra = QgsFeature()
    extra.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500500, 1600000)))
    points[0].dataProvider().addFeatures([extra])
    points[0].selectAll()
    with pytest.raises(ValueError, match='exactly one tracking station'):
        run_radial_bearing_intersection(
            _Iface(QgsCoordinateReferenceSystem('EPSG:32616')), *points)
    assert _outputs() == []


def test_dock_loads_with_fixed_types_and_direction(points):
    iface = _Iface(QgsCoordinateReferenceSystem('EPSG:32616'))
    window = QMainWindow()
    iface.mainWindow = lambda: window
    dock = QPANSOPYRadialBearingIntersectionDockWidget(iface)
    assert [dock.trackingTypeComboBox.itemText(index) for index in range(3)] == [
        'VOR', 'ILS', 'NDB']
    assert [dock.crossingTypeComboBox.itemText(index) for index in range(3)] == [
        'VOR', 'ILS', 'NDB']
    assert [dock.flightDirectionComboBox.itemText(index) for index in range(2)] == [
        'Outbound', 'Inbound']
    assert not dock.outputFolderLineEdit.isEnabled()
    dock.close()
