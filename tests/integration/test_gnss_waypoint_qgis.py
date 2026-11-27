"""Real-QGIS output preservation gates for GNSS Waypoint's Qt6 migration."""
import math

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    Qgis, QgsFeature, QgsGeometry, QgsMapLayerProxyModel, QgsPointXY,
    QgsProject, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402
from .test_qt6_plugin_runtime import plugin, qgis_app  # noqa: F401,E402

WAYPOINT = QgsPointXY(500000, 1600000)
OUTPUT = 'GNSS Waypoint Tolerance'


def waypoint_layer(count=1, select=True):
    layer = QgsVectorLayer('Point?crs=EPSG:32616', 'Waypoint', 'memory')
    features = []
    for index in range(count):
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(
            QgsPointXY(WAYPOINT.x() + 10000 * index, WAYPOINT.y())))
        features.append(feature)
    assert layer.dataProvider().addFeatures(features)[0]
    if select:
        layer.selectByIds([next(layer.getFeatures()).id()])
    QgsProject.instance().addMapLayer(layer)
    return layer


def routing_layer(track_deg, select=True):
    """Leg that ends on the waypoint, flown on the given true track."""
    layer = QgsVectorLayer('LineString?crs=EPSG:32616', 'Routing', 'memory')
    track = math.radians(track_deg)
    start = QgsPointXY(WAYPOINT.x() - 10000 * math.sin(track),
                       WAYPOINT.y() - 10000 * math.cos(track))
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([start, WAYPOINT]))
    assert layer.dataProvider().addFeature(feature)
    if select:
        layer.selectAll()
    QgsProject.instance().addMapLayer(layer)
    return layer


def outputs():
    return [layer for layer in QgsProject.instance().mapLayers().values()
            if layer.name() == OUTPUT]


def capture_messages(instance, monkeypatch):
    messages = []
    monkeypatch.setattr(instance.iface.messageBar(), 'pushMessage',
                        lambda title, text, level: messages.append((title, text, level)))
    return messages


def assert_rectangle(geometry, track_deg, xtt_m, att_m):
    track = math.radians(track_deg)
    along = (math.sin(track), math.cos(track))
    across = (math.cos(track), -math.sin(track))
    assert geometry.isGeosValid()
    assert geometry.area() == pytest.approx(4 * xtt_m * att_m, rel=1e-9)
    assert geometry.centroid().asPoint().distance(WAYPOINT) < 1e-6
    vertices = list(geometry.vertices())[:-1]
    assert len(vertices) == 4
    for vertex in vertices:
        dx, dy = vertex.x() - WAYPOINT.x(), vertex.y() - WAYPOINT.y()
        assert abs(dx * along[0] + dy * along[1]) == pytest.approx(att_m, abs=1e-6)
        assert abs(dx * across[0] + dy * across[1]) == pytest.approx(xtt_m, abs=1e-6)


@pytest.mark.parametrize('xtt,track,expected_text', [
    (1.0, 0, ('1.0 NM', '0.8 NM')),
    (2.0, 45, ('2.0 NM', '1.6 NM')),
    (0.3, 300, ('0.3 NM', '0.24 NM')),
])
def test_calculate_button_preserves_rectangle_fields_and_style(
        plugin, monkeypatch, xtt, track, expected_text):
    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    waypoint = waypoint_layer()
    routing = routing_layer(track)
    instance.toggle_dock('GNSS_WAYPOINT')
    dock = instance.modules['GNSS_WAYPOINT']['GUI_INSTANCE']
    dock.waypointLayerComboBox.setLayer(waypoint)
    dock.routingLayerComboBox.setLayer(routing)
    dock.xttSpinBox.setValue(xtt)
    assert dock.attLineEdit.text() == f'{xtt * 0.8:.2f}'
    dock.calculateButton.click()

    assert len(outputs()) == 1
    output = outputs()[0]
    assert output.crs().authid() == 'EPSG:32616'
    assert output.geometryType() == Qgis.GeometryType.Polygon
    assert output.fields().names() == ['XTT', 'ATT', 'XTT_m', 'ATT_m']
    assert [field.type() for field in output.fields()] == [
        QMetaType.Type.QString, QMetaType.Type.QString,
        QMetaType.Type.Double, QMetaType.Type.Double,
    ]
    assert output.featureCount() == 1
    feature = next(output.getFeatures())
    xtt_m, att_m = xtt * 1852, 0.8 * xtt * 1852
    assert feature.attributes()[:2] == list(expected_text)
    assert feature['XTT_m'] == pytest.approx(xtt_m)
    assert feature['ATT_m'] == pytest.approx(att_m)
    assert_rectangle(feature.geometry(), track, xtt_m, att_m)

    symbol = output.renderer().symbol()
    assert symbol.opacity() == pytest.approx(0.3)
    assert symbol.color() == QColor('blue')
    assert symbol.symbolLayer(0).strokeColor() == QColor('darkblue')
    assert symbol.symbolLayer(0).strokeWidth() == pytest.approx(0.5)
    assert [m[2] for m in messages] == [Qgis.MessageLevel.Info, Qgis.MessageLevel.Success]
    assert f'XTT: {xtt} NM' in messages[0][1]
    assert waypoint.selectedFeatureCount() == 1 and routing.selectedFeatureCount() == 1
    assert 'completed successfully' in dock.logTextEdit.toPlainText()


def test_module_uses_single_unselected_waypoint_and_north_without_routing(plugin, monkeypatch):
    from Q_Pansopy.modules.pbn.gnss_waypoint import run_gnss_waypoint

    instance, _ = plugin
    capture_messages(instance, monkeypatch)
    result = run_gnss_waypoint(instance.iface, waypoint_layer(select=False), None, {'xtt': 1.5})
    assert result['xtt'] == 1.5 and result['att'] == pytest.approx(1.2)
    assert result['azimuth'] == 0 and result['layer'] is outputs()[0]
    feature = next(result['layer'].getFeatures())
    assert_rectangle(feature.geometry(), 0, 1.5 * 1852, 1.2 * 1852)


@pytest.mark.parametrize('case,message', [
    ('missing', 'No waypoint layer provided'),
    ('ambiguous', 'Please select a waypoint'),
    ('multiple', 'Please select only one waypoint'),
])
def test_rejected_waypoints_create_no_output(plugin, monkeypatch, case, message):
    from Q_Pansopy.modules.pbn.gnss_waypoint import run_gnss_waypoint

    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    layer = None
    if case != 'missing':
        layer = waypoint_layer(count=2, select=False)
        if case == 'multiple':
            layer.selectAll()
    before = set(QgsProject.instance().mapLayers())
    assert run_gnss_waypoint(instance.iface, layer, None) is None
    assert set(QgsProject.instance().mapLayers()) == before
    assert messages == [('Error', message, Qgis.MessageLevel.Critical)]


def test_runtime_failure_is_reported_without_output(plugin, monkeypatch):
    from Q_Pansopy.modules.pbn.gnss_waypoint import run_gnss_waypoint

    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    layer = waypoint_layer()
    before = set(QgsProject.instance().mapLayers())
    assert run_gnss_waypoint(instance.iface, layer, None, {'xtt': 'bad'}) is None
    assert set(QgsProject.instance().mapLayers()) == before
    assert [m[2] for m in messages] == [Qgis.MessageLevel.Critical] * 2
    assert messages[0][1].startswith('GNSS Waypoint error:')


@pytest.mark.parametrize('missing,log', [
    ('waypoint_layer', 'Please select a waypoint (point) layer'),
    ('routing_layer', 'Please select a routing (line) layer'),
    ('waypoint_selection', 'Please select at least one waypoint'),
    ('routing_selection', 'Please select the routing segment'),
])
def test_dock_validation_creates_no_output(plugin, missing, log):
    instance, _ = plugin
    instance.toggle_dock('GNSS_WAYPOINT')
    dock = instance.modules['GNSS_WAYPOINT']['GUI_INSTANCE']
    assert dock.waypointLayerComboBox.filters() == QgsMapLayerProxyModel.Filter.PointLayer
    assert dock.routingLayerComboBox.filters() == QgsMapLayerProxyModel.Filter.LineLayer
    waypoint = waypoint_layer(select=missing != 'waypoint_selection')
    routing = routing_layer(90, select=missing != 'routing_selection')
    for combo in (dock.waypointLayerComboBox, dock.routingLayerComboBox):
        combo.setAllowEmptyLayer(True)
    dock.waypointLayerComboBox.setLayer(None if missing == 'waypoint_layer' else waypoint)
    dock.routingLayerComboBox.setLayer(None if missing == 'routing_layer' else routing)
    dock.calculateButton.click()
    assert log in dock.logTextEdit.toPlainText()
    assert not outputs()


def test_dock_preseeds_active_line_layer(plugin):
    instance, _ = plugin
    routing = routing_layer(90)
    waypoint = waypoint_layer()
    from Q_Pansopy.dockwidgets.pbn.qpansopy_gnss_waypoint_dockwidget import (
        QPANSOPYGNSSWaypointDockWidget,
    )
    for active, expected in ((routing, routing), (waypoint, None)):
        instance.iface.activeLayer = lambda layer=active: layer
        dock = QPANSOPYGNSSWaypointDockWidget(instance.iface)
        try:
            if expected is not None:
                assert dock.routingLayerComboBox.currentLayer() is expected
            else:
                assert dock.routingLayerComboBox.currentLayer() is not waypoint
        finally:
            dock.close()
            dock.deleteLater()
