"""Runtime direction, CRS and lifecycle checks for the Initial SID preview."""
from unittest.mock import MagicMock

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas, QgsRubberBand  # noqa: E402
from qgis.PyQt.QtWidgets import QMainWindow  # noqa: E402

from Q_Pansopy.dockwidgets.departures.qpansopy_sid_initial_dockwidget import (  # noqa: E402
    QPANSOPYSIDInitialDockWidget,
)
from Q_Pansopy.qt_compat import Qt_RightDockWidgetArea  # noqa: E402


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


def _runway(points, crs='EPSG:32616'):
    layer = QgsVectorLayer('LineString?crs=' + crs, 'Runway', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY(
        [QgsPointXY(*point) for point in points]))
    layer.dataProvider().addFeatures([feature])
    QgsProject.instance().addMapLayer(layer)
    layer.selectAll()
    return layer


class _Iface:
    def __init__(self, layer):
        self.layer = layer
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas(self.window)
        self.window.setCentralWidget(self.canvas)
        self.window.resize(1000, 700)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
        self.canvas.setLayers([layer])
        self.canvas.setExtent(QgsRectangle(499000, 1599000, 502000, 1602000))

    def mainWindow(self):
        return self.window

    def mapCanvas(self):
        return self.canvas

    def activeLayer(self):
        return self.layer


@pytest.fixture
def preview(qgis_app):
    QgsProject.instance().removeAllMapLayers()
    layer = _runway([(500000, 1600000), (501000, 1601000)])
    iface = _Iface(layer)
    dock = QPANSOPYSIDInitialDockWidget(iface)
    iface.window.addDockWidget(Qt_RightDockWidgetArea, dock)
    iface.window.show()
    qgis_app.processEvents()
    yield dock, iface, layer
    dock.close()
    iface.window.close()
    qgis_app.processEvents()
    QgsProject.instance().removeAllMapLayers()


def _ring(dock):
    geometry = dock._der_marker_band.asGeometry()
    if geometry.isMultipart():
        return geometry.asMultiPolygon()[0][0]
    return geometry.asPolygon()[0]


def _assert_tip_and_heading(dock, start, der):
    ring = _ring(dock)
    tip = ring[0]
    assert tip.x() == pytest.approx(der.x(), abs=1e-6)
    assert tip.y() == pytest.approx(der.y(), abs=1e-6)
    base_x = (ring[1].x() + ring[2].x()) / 2
    base_y = (ring[1].y() + ring[2].y()) / 2
    # The triangle points out along the runway direction, away from its base.
    heading_dot = ((tip.x() - base_x) * (der.x() - start.x())
                   + (tip.y() - base_y) * (der.y() - start.y()))
    assert heading_dot > 0
    length = ((tip.x() - base_x) ** 2 + (tip.y() - base_y) ** 2) ** 0.5
    assert length / dock.iface.mapCanvas().mapUnitsPerPixel() == pytest.approx(24)


def test_marker_is_opt_in_and_does_not_add_output_parameters(preview):
    dock, iface, layer = preview
    assert not dock.showDerMarkerCheckBox.isChecked()
    assert dock._der_marker_band.asGeometry().isEmpty()
    assert dock.runwayLayerComboBox.currentLayer() is layer
    layers_before = set(QgsProject.instance().mapLayers())
    params_before = dock.get_parameters()
    dock.showDerMarkerCheckBox.setChecked(True)
    assert not dock._der_marker_band.asGeometry().isEmpty()
    assert set(QgsProject.instance().mapLayers()) == layers_before
    assert dock.get_parameters() == params_before


@pytest.mark.parametrize('reversed_direction', [False, True])
@pytest.mark.parametrize('points', [
    [(500000, 1600000), (501000, 1601000)],
    [(500000, 1600000), (500300, 1599500), (501000, 1601000)],
])
def test_marker_matches_first_and_last_runway_vertices(
        preview, points, reversed_direction):
    dock, iface, old_layer = preview
    layer = _runway(points)
    dock.runwayLayerComboBox.setLayer(layer)
    dock.showDerMarkerCheckBox.setChecked(True)
    if reversed_direction:
        dock.directionButton.click()
    start, der = (points[-1], points[0]) if reversed_direction else (points[0], points[-1])
    _assert_tip_and_heading(dock, QgsPointXY(*start), QgsPointXY(*der))
    assert dock._connected_runway_layer is layer


def test_marker_tracks_crs_changes_without_editing_the_runway(preview):
    dock, iface, old_layer = preview
    points = [(-87, 14.5), (-87, 14.51)]
    layer = _runway(points, 'EPSG:4326')
    original = layer.selectedFeatures()[0].geometry().asWkt()
    dock.runwayLayerComboBox.setLayer(layer)
    dock.showDerMarkerCheckBox.setChecked(True)
    for crs in ('EPSG:32616', 'EPSG:3857'):
        iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
        transform = QgsCoordinateTransform(
            layer.crs(), iface.canvas.mapSettings().destinationCrs(), QgsProject.instance())
        _assert_tip_and_heading(
            dock, transform.transform(QgsPointXY(*points[0])),
            transform.transform(QgsPointXY(*points[-1])))
    assert layer.selectedFeatures()[0].geometry().asWkt() == original


def test_marker_retains_screen_size_after_zoom(preview):
    dock, iface, layer = preview
    dock.showDerMarkerCheckBox.setChecked(True)
    _assert_tip_and_heading(dock, QgsPointXY(500000, 1600000), QgsPointXY(501000, 1601000))
    pixel_size_before = iface.canvas.mapUnitsPerPixel()
    iface.canvas.zoomByFactor(0.5)
    assert iface.canvas.mapUnitsPerPixel() == pytest.approx(pixel_size_before * 0.5)
    _assert_tip_and_heading(dock, QgsPointXY(500000, 1600000), QgsPointXY(501000, 1601000))


def test_selection_toggle_and_visibility_clear_and_restore_marker(preview, qgis_app):
    dock, iface, layer = preview
    dock.showDerMarkerCheckBox.setChecked(True)
    layer.removeSelection()
    assert dock._der_marker_band.asGeometry().isEmpty()
    layer.selectAll()
    assert not dock._der_marker_band.asGeometry().isEmpty()
    dock.showDerMarkerCheckBox.setChecked(False)
    assert dock._der_marker_band.asGeometry().isEmpty()
    dock.showDerMarkerCheckBox.setChecked(True)
    dock.hide()
    assert dock._der_marker_band.asGeometry().isEmpty()
    dock.show()
    qgis_app.processEvents()
    assert not dock._der_marker_band.asGeometry().isEmpty()


def test_layer_switch_disconnects_old_selection_and_connects_new_once(preview):
    dock, iface, old_layer = preview
    dock.showDerMarkerCheckBox.setChecked(True)
    layer = _runway([(500000, 1600000), (500500, 1600000)])
    dock.runwayLayerComboBox.setLayer(layer)
    dock._clear_der_marker = MagicMock(wraps=dock._clear_der_marker)
    old_layer.removeSelection()
    dock._clear_der_marker.assert_not_called()
    layer.removeSelection()
    dock._clear_der_marker.assert_called_once_with()
    assert dock._der_marker_band.asGeometry().isEmpty()
    dock._clear_der_marker.reset_mock()
    layer.selectAll()
    dock._clear_der_marker.assert_called_once_with()
    assert not dock._der_marker_band.asGeometry().isEmpty()


def test_multiple_selection_and_degenerate_runway_clear_marker(preview):
    dock, iface, layer = preview
    dock.showDerMarkerCheckBox.setChecked(True)
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY(
        [QgsPointXY(501000, 1601000), QgsPointXY(502000, 1602000)]))
    layer.dataProvider().addFeatures([feature])
    layer.selectAll()
    assert dock._der_marker_band.asGeometry().isEmpty()
    degenerate = _runway([(500000, 1600000), (500100, 1600000), (500000, 1600000)])
    dock.runwayLayerComboBox.setLayer(degenerate)
    assert dock._der_marker_band.asGeometry().isEmpty()


def test_close_removes_marker_and_disconnects_external_signals(preview):
    dock, iface, layer = preview
    dock.showDerMarkerCheckBox.setChecked(True)
    band = dock._der_marker_band
    dock.close()
    assert band.scene() is None
    assert dock._der_marker_band is None
    assert dock._connected_runway_layer is None
    dock._clear_der_marker = MagicMock()
    layer.removeSelection()
    iface.canvas.scaleChanged.emit(1000)
    iface.canvas.destinationCrsChanged.emit()
    dock._clear_der_marker.assert_not_called()
    # Project changes may still update the closed dock's layer combo.
    replacement = _runway([(500000, 1600000), (500500, 1600000)])
    dock.runwayLayerComboBox.setLayer(replacement)
    assert dock._connected_runway_layer is None


def test_reopening_creates_one_marker_without_leaving_the_old_one(preview, qgis_app):
    dock, iface, layer = preview
    count_before = sum(isinstance(item, QgsRubberBand) for item in iface.canvas.scene().items())
    dock.showDerMarkerCheckBox.setChecked(True)
    dock.close()
    replacement = QPANSOPYSIDInitialDockWidget(iface)
    iface.window.addDockWidget(Qt_RightDockWidgetArea, replacement)
    replacement.show()
    qgis_app.processEvents()
    replacement.showDerMarkerCheckBox.setChecked(True)
    try:
        assert not replacement._der_marker_band.asGeometry().isEmpty()
        assert sum(isinstance(item, QgsRubberBand) for item in iface.canvas.scene().items()) == count_before
    finally:
        replacement.close()
