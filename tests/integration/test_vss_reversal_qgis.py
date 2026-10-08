"""QGIS checks for VSS/OCS direction, preview and THR reference line."""

import json
import math
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication, QMainWindow  # noqa: E402
from qgis.PyQt.QtCore import Qt  # noqa: E402

from Q_Pansopy.dockwidgets.utilities.qpansopy_vss_dockwidget import (  # noqa: E402
    QPANSOPYVSSDockWidget,
)
from Q_Pansopy.modules.vss_loc import calculate_vss_loc  # noqa: E402
from Q_Pansopy.modules.vss_straight import calculate_vss_straight  # noqa: E402


class _Bar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _Iface:
    def __init__(self):
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas(self.window)
        self.bar = _Bar()

    def mainWindow(self):
        return self.window

    def mapCanvas(self):
        return self.canvas

    def messageBar(self):
        return self.bar

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


@pytest.fixture(autouse=True)
def clear_project():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    project.setEllipsoid('NONE')
    project.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    yield project
    project.removeAllMapLayers()


def _input_layers(project, line_angle_degrees):
    threshold_xy = QgsPointXY(500000.0, 1600000.0)
    angle = math.radians(line_angle_degrees)
    direction_x, direction_y = math.cos(angle), math.sin(angle)
    far_xy = QgsPointXY(
        threshold_xy.x() - 10000.0 * direction_x,
        threshold_xy.y() - 10000.0 * direction_y,
    )
    middle_xy = QgsPointXY(
        threshold_xy.x() - 5000.0 * direction_x,
        threshold_xy.y() - 5000.0 * direction_y,
    )

    point_layer = QgsVectorLayer('Point?crs=EPSG:32616', 'Threshold', 'memory')
    point = QgsFeature(point_layer.fields())
    point.setGeometry(QgsGeometry.fromPointXY(threshold_xy))
    point_layer.dataProvider().addFeatures([point])
    point_layer.updateExtents()
    point_layer.selectAll()

    runway_layer = QgsVectorLayer('LineString?crs=EPSG:32616', 'Runway', 'memory')
    runway = QgsFeature(runway_layer.fields())
    runway.setGeometry(QgsGeometry.fromPolylineXY([far_xy, middle_xy, threshold_xy]))
    runway_layer.dataProvider().addFeatures([runway])
    runway_layer.updateExtents()
    runway_layer.selectAll()

    project.addMapLayer(point_layer)
    project.addMapLayer(runway_layer)
    return point_layer, runway_layer, threshold_xy


def _iface(project):
    iface = _Iface()
    iface.canvas.setDestinationCrs(project.crs())
    iface.canvas.zoomScale(30000)
    return iface


def _calculate(mode, iface, point_layer, runway_layer, reverse_direction=None,
               export_kml=False, output_dir=None, **overrides):
    params = {
        'rwy_width': '45',
        'thr_elev': '100',
        'thr_elev_unit': 'm',
        'strip_width': '140',
        'OCH': '100',
        'OCH_unit': 'm',
        'RDH': '15',
        'RDH_unit': 'm',
        'VPA': '3.0',
        'export_kml': export_kml,
        'output_dir': output_dir or '',
    }
    if reverse_direction is not None:
        params['reverse_direction'] = reverse_direction
    params.update(overrides)
    calculator = {
        'Straight In': calculate_vss_straight,
        'LOC': calculate_vss_loc,
    }[mode]
    return calculator(iface, point_layer, runway_layer, params)


def _output_vertices(layer):
    feature = next(layer.getFeatures())
    ring = feature.geometry().constGet().exteriorRing()
    vertices = ring.points()
    assert feature.geometry().isGeosValid()
    assert feature.geometry().wkbType().name.endswith('PolygonZ')
    return [(vertex.x(), vertex.y(), vertex.z()) for vertex in vertices]


def _remove_outputs(project, result):
    for layer in (result['vss_layer'], result['ocs_layer'], result['reference_line_layer']):
        project.removeMapLayer(layer.id())


def _assert_vertices_approx(actual, expected):
    actual = sorted(actual)
    expected = sorted(expected)
    assert len(actual) == len(expected)
    for actual_vertex, expected_vertex in zip(actual, expected):
        assert actual_vertex == pytest.approx(expected_vertex, abs=1e-6)


@pytest.mark.parametrize('mode', ['Straight In', 'LOC'])
@pytest.mark.parametrize('line_angle_degrees', [0.0, 37.0], ids=['east-west', 'oblique'])
def test_reversal_rotates_both_surfaces_around_selected_threshold(
        clear_project, mode, line_angle_degrees):
    project = clear_project
    point_layer, runway_layer, threshold = _input_layers(project, line_angle_degrees)
    iface = _iface(project)
    point_wkb = next(point_layer.getFeatures()).geometry().asWkb()
    runway_wkb = next(runway_layer.getFeatures()).geometry().asWkb()
    point_selection = point_layer.selectedFeatureIds()
    runway_selection = runway_layer.selectedFeatureIds()

    normal = _calculate(mode, iface, point_layer, runway_layer)
    normal_vertices = {
        name: _output_vertices(normal[name]) for name in ('vss_layer', 'ocs_layer')
    }
    normal_areas = {
        name: next(normal[name].getFeatures()).geometry().area()
        for name in ('vss_layer', 'ocs_layer')
    }
    normal_parameters = {
        name: json.loads(next(normal[name].getFeatures())['parameters'])
        for name in ('vss_layer', 'ocs_layer')
    }
    assert all(params['reverse_direction'] == 'NO' for params in normal_parameters.values())

    _remove_outputs(project, normal)
    explicit_normal = _calculate(mode, iface, point_layer, runway_layer, 'NO')
    for name in ('vss_layer', 'ocs_layer'):
        assert _output_vertices(explicit_normal[name]) == normal_vertices[name]
    _remove_outputs(project, explicit_normal)

    reversed_result = _calculate(mode, iface, point_layer, runway_layer, 'YES')
    for name in ('vss_layer', 'ocs_layer'):
        reversed_vertices = _output_vertices(reversed_result[name])
        expected_reflection = sorted(
            (2 * threshold.x() - x, 2 * threshold.y() - y, z)
            for x, y, z in normal_vertices[name]
        )
        _assert_vertices_approx(reversed_vertices, expected_reflection)

        reversed_area = next(reversed_result[name].getFeatures()).geometry().area()
        assert reversed_area == pytest.approx(normal_areas[name], rel=1e-9)
        params = json.loads(next(reversed_result[name].getFeatures())['parameters'])
        assert params['reverse_direction'] == 'YES'

    assert next(point_layer.getFeatures()).geometry().asWkb() == point_wkb
    assert next(runway_layer.getFeatures()).geometry().asWkb() == runway_wkb
    assert point_layer.selectedFeatureIds() == point_selection
    assert runway_layer.selectedFeatureIds() == runway_selection

    reverse_runway = QgsVectorLayer('LineString?crs=EPSG:32616', 'Reverse Runway', 'memory')
    original_points = next(runway_layer.getFeatures()).geometry().asPolyline()
    reverse_feature = QgsFeature(reverse_runway.fields())
    reverse_feature.setGeometry(QgsGeometry.fromPolylineXY(list(reversed(original_points))))
    reverse_runway.dataProvider().addFeatures([reverse_feature])
    reverse_runway.updateExtents()
    reverse_runway.selectAll()
    project.addMapLayer(reverse_runway)

    flipped_line = _calculate(mode, iface, point_layer, reverse_runway)
    for name in ('vss_layer', 'ocs_layer'):
        _assert_vertices_approx(
            _output_vertices(flipped_line[name]), _output_vertices(reversed_result[name])
        )
        params = json.loads(next(flipped_line[name].getFeatures())['parameters'])
        assert params['reverse_direction'] == 'NO'


def test_dock_direction_toggle_and_parameter_exports(clear_project, monkeypatch):
    project = clear_project
    point_layer, runway_layer, _ = _input_layers(project, 0.0)
    iface = _iface(project)
    dock = QPANSOPYVSSDockWidget(iface)
    dock.pointLayerComboBox.setLayer(point_layer)
    dock.runwayLayerComboBox.setLayer(runway_layer)

    try:
        assert dock.directionButton.text() == 'Direction: End to Start'
        assert dock._get_reverse_direction() == 'NO'

        dock.directionButton.click()
        assert dock.directionButton.text() == 'Direction: Start to End'
        assert dock._get_reverse_direction() == 'YES'
        dock.locRadioButton.setChecked(True)
        assert dock._get_reverse_direction() == 'YES'

        captured = {}

        def capture_loc(_iface_arg, _point, _runway, params):
            captured.update(params)
            return None

        monkeypatch.setattr(dock, 'validate_inputs', lambda: True)
        monkeypatch.setattr(dock, 'log', lambda _message: None)
        with patch('Q_Pansopy.modules.vss_loc.calculate_vss_loc', capture_loc):
            dock.calculate()
        assert captured['reverse_direction'] == 'YES'

        dock.straightInNPARadioButton.setChecked(True)
        captured.clear()

        def capture_straight(_iface_arg, _point, _runway, params):
            captured.update(params)
            return None

        with patch(
                'Q_Pansopy.modules.vss_straight.calculate_vss_straight',
                capture_straight):
            dock.calculate()
        assert captured['reverse_direction'] == 'YES'

        shown = {}

        def capture_table(_title, sections):
            shown.update(sections[0][1])

        monkeypatch.setattr(
            'Q_Pansopy.parameters_inspector_dialog.show_web_popup', capture_table
        )
        dock.show_parameters_table()
        assert shown['reverse_direction'] == 'YES'

        dock.copy_parameters_as_json()
        copied = json.loads(QApplication.clipboard().text())
        assert copied['parameters']['reverse_direction'] == 'YES'

        dock.directionButton.click()
        assert dock.directionButton.text() == 'Direction: End to Start'
        assert dock._get_reverse_direction() == 'NO'
    finally:
        dock.close()


@pytest.mark.parametrize('mode', ['Straight In', 'LOC'])
@pytest.mark.parametrize('elevation,unit', [(100.0, 'm'), (1000.0, 'ft')])
def test_reversed_surfaces_export_kml(clear_project, tmp_path, mode, elevation, unit):
    project = clear_project
    point_layer, runway_layer, _ = _input_layers(project, 0.0)
    result = _calculate(
        mode, _iface(project), point_layer, runway_layer, 'YES',
        export_kml=True, output_dir=str(tmp_path),
        thr_elev=elevation, thr_elev_unit=unit,
    )

    assert set(result) >= {'vss_path', 'ocs_path', 'reference_line_path'}
    assert len(list(tmp_path.glob('*.kml'))) == 3

    namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
    root = ET.parse(result['reference_line_path']).getroot()
    line = root.find('.//kml:LineString', namespaces)
    assert line is not None
    assert line.find('kml:altitudeMode', namespaces).text == 'absolute'
    coordinates = [
        tuple(map(float, value.split(',')))
        for value in line.find('kml:coordinates', namespaces).text.split()
    ]
    points = next(result['reference_line_layer'].getFeatures()).geometry().constGet().points()
    transform = QgsCoordinateTransform(
        point_layer.crs(), QgsCoordinateReferenceSystem('EPSG:4326'), project
    )
    assert len(coordinates) == len(points) == 3
    z = elevation if unit == 'm' else elevation * 0.3048
    for coordinate, point in zip(coordinates, points):
        lon_lat = transform.transform(QgsPointXY(point.x(), point.y()))
        assert coordinate == pytest.approx((lon_lat.x(), lon_lat.y(), z), abs=1e-7)


@pytest.mark.parametrize('mode', ['Straight In', 'LOC'])
def test_surface_crs_uses_input_crs_when_canvas_crs_differs(clear_project, mode):
    project = clear_project
    point_layer, runway_layer, _ = _input_layers(project, 37.0)
    iface = _iface(project)
    iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))

    result = _calculate(mode, iface, point_layer, runway_layer)
    for name in ('vss_layer', 'ocs_layer', 'reference_line_layer'):
        output = result[name]
        assert output.crs() == point_layer.crs()
        assert output.crs().authid() == 'EPSG:32616'
    _remove_outputs(project, result)


@pytest.mark.parametrize('mode', ['Straight In', 'LOC'])
@pytest.mark.parametrize('line_angle_degrees', [0.0, 37.0], ids=['east-west', 'oblique'])
@pytest.mark.parametrize('reverse_direction', ['NO', 'YES'])
@pytest.mark.parametrize('elevation,unit', [(100.0, 'm'), (1000.0, 'ft')])
def test_reference_line_geometry_and_threshold_elevation(
        clear_project, tmp_path, mode, line_angle_degrees, reverse_direction, elevation, unit):
    project = clear_project
    point_layer, runway_layer, threshold = _input_layers(project, line_angle_degrees)
    point_wkb = next(point_layer.getFeatures()).geometry().asWkb()
    runway_wkb = next(runway_layer.getFeatures()).geometry().asWkb()
    point_selection = point_layer.selectedFeatureIds()
    runway_selection = runway_layer.selectedFeatureIds()
    result = _calculate(
        mode, _iface(project), point_layer, runway_layer, reverse_direction,
        output_dir=str(tmp_path), thr_elev=elevation, thr_elev_unit=unit,
    )

    reference = result['reference_line_layer']
    assert reference.name() == 'VSS_OCS_RWY_reference_line'
    assert project.mapLayer(reference.id()) is reference
    assert reference.featureCount() == 1
    feature = next(reference.getFeatures())
    assert feature.geometry().wkbType().name.endswith('LineStringZ')
    points = feature.geometry().constGet().points()
    assert len(points) == 3
    z = elevation if unit == 'm' else elevation * 0.3048
    assert all(point.z() == pytest.approx(z) for point in points)
    assert (points[1].x(), points[1].y()) == pytest.approx((threshold.x(), threshold.y()))

    angle = math.radians(line_angle_degrees)
    for point in (points[0], points[2]):
        dx, dy = point.x() - threshold.x(), point.y() - threshold.y()
        assert dx * math.cos(angle) + dy * math.sin(angle) == pytest.approx(0.0, abs=1e-8)
    assert points[0].x() + points[2].x() == pytest.approx(2 * threshold.x())
    assert points[0].y() + points[2].y() == pytest.approx(2 * threshold.y())

    # Independently measure the widest surface in runway-relative coordinates.
    surface_half_width = max(
        abs((x - threshold.x()) * -math.sin(angle) + (y - threshold.y()) * math.cos(angle))
        for name in ('vss_layer', 'ocs_layer')
        for x, y, _z in _output_vertices(result[name])
    )
    half_width = surface_half_width + 926.0
    assert feature.geometry().length() == pytest.approx(2 * half_width)
    for point in (points[0], points[2]):
        assert math.hypot(point.x() - threshold.x(), point.y() - threshold.y()) == pytest.approx(half_width)
    assert reference.renderer().symbol().color().name() == '#800080'
    assert reference.renderer().symbol().width() == pytest.approx(0.5)
    assert len(reference.actions().actions()) > 0
    assert feature['id'] == 1
    assert json.loads(feature['parameters']) == json.loads(next(result['vss_layer'].getFeatures())['parameters'])
    assert next(point_layer.getFeatures()).geometry().asWkb() == point_wkb
    assert next(runway_layer.getFeatures()).geometry().asWkb() == runway_wkb
    assert point_layer.selectedFeatureIds() == point_selection
    assert runway_layer.selectedFeatureIds() == runway_selection
    assert 'reference_line_path' not in result
    assert not list(tmp_path.glob('*.kml'))

    _remove_outputs(project, result)
    inverted = _calculate(
        mode, _iface(project), point_layer, runway_layer,
        'YES' if reverse_direction == 'NO' else 'NO', thr_elev=elevation, thr_elev_unit=unit,
    )
    inverted_points = next(inverted['reference_line_layer'].getFeatures()).geometry().constGet().points()
    for normal_point, inverted_point in zip(points, reversed(inverted_points)):
        assert (normal_point.x(), normal_point.y(), normal_point.z()) == pytest.approx(
            (inverted_point.x(), inverted_point.y(), inverted_point.z())
        )


@pytest.mark.parametrize('mode', ['Straight In', 'LOC'])
@pytest.mark.parametrize('overrides', [
    {'rwy_width': 3000},
    {'strip_width': 3000},
    {'OCH': 25, 'strip_width': 20},
])
def test_reference_covers_widest_surface(clear_project, mode, overrides):
    project = clear_project
    point_layer, runway_layer, threshold = _input_layers(project, 37.0)
    result = _calculate(mode, _iface(project), point_layer, runway_layer, **overrides)
    normal_x, normal_y = -math.sin(math.radians(37.0)), math.cos(math.radians(37.0))
    widest = max(
        abs((x - threshold.x()) * normal_x + (y - threshold.y()) * normal_y)
        for name in ('vss_layer', 'ocs_layer')
        for x, y, _z in _output_vertices(result[name])
    )
    line = next(result['reference_line_layer'].getFeatures()).geometry()
    assert line.length() == pytest.approx(2 * (widest + 926.0))


@pytest.mark.parametrize('mode', ['Straight In', 'LOC'])
@pytest.mark.parametrize('failure', [None, 'write', 'altitude'], ids=['success', 'write-error', 'altitude-error'])
def test_reference_export_status_preserves_outputs_and_logs(
        clear_project, tmp_path, monkeypatch, mode, failure):
    project = clear_project
    point_layer, runway_layer, _ = _input_layers(project, 0.0)
    if failure == 'write':
        writer = QgsVectorFileWriter.writeAsVectorFormat

        def fail_reference(layer, *args, **kwargs):
            if layer.name() == 'VSS_OCS_RWY_reference_line':
                return QgsVectorFileWriter.ErrCreateDataSource, 'Reference write failed'
            return writer(layer, *args, **kwargs)

        monkeypatch.setattr(QgsVectorFileWriter, 'writeAsVectorFormat', fail_reference)
    elif failure == 'altitude':
        monkeypatch.setattr('Q_Pansopy.modules.vss_reference.fix_kml_altitude_mode', lambda _path: False)

    result = _calculate(
        mode, _iface(project), point_layer, runway_layer,
        export_kml=True, output_dir=str(tmp_path),
    )
    assert ('reference_line_path' in result) is (failure is None)
    assert set(result) >= {'vss_path', 'ocs_path'}
    for name in ('vss_layer', 'ocs_layer', 'reference_line_layer'):
        assert project.mapLayer(result[name].id()) is result[name]

    iface = _iface(project)
    dock = QPANSOPYVSSDockWidget(iface)
    dock.pointLayerComboBox.setLayer(point_layer)
    dock.runwayLayerComboBox.setLayer(runway_layer)
    dock.exportKmlCheckBox.setChecked(True)
    dock.outputFolderLineEdit.setText(str(tmp_path))
    dock.locRadioButton.setChecked(mode == 'LOC')
    logs = []
    monkeypatch.setattr(dock, 'log', logs.append)
    calculator = 'vss_loc.calculate_vss_loc' if mode == 'LOC' else 'vss_straight.calculate_vss_straight'
    try:
        with patch(f'Q_Pansopy.modules.{calculator}', return_value=result):
            dock.calculate()
        assert any('Reference line created: VSS_OCS_RWY_reference_line' in message for message in logs)
        if failure is None:
            assert f"Reference line KML exported to: {result['reference_line_path']}" in logs
            assert 'Calculation completed successfully!' in logs
        else:
            assert any('Reference line KML export failed' in message for message in logs)
            assert not any('Reference line KML exported to:' in message for message in logs)
            assert 'Calculation completed successfully!' not in logs
    finally:
        dock.close()


def test_direction_preview_tracks_toggle_and_visibility(clear_project):
    project = clear_project
    point_layer, runway_layer, _ = _input_layers(project, 37.0)
    iface = _iface(project)
    dock = QPANSOPYVSSDockWidget(iface)
    dock.pointLayerComboBox.setLayer(point_layer)
    dock.runwayLayerComboBox.setLayer(runway_layer)
    iface.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    iface.window.show()
    dock.show()
    QApplication.processEvents()
    try:
        band = dock._direction_preview_band
        first = band.asGeometry()
        assert not first.isEmpty()
        first_vertices = first.asMultiPolygon()[0][0]
        assert len(first_vertices) == 4

        dock.directionButton.click()
        QApplication.processEvents()
        reversed_geometry = band.asGeometry()
        assert not reversed_geometry.isEmpty()
        reversed_vertices = reversed_geometry.asMultiPolygon()[0][0]
        assert reversed_vertices[0].x() != pytest.approx(first_vertices[0].x())
        assert reversed_vertices[0].y() != pytest.approx(first_vertices[0].y())

        dock.hide()
        QApplication.processEvents()
        assert band.asGeometry().isEmpty()
        dock.show()
        QApplication.processEvents()
        assert not band.asGeometry().isEmpty()
    finally:
        dock.close()
