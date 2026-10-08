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
from qgis.gui import QgsMapCanvas  # noqa: E402
from Q_Pansopy.qt_compat import Qt_RightDockWidgetArea  # noqa: E402

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


class _Iface:
    def __init__(self, crs):
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas(self.window)
        self.canvas.setDestinationCrs(crs)
        self.window.setCentralWidget(self.canvas)
        self.bar = _Bar()

    def mapCanvas(self):
        return self.canvas

    def messageBar(self):
        return self.bar

    def mainWindow(self):
        return self.window

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


@pytest.fixture
def preview_dock(points):
    iface = _Iface(QgsCoordinateReferenceSystem('EPSG:32616'))
    dock = QPANSOPYRadialBearingIntersectionDockWidget(iface)
    for combo, layer in zip(
            (dock.trackingLayerComboBox, dock.crossingLayerComboBox,
             dock.fixLayerComboBox), points):
        combo.setLayer(layer)
    iface.window.addDockWidget(Qt_RightDockWidgetArea, dock)
    iface.window.show()
    QgsApplication.processEvents()
    yield dock
    dock.close()
    iface.window.close()


@pytest.mark.parametrize('tracking_type', ['VOR', 'ILS', 'NDB'])
@pytest.mark.parametrize('crossing_type', ['VOR', 'ILS', 'NDB'])
@pytest.mark.parametrize('include_lines', [False, True])
def test_live_preview_matches_created_geometry(
        preview_dock, tracking_type, crossing_type, include_lines):
    dock = preview_dock
    before_layers = set(QgsProject.instance().mapLayers())
    dock.trackingTypeComboBox.setCurrentText(tracking_type)
    dock.crossingTypeComboBox.setCurrentText(crossing_type)
    dock.includeConstructionLinesCheckBox.setChecked(include_lines)
    preview = dock._preview_band.asGeometry()
    lines = dock._construction_preview_band.asGeometry()
    assert not preview.isEmpty()
    assert lines.isEmpty() == (not include_lines)
    assert set(QgsProject.instance().mapLayers()) == before_layers
    assert dock.iface.bar.messages == []
    assert dock.logTextEdit.toPlainText() == ''

    dock.calculate()
    output = next(_outputs()[0].getFeatures()).geometry()
    assert output.symDifference(preview).area() < 1e-5
    if include_lines:
        paths = lines.asMultiPolyline()
        features = list(_construction_outputs()[0].getFeatures())
        assert len(paths) == len(features) == 6
        for path, feature in zip(paths, features):
            assert QgsGeometry.fromPolylineXY(path).asWkb() == feature.geometry().asWkb()
    assert dock._preview_band.asGeometry().isEmpty()
    assert dock._construction_preview_band.asGeometry().isEmpty()
    dock.crossingTypeComboBox.setCurrentText('VOR' if crossing_type != 'VOR' else 'ILS')
    assert not dock._preview_band.asGeometry().isEmpty()


def test_preview_tracks_types_construction_and_geometry_edits(preview_dock, points):
    dock = preview_dock
    original = dock._preview_band.asGeometry().asWkb()
    dock.trackingTypeComboBox.setCurrentText('ILS')
    assert dock._preview_band.asGeometry().asWkb() != original
    original = dock._preview_band.asGeometry().asWkb()
    dock.crossingTypeComboBox.setCurrentText('NDB')
    assert dock._preview_band.asGeometry().asWkb() != original
    dock.includeConstructionLinesCheckBox.setChecked(True)
    polygon = dock._preview_band.asGeometry().asWkb()
    assert len(dock._construction_preview_band.asGeometry().asMultiPolyline()) == 6
    dock.includeConstructionLinesCheckBox.setChecked(False)
    assert dock._construction_preview_band.asGeometry().isEmpty()
    assert dock._preview_band.asGeometry().asWkb() == polygon
    assert points[0].startEditing()
    feature_id = points[0].selectedFeatureIds()[0]
    assert points[0].changeGeometry(
        feature_id, QgsGeometry.fromPointXY(QgsPointXY(499000, 1599000)))
    assert dock._preview_band.asGeometry().asWkb() != polygon
    assert dock.iface.bar.messages == []


def test_preview_selection_fallback_ambiguity_and_replacement(preview_dock, points):
    dock = preview_dock
    for layer in points:
        layer.removeSelection()
    assert not dock._preview_band.asGeometry().isEmpty()
    tracking = points[0]
    assert tracking.startEditing()
    extra = QgsFeature()
    extra.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(499000, 1599000)))
    assert tracking.addFeature(extra)
    assert dock._preview_band.asGeometry().isEmpty()
    tracking.selectAll()
    assert dock._preview_band.asGeometry().isEmpty()
    tracking.selectByIds([extra.id()])
    assert not dock._preview_band.asGeometry().isEmpty()
    replacement = _point_layer('replacement', (498000, 1598000))
    before = dock._preview_band.asGeometry().asWkb()
    dock.trackingLayerComboBox.setLayer(replacement)
    assert dock._preview_band.asGeometry().asWkb() != before
    assert tracking not in dock._connected_layers
    assert replacement in dock._connected_layers
    assert dock.iface.bar.messages == []


def test_preview_connections_are_deduplicated(preview_dock, points):
    dock = preview_dock
    receivers = [layer.receivers(layer.selectionChanged) for layer in points]
    for _ in range(3):
        dock._on_preview_layers_changed()
    assert [layer.receivers(layer.selectionChanged) for layer in points] == receivers
    dock.crossingLayerComboBox.setLayer(points[0])
    assert len(dock._connected_layers) == 2
    assert len({id(layer) for layer in dock._connected_layers}) == 2
    assert dock._preview_band.asGeometry().isEmpty()
    dock.crossingLayerComboBox.setLayer(points[1])
    assert len(dock._connected_layers) == 3
    assert not dock._preview_band.asGeometry().isEmpty()


def test_preview_tracks_source_crs_and_provider_data_changes(preview_dock, points):
    dock = preview_dock
    layer = points[0]
    original = dock._preview_band.asGeometry().asWkb()
    layer.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    assert dock._preview_band.asGeometry().isEmpty()
    layer.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    assert dock._preview_band.asGeometry().asWkb() == original
    assert layer.dataProvider().changeGeometryValues({
        layer.selectedFeatureIds()[0]: QgsGeometry.fromPointXY(QgsPointXY(499000, 1599000)),
    })
    layer.dataChanged.emit()
    assert dock._preview_band.asGeometry().asWkb() != original
    assert dock.iface.bar.messages == []


def test_preview_tracks_deleting_and_adding_the_only_feature(preview_dock, points):
    dock = preview_dock
    dock.includeConstructionLinesCheckBox.setChecked(True)
    layer = points[1]
    assert layer.startEditing()
    assert layer.deleteFeature(layer.selectedFeatureIds()[0])
    assert dock._preview_band.asGeometry().isEmpty()
    assert dock._construction_preview_band.asGeometry().isEmpty()
    replacement = QgsFeature()
    replacement.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(510000, 1590000)))
    assert layer.addFeature(replacement)
    assert not dock._preview_band.asGeometry().isEmpty()
    assert not dock._construction_preview_band.asGeometry().isEmpty()
    assert dock.iface.bar.messages == []


@pytest.mark.parametrize('failure', [
    'missing', 'ambiguous', 'empty', 'multipart', 'parallel', 'coincident',
    'geographic', 'feet', 'transform',
])
def test_invalid_live_inputs_clear_both_bands_without_messages(preview_dock, points, failure):
    dock = preview_dock
    dock.includeConstructionLinesCheckBox.setChecked(True)
    assert not dock._preview_band.asGeometry().isEmpty()
    before_layers = set(QgsProject.instance().mapLayers())
    if failure == 'missing':
        dock.trackingLayerComboBox.setLayer(None)
    elif failure in ('geographic', 'feet'):
        dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem(
            'EPSG:4326' if failure == 'geographic' else 'EPSG:2263'))
    elif failure == 'transform':
        bad = _point_layer('invalid_latitude', (-87, 100), 'EPSG:4326')
        before_layers.add(bad.id())
        dock.crossingLayerComboBox.setLayer(bad)
    else:
        layer = points[1]
        assert layer.startEditing()
        if failure == 'ambiguous':
            extra = QgsFeature()
            extra.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(509000, 1590000)))
            assert layer.addFeature(extra)
            layer.selectAll()
        else:
            geometry = {
                'empty': QgsGeometry(),
                'multipart': QgsGeometry.fromWkt('MultiPoint ((510000 1590000), (511000 1590000))'),
                'parallel': QgsGeometry.fromPointXY(QgsPointXY(505000, 1600000)),
                'coincident': QgsGeometry.fromPointXY(QgsPointXY(500000, 1600000)),
            }[failure]
            assert layer.changeGeometry(layer.selectedFeatureIds()[0], geometry)
    assert dock._preview_band.asGeometry().isEmpty()
    assert dock._construction_preview_band.asGeometry().isEmpty()
    assert dock.iface.bar.messages == []
    assert dock.logTextEdit.toPlainText() == ''
    assert set(QgsProject.instance().mapLayers()) == before_layers
    dock.calculate()
    assert _outputs() == []
    assert _construction_outputs() == []
    assert dock.iface.bar.messages


def test_preview_transforms_source_and_canvas_crs(preview_dock, points):
    dock = preview_dock
    original = dock._preview_band.asGeometry()
    project = QgsProject.instance()
    transform = QgsCoordinateTransform(
        points[1].crs(), QgsCoordinateReferenceSystem('EPSG:4326'), project)
    source = transform.transform(points[1].selectedFeatures()[0].geometry().asPoint())
    replacement = _point_layer('geographic_crossing', (source.x(), source.y()), 'EPSG:4326')
    dock.crossingLayerComboBox.setLayer(replacement)
    assert original.symDifference(dock._preview_band.asGeometry()).area() < 1e-4
    dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    preview = dock._preview_band.asGeometry()
    assert not preview.isEmpty()
    assert preview.asWkb() != original.asWkb()
    dock.calculate()
    output = next(_outputs()[0].getFeatures()).geometry()
    assert output.symDifference(preview).area() < 1e-4
    dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    assert dock._preview_band.asGeometry().isEmpty()
    dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    assert not dock._preview_band.asGeometry().isEmpty()


def test_hide_show_close_release_bands_and_connections(preview_dock, points):
    dock = preview_dock
    dock.includeConstructionLinesCheckBox.setChecked(True)
    polygon_band = dock._preview_band
    line_band = dock._construction_preview_band
    scene = dock.iface.canvas.scene()
    canvas = dock.iface.canvas
    project = QgsProject.instance()
    canvas_receivers = canvas.receivers(canvas.destinationCrsChanged)
    project_receivers = project.receivers(project.layersWillBeRemoved)
    layer_receivers = [layer.receivers(layer.selectionChanged) for layer in points]
    dock.hide()
    assert dock._preview_band is None
    assert dock._construction_preview_band is None
    assert not dock._preview_active
    assert dock._connected_layers == []
    assert polygon_band.asGeometry().isEmpty()
    assert line_band.asGeometry().isEmpty()
    assert polygon_band not in scene.items()
    assert line_band not in scene.items()
    assert canvas.receivers(canvas.destinationCrsChanged) == canvas_receivers - 1
    assert project.receivers(project.layersWillBeRemoved) == project_receivers - 1
    assert [layer.receivers(layer.selectionChanged) for layer in points] == [
        count - 1 for count in layer_receivers]
    dock.crossingTypeComboBox.setCurrentText('NDB')
    points[0].removeSelection()
    dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    assert dock._preview_band is None
    dock.show()
    assert dock._preview_band is not polygon_band
    assert not dock._preview_band.asGeometry().isEmpty()
    assert not dock._construction_preview_band.asGeometry().isEmpty()
    assert len(dock._connected_layers) == 3
    assert canvas.receivers(canvas.destinationCrsChanged) == canvas_receivers
    assert project.receivers(project.layersWillBeRemoved) == project_receivers
    dock.close()
    assert dock._preview_band is None
    assert dock._construction_preview_band is None
    assert dock._connected_layers == []
    assert canvas.receivers(canvas.destinationCrsChanged) == canvas_receivers - 1
    assert project.receivers(project.layersWillBeRemoved) == project_receivers - 1
    dock._start_preview()
    dock._stop_preview()
    assert dock._preview_band is None


def test_removing_dock_cleans_preview_like_plugin_unload(preview_dock):
    dock = preview_dock
    bands = (dock._preview_band, dock._construction_preview_band)
    dock.iface.window.removeDockWidget(dock)
    QgsApplication.processEvents()
    assert dock._preview_band is None
    assert dock._construction_preview_band is None
    assert dock._connected_layers == []
    assert all(band not in dock.iface.canvas.scene().items() for band in bands)


def test_removing_input_layer_clears_preview(preview_dock, points):
    dock = preview_dock
    dock.includeConstructionLinesCheckBox.setChecked(True)
    removed_id = points[1].id()
    QgsProject.instance().removeMapLayer(removed_id)
    QgsApplication.processEvents()
    assert dock._preview_band.asGeometry().isEmpty()
    assert dock._construction_preview_band.asGeometry().isEmpty()
    assert all(layer.id() != removed_id for layer in dock._connected_layers)
    assert dock.iface.bar.messages == []
    replacement = _point_layer('new_crossing', (510000, 1590000))
    dock.crossingLayerComboBox.setLayer(replacement)
    assert not dock._preview_band.asGeometry().isEmpty()


def test_readding_the_same_layer_restores_preview(preview_dock, points):
    dock = preview_dock
    project = QgsProject.instance()
    crossing = project.takeMapLayer(points[1])
    assert dock._preview_band.asGeometry().isEmpty()
    project.addMapLayer(crossing)
    dock.crossingLayerComboBox.setLayer(crossing)
    assert not dock._preview_band.asGeometry().isEmpty()
