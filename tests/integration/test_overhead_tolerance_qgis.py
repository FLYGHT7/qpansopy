"""QGIS runtime checks for overhead tolerance and its direction preview."""

import math

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication, QEvent, Qt  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication, QMainWindow  # noqa: E402

from Q_Pansopy.modules.conv.overhead_tolerance import run_overhead_tolerance  # noqa: E402
from Q_Pansopy.dockwidgets.conv.qpansopy_overhead_tolerance_dockwidget import (  # noqa: E402
    QPANSOPYOverheadToleranceDockWidget,
)


class _Bar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _Iface:
    def __init__(self, crs):
        self.window = QMainWindow()
        self.window.resize(1000, 600)
        self.canvas = QgsMapCanvas(self.window)
        self.window.setCentralWidget(self.canvas)
        self.canvas.setDestinationCrs(crs)
        self.canvas.setExtent(QgsRectangle(480000, 1580000, 520000, 1620000))
        self.bar = _Bar()

    def mainWindow(self):
        return self.window

    def activeLayer(self):
        return None

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
    project.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
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


@pytest.fixture
def dock(selected_layers):
    iface = _Iface(QgsCoordinateReferenceSystem('EPSG:32616'))
    widget = QPANSOPYOverheadToleranceDockWidget(iface)
    widget.navaidLayerComboBox.setLayer(selected_layers[0])
    widget.trackLayerComboBox.setLayer(selected_layers[1])
    iface.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, widget)
    iface.window.show()
    widget.show()
    QApplication.processEvents()
    yield widget
    widget.close()
    iface.window.close()
    widget.deleteLater()
    iface.window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def _marker_ring(dock):
    geometry = dock._direction_preview_band.asGeometry()
    assert not geometry.isEmpty()
    return geometry.asMultiPolygon()[0][0]


def _assert_marker(dock, station=(500000, 1600000), direction=(1, 0)):
    tip, left, right, closing = _marker_ring(dock)
    mupp = dock.iface.mapCanvas().mapUnitsPerPixel()
    norm = math.hypot(*direction)
    assert (tip.x(), tip.y()) == pytest.approx((
        station[0] + direction[0] / norm * 24 * mupp,
        station[1] + direction[1] / norm * 24 * mupp,
    ), abs=1e-7)
    assert ((left.x() + right.x()) / 2, (left.y() + right.y()) / 2) == pytest.approx(station, abs=1e-7)
    assert math.hypot(left.x() - station[0], left.y() - station[1]) / mupp == pytest.approx(12)
    assert math.hypot(right.x() - station[0], right.y() - station[1]) / mupp == pytest.approx(12)
    assert (closing.x(), closing.y()) == (tip.x(), tip.y())


@pytest.mark.parametrize('navaid_type', ['VOR', 'NDB'])
def test_preview_direction_reversal_and_no_side_effects(dock, selected_layers, navaid_type):
    dock.navaidTypeComboBox.setCurrentText(navaid_type)
    project = QgsProject.instance()
    ids = set(project.mapLayers())
    original = [next(layer.getFeatures()).geometry().asWkb() for layer in selected_layers]
    selections = [layer.selectedFeatureIds() for layer in selected_layers]
    _assert_marker(dock)
    dock.reverseDirectionCheckBox.setChecked(True)
    _assert_marker(dock, direction=(-1, 0))
    dock.reverseDirectionCheckBox.setChecked(False)
    _assert_marker(dock)
    assert set(project.mapLayers()) == ids
    assert [next(layer.getFeatures()).geometry().asWkb() for layer in selected_layers] == original
    assert [layer.selectedFeatureIds() for layer in selected_layers] == selections
    assert dock.iface.bar.messages == []
    assert dock.logTextEdit.toPlainText() == ''


@pytest.mark.parametrize('vertices,direction,tied', [
    ([(490000, 1590000), (499000, 1598000), (500000, 1600000)], (1000, 2000), False),
    ([(500000, 1600000), (502000, 1601000), (510000, 1610000)], (-2000, -1000), False),
    ([(499000, 1600000), (499000, 1599000), (501000, 1600000)], (2000, 1000), True),
])
@pytest.mark.parametrize('reverse', [False, True], ids=['normal', 'inverted'])
def test_preview_uses_adjacent_segment_and_matches_calculation(
        dock, selected_layers, vertices, direction, tied, reverse):
    _, line = selected_layers
    feature = next(line.getFeatures())
    geometry = QgsGeometry.fromPolylineXY([QgsPointXY(*point) for point in vertices])
    assert line.dataProvider().changeGeometryValues({feature.id(): geometry})
    line.dataChanged.emit()
    if reverse:
        direction = tuple(-value for value in direction)
    dock.reverseDirectionCheckBox.setChecked(reverse)
    _assert_marker(dock, direction=direction)
    assert dock.iface.bar.messages == []  # No warning from the preview for tied endpoints.
    dock.aircraftAltitudeLineEdit.setText('8000')
    dock.stationElevationLineEdit.setText('1500')
    dock.includePointsCheckBox.setChecked(True)
    dock.calculate()
    point_layer = next(layer for layer in QgsProject.instance().mapLayers().values()
                       if 'Construction_Points' in layer.name())
    points = {feature['Name']: feature.geometry().asPoint() for feature in point_layer.getFeatures()}
    dx = (points['V1'].x() + points['V3'].x() - points['V2'].x() - points['V4'].x()) / 2
    dy = (points['V1'].y() + points['V3'].y() - points['V2'].y() - points['V4'].y()) / 2
    assert dx * direction[1] - dy * direction[0] == pytest.approx(0, abs=1e-5)
    assert dx * direction[0] + dy * direction[1] > 0
    assert any('equidistant' in args[1] for args, _ in dock.iface.bar.messages) is tied
    _assert_marker(dock, direction=direction)  # Calculation retains the indicator.


def test_preview_size_tracks_zoom_and_ignores_altitudes(dock):
    for scale in (100000, 200000):
        dock.iface.canvas.zoomScale(scale)
        QApplication.processEvents()
        _assert_marker(dock)
    for altitude in ('', 'invalid', '-100'):
        dock.aircraftAltitudeLineEdit.setText(altitude)
        dock.stationElevationLineEdit.clear()
        _assert_marker(dock)


def test_preview_source_crs_and_canvas_crs(dock, selected_layers):
    station, track = selected_layers
    project = QgsProject.instance()
    utm = station.crs()
    wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
    to_wgs84 = QgsCoordinateTransform(utm, wgs84, project)
    replacement = QgsVectorLayer('Point?crs=EPSG:4326', 'WGS84 station', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPointXY(to_wgs84.transform(QgsPointXY(500000, 1600000))))
    replacement.dataProvider().addFeatures([feature])
    replacement.selectAll()
    project.addMapLayer(replacement)
    dock.navaidLayerComboBox.setLayer(replacement)
    _assert_marker(dock)
    assert station not in dock._connected_layers
    assert replacement in dock._connected_layers

    mercator = QgsCoordinateReferenceSystem('EPSG:3857')
    dock.iface.canvas.setDestinationCrs(mercator)
    transform = QgsCoordinateTransform(utm, mercator, project)
    center = transform.transform(QgsPointXY(500000, 1600000))
    previous = transform.transform(QgsPointXY(490000, 1600000))
    _assert_marker(dock, (center.x(), center.y()), (center.x() - previous.x(), center.y() - previous.y()))
    assert dock.iface.bar.messages == []
    assert next(track.getFeatures()).geometry().asPolyline()[-1] == QgsPointXY(500000, 1600000)


def test_preview_tracks_edits_provider_data_and_source_crs(dock, selected_layers):
    station, track = selected_layers
    original = dock._direction_preview_band.asGeometry().asWkb()
    track_id = next(track.getFeatures()).id()
    assert track.startEditing()
    assert track.changeGeometry(track_id, QgsGeometry.fromPolylineXY([
        QgsPointXY(490000, 1590000), QgsPointXY(500000, 1600000),
    ]))
    _assert_marker(dock, direction=(1, 1))
    assert track.rollBack()
    _assert_marker(dock)

    feature = next(station.getFeatures())
    assert station.dataProvider().changeGeometryValues({
        feature.id(): QgsGeometry.fromPointXY(QgsPointXY(499000, 1600000)),
    })
    station.dataChanged.emit()
    _assert_marker(dock, station=(499000, 1600000))
    assert dock._direction_preview_band.asGeometry().asWkb() != original
    station.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    assert dock._direction_preview_band.asGeometry().isEmpty()
    station.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    _assert_marker(dock, station=(499000, 1600000))
    assert dock.iface.bar.messages == []


@pytest.mark.parametrize('layer_index', [0, 1], ids=['station', 'track'])
def test_preview_requires_exactly_one_selected_feature(dock, selected_layers, layer_index):
    layer = selected_layers[layer_index]
    original_id = layer.selectedFeatureIds()[0]
    layer.removeSelection()
    assert dock._direction_preview_band.asGeometry().isEmpty()
    layer.selectByIds([original_id])
    _assert_marker(dock)

    feature = next(layer.getFeatures())
    feature.setId(-1)
    assert layer.startEditing()
    assert layer.addFeature(feature)
    layer.selectAll()
    assert dock._direction_preview_band.asGeometry().isEmpty()
    layer.selectByIds([original_id])
    _assert_marker(dock)
    assert layer.deleteFeature(original_id)
    assert dock._direction_preview_band.asGeometry().isEmpty()
    assert layer.rollBack()
    layer.selectAll()
    _assert_marker(dock)
    assert dock.iface.bar.messages == []


@pytest.mark.parametrize('layer_index,wkt', [
    (0, None),
    (0, 'Point EMPTY'),
    (0, 'MultiPoint ((500000 1600000), (500001 1600000))'),
    (0, 'LineString (500000 1600000, 500001 1600000)'),
    (0, 'Point (nan 1600000)'),
    (1, 'LineString EMPTY'),
    (1, 'MultiLineString ((490000 1600000, 500000 1600000))'),
    (1, 'Point (500000 1600000)'),
    (1, 'LineString (500000 1600000, 500000 1600000)'),
])
def test_preview_invalid_geometry_clears_without_messages(dock, selected_layers, layer_index, wkt):
    layer = selected_layers[layer_index]
    feature_id = next(layer.getFeatures()).id()
    geometry = QgsGeometry() if wkt is None else QgsGeometry.fromWkt(wkt)
    assert layer.dataProvider().changeGeometryValues({feature_id: geometry})
    layer.dataChanged.emit()
    assert dock._direction_preview_band.asGeometry().isEmpty()
    assert dock.iface.bar.messages == []
    assert dock.logTextEdit.toPlainText() == ''
    assert len(QgsProject.instance().mapLayers()) == 2


@pytest.mark.parametrize('crs', ['EPSG:4326', 'EPSG:2263'])
def test_preview_rejects_geographic_and_nonmetric_map_crs(dock, crs):
    dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    assert dock._direction_preview_band.asGeometry().isEmpty()
    assert dock.iface.bar.messages == []
    dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    _assert_marker(dock)


@pytest.mark.parametrize('combo_name', ['navaidLayerComboBox', 'trackLayerComboBox'])
def test_missing_input_layer_clears_preview_and_recovers(dock, combo_name):
    combo = getattr(dock, combo_name)
    layer = combo.currentLayer()
    combo.setAllowEmptyLayer(True)
    combo.setLayer(None)
    assert dock._direction_preview_band.asGeometry().isEmpty()
    combo.setLayer(layer)
    _assert_marker(dock)
    assert dock.iface.bar.messages == []


def test_hide_show_close_remove_marker_and_disconnect(dock, selected_layers):
    canvas = dock.iface.canvas
    project = QgsProject.instance()
    scene = canvas.scene()
    band = dock._direction_preview_band
    layers = list(selected_layers)
    receivers = [layer.receivers(layer.selectionChanged) for layer in layers]
    scale_receivers = canvas.receivers(canvas.scaleChanged)
    crs_receivers = canvas.receivers(canvas.destinationCrsChanged)
    project_receivers = project.receivers(project.layersWillBeRemoved)
    dock.hide()
    assert dock._direction_preview_band is None
    assert band not in scene.items()
    assert dock._connected_layers == []
    assert canvas.receivers(canvas.scaleChanged) == scale_receivers - 1
    assert canvas.receivers(canvas.destinationCrsChanged) == crs_receivers - 1
    assert project.receivers(project.layersWillBeRemoved) == project_receivers - 1
    assert [layer.receivers(layer.selectionChanged) for layer in layers] == [value - 1 for value in receivers]
    dock.reverseDirectionCheckBox.setChecked(True)
    dock.show()
    QApplication.processEvents()
    _assert_marker(dock, direction=(-1, 0))
    for _ in range(3):
        dock._on_preview_layers_changed()
    assert [layer.receivers(layer.selectionChanged) for layer in layers] == receivers
    dock.close()
    assert dock._direction_preview_band is None
    assert dock._connected_layers == []
    dock._start_preview()
    dock._stop_preview()
    assert dock._direction_preview_band is None


def test_remove_dock_cleans_marker_like_plugin_unload(dock):
    band = dock._direction_preview_band
    dock.iface.window.removeDockWidget(dock)
    QApplication.processEvents()
    assert dock._direction_preview_band is None
    assert dock._connected_layers == []
    assert band not in dock.iface.canvas.scene().items()


@pytest.mark.parametrize('layer_index', [0, 1], ids=['station', 'track'])
def test_removing_input_clears_marker(dock, selected_layers, layer_index):
    layer_id = selected_layers[layer_index].id()
    QgsProject.instance().removeMapLayer(layer_id)
    QApplication.processEvents()
    assert dock._direction_preview_band.asGeometry().isEmpty()
    assert all(layer.id() != layer_id for layer in dock._connected_layers)
    assert dock._removing_layer_ids == set()


def test_taking_and_reinserting_input_recovers_preview(dock, selected_layers):
    project = QgsProject.instance()
    station = selected_layers[0]
    retained = project.takeMapLayer(station)
    assert retained is station
    assert dock._direction_preview_band.asGeometry().isEmpty()
    assert dock._removing_layer_ids == set()
    project.addMapLayer(retained)
    dock.navaidLayerComboBox.setLayer(retained)
    _assert_marker(dock)
    assert len(dock._connected_layers) == 2
    assert len({id(layer) for layer in dock._connected_layers}) == 2
