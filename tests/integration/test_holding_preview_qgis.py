"""Real QGIS checks for Holding's shared nominal and live canvas preview."""

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication, QEvent  # noqa: E402
from qgis.PyQt.QtWidgets import QMainWindow  # noqa: E402

from Q_Pansopy.qt_compat import Qt_RightDockWidgetArea  # noqa: E402
from Q_Pansopy.modules.utilities import holding  # noqa: E402
from Q_Pansopy.dockwidgets.utilities.qpansopy_holding_dockwidget import (  # noqa: E402
    QPANSOPYHoldingDockWidget,
)


class _Iface:
    def __init__(self):
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas(self.window)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
        self.window.setCentralWidget(self.canvas)
        self.messages = []

    def mainWindow(self):
        return self.window

    def mapCanvas(self):
        return self.canvas

    def activeLayer(self):
        return None

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
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    if existing is None:
        app.exitQgis()


def _route(name='routing', wkt='LineString (500000 1600000, 501000 1600000)'):
    layer = QgsVectorLayer('LineString?crs=EPSG:32616', name, 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    layer.dataProvider().addFeatures([feature])
    layer.selectByIds([next(layer.getFeatures()).id()])
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def routing():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    layer = _route()
    yield layer
    project.removeAllMapLayers()


@pytest.fixture
def dock(routing):
    iface = _Iface()
    widget = QPANSOPYHoldingDockWidget(iface)
    widget.routingLayerComboBox.setLayer(routing)
    widget.outputFolderLineEdit.setText('')
    iface.window.addDockWidget(Qt_RightDockWidgetArea, widget)
    iface.window.show()
    QgsApplication.processEvents()
    yield widget
    widget.close()
    iface.window.close()
    widget.deleteLater()
    iface.window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _preview(dock):
    return dock._preview_band.asGeometry()


@pytest.mark.parametrize('turn,side', [('R', -1), ('L', 1)])
def test_nominal_preserves_legacy_dimensions_without_side_effects(routing, turn, side):
    before_layers = set(QgsProject.instance().mapLayers())
    before = next(routing.getFeatures()).geometry().asWkb()
    points = next(routing.getFeatures()).geometry().asPolyline()
    params = {'IAS': 220, 'altitude': 10000, 'isa_var': -5,
              'bank_angle': 25, 'leg_time_min': 1.5, 'turn': turn}
    result = holding.build_holding_nominal(points, params)
    tas = holding.tas_calculation(220, 10000, -5, 25)[1]
    leg_m = tas * 1.5 / 60 * 1852
    assert QgsPointXY(result.start_point) == QgsPointXY(501000, 1600000)
    assert result.azimuth == pytest.approx(90)
    assert result.summary['Leg_nm'] == pytest.approx(leg_m / 1852)
    paths = [geometry.asPolyline() for geometry in result.geometries]
    assert len(paths) == 4
    assert paths[0][0].x() == pytest.approx(501000 - leg_m)
    assert paths[0][-1] == QgsPointXY(501000, 1600000)
    assert paths[1][-1].x() == pytest.approx(501000)
    assert paths[1][-1].y() == pytest.approx(1600000 + side * leg_m)
    assert len(paths[1]) > 2 and len(paths[3]) > 2
    assert paths[2][-1].x() == pytest.approx(501000 - leg_m)
    assert paths[3][-1] == paths[0][0]
    params['bank_angle'] = 15
    other = holding.build_holding_nominal(points, params)
    assert [g.asWkb() for g in other.geometries] == [g.asWkb() for g in result.geometries]
    assert other.summary['Radius_nm'] != result.summary['Radius_nm']
    assert set(QgsProject.instance().mapLayers()) == before_layers
    assert next(routing.getFeatures()).geometry().asWkb() == before


@pytest.mark.parametrize('turn', ['R', 'L'])
@pytest.mark.parametrize('unit,altitude,isa,leg', [
    ('ft', '10000', '0', '1'), ('m', '3048', '-5', '1.5'),
])
def test_live_preview_matches_all_four_final_features(
        dock, routing, monkeypatch, turn, unit, altitude, isa, leg):
    assert routing.startEditing()
    assert routing.changeGeometry(routing.selectedFeatureIds()[0], QgsGeometry.fromWkt(
        'LineString (500000 1600000, 500800 1600900, 501400 1600400)'))
    dock.altitudeUnitCombo.setCurrentText(unit)
    dock.altitudeLineEdit.setText(altitude)
    dock.isaVarLineEdit.setText(isa)
    dock.legTimeLineEdit.setText(leg)
    (dock.leftTurnRadio if turn == 'L' else dock.rightTurnRadio).setChecked(True)
    before_layers = set(QgsProject.instance().mapLayers())
    paths = _preview(dock).asMultiPolyline()
    assert len(paths) == 4
    assert dock.last_summary is None
    assert dock.logTextEdit.toPlainText() == ''
    assert dock.iface.messages == []
    assert set(QgsProject.instance().mapLayers()) == before_layers
    results = []
    original = holding.run_holding_pattern

    def record(*args):
        result = original(*args)
        results.append(result)
        return result

    monkeypatch.setattr(holding, 'run_holding_pattern', record)
    dock.showCirclesCheckBox.setChecked(False)
    dock.calculate()
    assert results and results[0]
    features = list(results[0]['layer'].getFeatures())
    assert len(features) == 4
    for path, feature in zip(paths, features):
        # Final output retains CircularStrings; the canvas renders their polylines.
        output_path = feature.geometry().asPolyline()
        assert QgsGeometry.fromPolylineXY(path).asWkb() == QgsGeometry.fromPolylineXY(output_path).asWkb()
    assert dock.last_summary == results[0]['summary']
    assert _preview(dock).isEmpty()
    summary = dock.last_summary.copy()
    dock.iasLineEdit.setText('230')
    assert not _preview(dock).isEmpty()
    assert dock.last_summary == summary


@pytest.mark.parametrize('control,value', [
    ('iasLineEdit', '240'), ('altitudeLineEdit', '12000'),
    ('isaVarLineEdit', '15'), ('legTimeLineEdit', '1.5'),
    ('altitudeUnitCombo', 'm'), ('leftTurnRadio', True),
])
def test_preview_tracks_nominal_parameters(dock, control, value):
    before = _preview(dock).asWkb()
    widget = getattr(dock, control)
    if control.endswith('Combo'):
        widget.setCurrentText(value)
    elif control.endswith('Radio'):
        widget.setChecked(value)
    else:
        widget.setText(value)
    assert not _preview(dock).isEmpty()
    assert _preview(dock).asWkb() != before


@pytest.mark.parametrize('control,value', [
    ('iasLineEdit', ''), ('iasLineEdit', 'nan'), ('iasLineEdit', '0'),
    ('altitudeLineEdit', 'inf'), ('isaVarLineEdit', '-1000'),
    ('bankAngleLineEdit', '0'), ('bankAngleLineEdit', '90'),
    ('legTimeLineEdit', '-1'), ('legTimeLineEdit', 'invalid'),
])
def test_invalid_parameters_clear_silently_and_recover(dock, control, value):
    before_layers = set(QgsProject.instance().mapLayers())
    widget = getattr(dock, control)
    original = widget.text()
    assert not _preview(dock).isEmpty()
    widget.setText(value)
    assert _preview(dock).isEmpty()
    assert dock.iface.messages == []
    assert dock.logTextEdit.toPlainText() == ''
    assert dock.last_summary is None
    assert set(QgsProject.instance().mapLayers()) == before_layers
    widget.setText(original)
    assert not _preview(dock).isEmpty()


def test_selection_geometry_and_layer_replacement(dock, routing):
    fid = routing.selectedFeatureIds()[0]
    routing.removeSelection()
    assert _preview(dock).isEmpty()
    routing.selectByIds([fid])
    before = _preview(dock).asWkb()
    assert routing.startEditing()
    assert routing.changeGeometry(fid, QgsGeometry.fromWkt(
        'LineString (500000 1600000, 501000 1600500)'))
    assert _preview(dock).asWkb() != before
    extra = QgsFeature()
    extra.setGeometry(QgsGeometry.fromWkt('LineString (500000 1600000, 502000 1600000)'))
    assert routing.addFeature(extra)
    routing.selectAll()
    assert _preview(dock).isEmpty()
    routing.selectByIds([fid])
    assert not _preview(dock).isEmpty()
    replacement = _route('replacement', 'LineString (500000 1600000, 502000 1600000)')
    dock.routingLayerComboBox.setLayer(replacement)
    assert dock._connected_layers == [replacement]
    dock.routingLayerComboBox.setLayer(None)
    assert _preview(dock).isEmpty()


@pytest.mark.parametrize('wkt', [
    'LineString EMPTY', 'LineString (501000 1600000, 501000 1600000)',
    'MultiLineString ((500000 1600000, 501000 1600000))',
])
def test_invalid_routing_geometry_clears(dock, routing, wkt):
    assert routing.startEditing()
    assert routing.changeGeometry(routing.selectedFeatureIds()[0], QgsGeometry.fromWkt(wkt))
    assert _preview(dock).isEmpty()
    assert dock.iface.messages == []


def test_crs_changes_clear_and_recover(dock, routing):
    original = _preview(dock).asWkb()
    routing.setCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    assert _preview(dock).isEmpty()
    routing.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    assert _preview(dock).asWkb() == original
    for crs in ('EPSG:4326', 'EPSG:2263', 'EPSG:3857'):
        dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
        assert _preview(dock).isEmpty()
    dock.iface.canvas.setDestinationCrs(routing.crs())
    assert _preview(dock).asWkb() == original


def test_provider_edit_and_layer_removal(dock, routing):
    before = _preview(dock).asWkb()
    geometry = QgsGeometry.fromWkt('LineString (500000 1600000, 501000 1600500)')
    assert routing.dataProvider().changeGeometryValues({routing.selectedFeatureIds()[0]: geometry})
    routing.dataChanged.emit()
    assert _preview(dock).asWkb() != before
    project = QgsProject.instance()
    layer = project.takeMapLayer(routing)
    assert _preview(dock).isEmpty()
    assert dock._connected_layers == []
    project.addMapLayer(layer)
    dock.routingLayerComboBox.setLayer(layer)
    assert not _preview(dock).isEmpty()


def test_visibility_close_and_remove_dock_release_resources(dock, routing):
    canvas = dock.iface.canvas
    project = QgsProject.instance()
    counts = (routing.receivers(routing.selectionChanged),
              canvas.receivers(canvas.destinationCrsChanged),
              project.receivers(project.layersWillBeRemoved))
    for _ in range(3):
        dock._on_preview_layers_changed()
    assert counts == (routing.receivers(routing.selectionChanged),
                      canvas.receivers(canvas.destinationCrsChanged),
                      project.receivers(project.layersWillBeRemoved))
    band = dock._preview_band
    dock.hide()
    assert dock._preview_band is None
    assert dock._connected_layers == []
    assert band not in canvas.scene().items()
    assert band.asGeometry().isEmpty()
    assert routing.receivers(routing.selectionChanged) == counts[0] - 1
    assert canvas.receivers(canvas.destinationCrsChanged) == counts[1] - 1
    assert project.receivers(project.layersWillBeRemoved) == counts[2] - 1
    dock.iasLineEdit.setText('240')
    assert dock._preview_band is None
    dock.show()
    assert dock._preview_band is not band
    assert not _preview(dock).isEmpty()
    band = dock._preview_band
    dock.iface.window.removeDockWidget(dock)
    QgsApplication.processEvents()
    assert dock._preview_band is None
    assert band not in canvas.scene().items()
    dock.close()
    dock._start_preview()
    assert dock._preview_band is None
