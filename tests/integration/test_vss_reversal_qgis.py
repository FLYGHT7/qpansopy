"""QGIS geometry and widget checks for VSS/OCS direction reversal (#307)."""

import json
import math
from unittest.mock import patch

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication, QMainWindow  # noqa: E402

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
               export_kml=False, output_dir=None):
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
    for layer in (result['vss_layer'], result['ocs_layer']):
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
def test_reversed_surfaces_export_kml(clear_project, tmp_path, mode):
    project = clear_project
    point_layer, runway_layer, _ = _input_layers(project, 0.0)
    result = _calculate(
        mode, _iface(project), point_layer, runway_layer, 'YES',
        export_kml=True, output_dir=str(tmp_path),
    )

    assert set(result) >= {'vss_path', 'ocs_path'}
    assert len(list(tmp_path.glob('*.kml'))) == 2
