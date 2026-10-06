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
from Q_Pansopy.modules.conv import radial_bearing_intersection  # noqa: E402


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


def _construction_outputs():
    return [layer for layer in QgsProject.instance().mapLayers().values()
            if 'Radial_Bearing_Construction_Lines' in layer.name()]


@pytest.mark.parametrize('enabled', [False, True])
def test_optional_construction_lines_match_polygon_and_attributes(points, enabled):
    crs = QgsCoordinateReferenceSystem('EPSG:32616')
    iface = _Iface(crs)
    params = {'tracking_type': 'ILS', 'crossing_type': 'NDB'}
    assert run_radial_bearing_intersection(iface, *points, params)
    assert _construction_outputs() == []
    baseline = next(_outputs()[0].getFeatures())
    QgsProject.instance().removeMapLayer(_outputs()[0])
    params['include_construction_lines'] = enabled
    assert run_radial_bearing_intersection(iface, *points, params)
    polygon_layer = _outputs()[0]
    polygon = next(polygon_layer.getFeatures())
    assert polygon.geometry().asWkb() == baseline.geometry().asWkb()
    assert polygon.attributes() == baseline.attributes()
    lines = _construction_outputs()
    assert len(lines) == int(enabled)
    if not enabled:
        return
    construction = lines[0]
    assert construction.name() == 'ILS_NDB_Radial_Bearing_Construction_Lines'
    assert construction.crs() == crs
    assert construction.featureCount() == 6
    assert construction.fields().names() == ['Role', 'Navaid', 'OffsetDeg']
    assert {(feature['Role'], feature['Navaid'], feature['OffsetDeg'])
            for feature in construction.getFeatures()} == {
        ('Tracking', 'ILS', 0), ('Tracking', 'ILS', -2.4), ('Tracking', 'ILS', 2.4),
        ('Intersecting', 'NDB', 0), ('Intersecting', 'NDB', -6.2), ('Intersecting', 'NDB', 6.2),
    }
    for feature in construction.getFeatures():
        geometry = feature.geometry()
        assert geometry.isGeosValid()
        assert geometry.length() > 0
        start = geometry.asPolyline()[0]
        assert (start.x(), start.y()) == (
            (500000, 1600000) if feature['Role'] == 'Tracking' else (510000, 1590000))
        assert geometry.distance(polygon.geometry()) < 1e-7
        if feature['OffsetDeg'] == 0:
            assert geometry.intersection(polygon.geometry()).length() > 0
    symbol = construction.renderer().symbol()
    assert symbol.color().name() == '#e6b800'
    assert symbol.width() == pytest.approx(0.3)
    tree_layers = QgsProject.instance().layerTreeRoot().findLayers()
    assert [node.layerId() for node in tree_layers[:2]] == [construction.id(), polygon_layer.id()]


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


def test_construction_layer_failure_creates_no_partial_output(points, monkeypatch):
    def fail_construction(*args):
        raise RuntimeError('Could not create construction lines layer')

    monkeypatch.setattr(radial_bearing_intersection, '_construction_layer', fail_construction)
    initial_layers = set(QgsProject.instance().mapLayers())
    with pytest.raises(RuntimeError, match='Could not create construction lines layer'):
        run_radial_bearing_intersection(
            _Iface(QgsCoordinateReferenceSystem('EPSG:32616')), *points,
            {'include_construction_lines': True})
    assert set(QgsProject.instance().mapLayers()) == initial_layers


def test_invalid_crs_and_parallel_facilities_create_no_output(points):
    with pytest.raises(ValueError, match='projected CRS in metres'):
        run_radial_bearing_intersection(
            _Iface(QgsCoordinateReferenceSystem('EPSG:4326')), *points,
            {'include_construction_lines': True})
    assert _outputs() == []
    assert _construction_outputs() == []
    project = QgsProject.instance()
    project.removeMapLayer(points[1])
    parallel = _point_layer('parallel', (505000, 1600000))
    with pytest.raises(ValueError, match='too close to parallel'):
        run_radial_bearing_intersection(
            _Iface(QgsCoordinateReferenceSystem('EPSG:32616')),
            points[0], parallel, points[2], {'include_construction_lines': True})
    assert _outputs() == []
    assert _construction_outputs() == []


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
        'include_construction_lines': True,
    })
    assert len(_outputs()) == 1
    assert _outputs()[0].crs() == utm
    construction = _construction_outputs()[0]
    assert construction.crs() == utm
    crossing_lines = [feature for feature in construction.getFeatures()
                      if feature['Role'] == 'Intersecting']
    assert len(crossing_lines) == 3
    for feature in crossing_lines:
        start = feature.geometry().asPolyline()[0]
        assert start.x() == pytest.approx(510000, abs=1e-5)
        assert start.y() == pytest.approx(1590000, abs=1e-5)
    assert any('Layer created, but' in args[1] for args, _ in iface.bar.messages)


def test_multiple_selected_features_are_rejected(points):
    extra = QgsFeature()
    extra.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500500, 1600000)))
    points[0].dataProvider().addFeatures([extra])
    points[0].selectAll()
    with pytest.raises(ValueError, match='exactly one tracking station'):
        run_radial_bearing_intersection(
            _Iface(QgsCoordinateReferenceSystem('EPSG:32616')), *points,
            {'include_construction_lines': True})
    assert _outputs() == []
    assert _construction_outputs() == []


@pytest.mark.parametrize('include_lines', [False, True])
def test_simplified_dock_loads_and_creates_tolerance(points, include_lines):
    iface = _Iface(QgsCoordinateReferenceSystem('EPSG:32616'))
    window = QMainWindow()
    iface.mainWindow = lambda: window
    dock = QPANSOPYRadialBearingIntersectionDockWidget(iface)
    assert not dock.includeConstructionLinesCheckBox.isChecked()
    dock.includeConstructionLinesCheckBox.setChecked(include_lines)
    assert [dock.trackingTypeComboBox.itemText(index) for index in range(3)] == [
        'VOR', 'ILS', 'NDB']
    assert [dock.crossingTypeComboBox.itemText(index) for index in range(3)] == [
        'VOR', 'ILS', 'NDB']
    for name in ('directionLabel', 'flightDirectionComboBox', 'crsHintLabel',
                 'outputGroup', 'exportKmlCheckBox', 'outputFolderLineEdit',
                 'browseButton'):
        assert not hasattr(dock, name)
    dock.trackingLayerComboBox.setLayer(points[0])
    dock.crossingLayerComboBox.setLayer(points[1])
    dock.fixLayerComboBox.setLayer(points[2])
    dock.crossingTypeComboBox.setCurrentText('NDB')
    dock.calculateButton.click()
    outputs = _outputs()
    assert len(outputs) == 1
    assert len(_construction_outputs()) == int(include_lines)
    feature = next(outputs[0].getFeatures())
    assert feature.geometry().isGeosValid()
    assert feature['TrackType'] == 'VOR'
    assert feature['CrossType'] == 'NDB'
    assert feature['Direction'] == 'outbound'
    expected_nm = 10000 * math.tan(math.radians(6.2)) / 1852
    assert feature['EarlyNM'] == pytest.approx(expected_nm)
    assert feature['LateNM'] == pytest.approx(expected_nm)
    assert 'Early:' in dock.logTextEdit.toPlainText()
    assert 'Radial/bearing fix tolerance created.' in dock.logTextEdit.toPlainText()
    dock.close()
