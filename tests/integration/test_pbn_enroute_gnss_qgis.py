"""Real QGIS checks for the constant-width GNSS en-route tool."""
from types import SimpleNamespace

import pytest

from .test_enroute_vor_vor_qgis import qgis_app, clear_project  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.qgis_runtime]


def route(crs='EPSG:4326', points=((-87, 14), (-86, 14.5)), wkt=None):
    from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
                           QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject)
    layer = QgsVectorLayer('LineString?crs=' + crs, 'Route', 'memory')
    feature = QgsFeature()
    transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), layer.crs(), QgsProject.instance())
    feature.setGeometry(QgsGeometry.fromWkt(wkt) if wkt else QgsGeometry.fromPolylineXY(
        [transform.transform(QgsPointXY(*p)) for p in points]))
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    QgsProject.instance().addMapLayer(layer)
    return layer


def run(layer, identifier='rnav5'):
    from Q_Pansopy.modules.pbn.pbn_enroute_gnss import run_pbn_enroute_gnss
    iface = SimpleNamespace(messageBar=lambda: SimpleNamespace(pushMessage=lambda *a, **kw: None))
    assert run_pbn_enroute_gnss(iface, layer, {'nav_spec': identifier})
    from qgis.core import QgsProject
    return QgsProject.instance().layerTreeRoot().children()[0].children()[0].layer()


@pytest.mark.parametrize('identifier,width', [('rnav5', 5.77), ('rnp4', 8), ('rnav2', 5), ('rnp2', 5),
                                             ('arnp2', 5), ('arnp1', 3.5), ('rnav1', 5), ('rnp03', 1.45)])
def test_exact_rectangles(identifier, width):
    from Q_Pansopy.modules.pbn.pbn_enroute_gnss import build_enroute_geometry
    primary, left, right = build_enroute_geometry((0, 0), (100000, 0), identifier)
    w = width * 1852
    assert primary.boundingBox().yMaximum() == pytest.approx(w / 2)
    assert left.boundingBox().yMaximum() == pytest.approx(w)
    assert right.boundingBox().yMinimum() == pytest.approx(-w)
    assert primary.area() == pytest.approx(w * 100000)
    assert left.area() == pytest.approx(w * 50000)
    assert right.area() == pytest.approx(w * 50000)
    for geometry in (primary, left, right):
        assert geometry.isGeosValid()
        assert geometry.boundingBox().xMinimum() == 0
        assert geometry.boundingBox().xMaximum() == 100000
    assert primary.intersection(left).area() == 0
    assert primary.intersection(right).area() == 0
    assert left.intersection(right).area() == 0
    assert primary.combine(left).combine(right).area() == pytest.approx(w * 200000)


def test_oblique_reversal():
    from Q_Pansopy.modules.pbn.pbn_enroute_gnss import build_enroute_geometry
    a, b = (500000, 1600000), (560000, 1680000)
    forward = build_enroute_geometry(a, b, 'rnav5')
    reverse = build_enroute_geometry(b, a, 'rnav5')
    for first, second in zip(forward, (reverse[0], reverse[2], reverse[1])):
        assert first.symDifference(second).area() < 1e-4


@pytest.mark.parametrize('identifier', ['rnav5', 'rnp4', 'rnav2', 'rnp2', 'arnp2', 'arnp1', 'rnav1', 'rnp03'])
def test_output_style_and_provenance(identifier):
    from Q_Pansopy.modules.pbn.pbn_enroute_gnss import resolve_spec
    source = route()
    source_id = source.selectedFeatures()[0].id()
    output = run(source, identifier)
    assert output.featureCount() == 3
    assert output.renderer().classAttribute() == 'Symbol'
    features = list(output.getFeatures())
    assert sorted(f['Symbol'] for f in features) == ['Primary Area', 'Secondary Area', 'Secondary Area']
    assert {f['nav_spec'] for f in features} == {resolve_spec(identifier).label}
    assert {f['sensor'] for f in features} == {'GNSS'}
    assert {f['source_fid'] for f in features} == {source_id}
    assert {f['half_width_nm'] for f in features} == {resolve_spec(identifier).half_width_nm}
    assert all(f['distance_nm'] > 0 for f in features)
    categories = {c.value(): c.symbol().clone() for c in output.renderer().categories()}
    assert categories['Primary Area'].symbolLayerCount() == 1
    assert categories['Secondary Area'].symbolLayer(0).layerType() == 'PointPatternFill'


@pytest.mark.parametrize('crs', ['EPSG:4326', 'EPSG:32616', 'EPSG:3857', 'EPSG:2227'])
@pytest.mark.parametrize('project_crs', ['EPSG:4326', 'EPSG:2227'])
def test_units_independent_of_input_and_project(crs, project_crs):
    from qgis.core import QgsProject, QgsCoordinateReferenceSystem
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem(project_crs))
    output = run(route(crs))
    primary = next(output.getFeatures()).geometry()
    w = 5.77 * 1852
    assert output.crs().mapUnits().name == 'Meters'
    assert primary.area() / (next(output.getFeatures())['distance_nm'] * 1852) == pytest.approx(w, rel=1e-7)


def test_antimeridian():
    output = run(route(points=((179.5, 10), (-179.5, 10))))
    assert all(f.geometry().isGeosValid() for f in output.getFeatures())
    assert next(output.getFeatures())['distance_nm'] < 100


@pytest.mark.parametrize('wkt', ['LINESTRING EMPTY', 'LINESTRING(0 0,0 0)',
                                'LINESTRING(0 0,1 1,2 0)'])
def test_invalid_geometries_leave_no_outputs(wkt):
    from qgis.core import QgsProject
    layer = route(wkt=wkt)
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError):
        run(layer)
    assert set(QgsProject.instance().mapLayers()) == before
    assert not QgsProject.instance().layerTreeRoot().findGroups()


def test_selection_spec_and_missing_style_fail_atomically(monkeypatch, tmp_path):
    import Q_Pansopy.modules.pbn.pbn_enroute_gnss as module
    from qgis.core import QgsProject
    layer = route()
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError):
        run(layer, 'unknown')
    layer.removeSelection()
    with pytest.raises(ValueError):
        run(layer)
    layer.selectAll()
    monkeypatch.setattr(module, 'STYLE_PATH', tmp_path / 'missing.qml')
    with pytest.raises(RuntimeError):
        run(layer)
    assert set(QgsProject.instance().mapLayers()) == before
    assert not QgsProject.instance().layerTreeRoot().findGroups()


def test_dock_all_specs(qgis_app):
    from qgis.PyQt.QtWidgets import QMainWindow
    from qgis.gui import QgsMessageBar
    from Q_Pansopy.dockwidgets.pbn.qpansopy_pbn_enroute_gnss_dockwidget import QPANSOPYPBNEnrouteGNSSDockWidget
    from Q_Pansopy.modules.pbn.pbn_enroute_gnss import SPECS
    layer = route()
    window = QMainWindow()
    bar = QgsMessageBar(window)
    iface = SimpleNamespace(mainWindow=lambda: window, messageBar=lambda: bar, activeLayer=lambda: layer)
    dock = QPANSOPYPBNEnrouteGNSSDockWidget(iface)
    try:
        assert 'How to verify' in dock.measurementTitleLabel.text()
        assert '±5.77 NM, not ±5 NM' in dock.measurementHintLabel.text()
        assert 'Cartesian' in dock.measurementHintLabel.text()
        assert dock.specComboBox.count() == 8
        assert dock.specComboBox.currentData() == 'rnav5'
        dock.routingLayerComboBox.setLayer(layer)
        for index, spec in enumerate(SPECS):
            dock.specComboBox.setCurrentIndex(index)
            assert f'±{spec.half_width_nm:g}' in dock.outputDescriptionLabel.text()
            dock.calculate()
            assert 'Error:' not in dock.logTextEdit.toPlainText()
            assert dock.calculateButton.isEnabled()
    finally:
        dock.close()
        window.close()
        dock.deleteLater()
        window.deleteLater()
        qgis_app.processEvents()


def test_pbn_menu_and_toolbar_open_the_registered_dock(qgis_app, monkeypatch):
    from qgis.PyQt import QtWidgets
    from qgis.gui import QgsMessageBar
    import Q_Pansopy.qpansopy as plugin_module

    assert not plugin_module._IMPORT_ERRORS
    window = QtWidgets.QMainWindow()
    bar = QgsMessageBar(window)

    def toolbar(name):
        result = QtWidgets.QToolBar(name, window)
        window.addToolBar(result)
        return result

    def fail_dialog(*args):
        pytest.fail(str(args))

    monkeypatch.setattr(plugin_module.QMessageBox, 'critical', fail_dialog)
    iface = SimpleNamespace(
        mainWindow=lambda: window, addToolBar=toolbar, messageBar=lambda: bar,
        activeLayer=lambda: None, addDockWidget=window.addDockWidget,
        removeDockWidget=window.removeDockWidget,
    )
    plugin = plugin_module.Qpansopy(iface)
    try:
        plugin.initGui()
        action = next(a for a in plugin.submenus['PBN'].actions()
                      if a.text() == 'ENR — PBN GNSS (straight)')
        assert action in plugin.toolbars['PBN'].actions()
        assert not action.icon().isNull()
        action.trigger()
        widget = plugin.modules['PBN_ENROUTE_GNSS']['GUI_INSTANCE']
        assert isinstance(widget, plugin_module.QPANSOPYPBNEnrouteGNSSDockWidget)
        assert widget.specComboBox.currentData() == 'rnav5'
        widget.close()
        assert plugin.modules['PBN_ENROUTE_GNSS']['GUI_INSTANCE'] is None
    finally:
        plugin.unload()
        window.close()
        window.deleteLater()
        qgis_app.processEvents()


@pytest.mark.parametrize('kind,wkt', [
    ('MultiLineString', 'MULTILINESTRING((0 0,1 1))'),
    ('CircularString', 'CIRCULARSTRING(0 0,1 1,2 0)'),
    ('Point', 'POINT(0 0)'),
])
def test_reject_unsupported_geometry_types(kind, wkt):
    from qgis.core import QgsVectorLayer, QgsGeometry, QgsFeature, QgsProject
    layer = QgsVectorLayer(kind + '?crs=EPSG:4326', 'Invalid route', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError):
        run(layer)
    assert set(QgsProject.instance().mapLayers()) == before
    assert not QgsProject.instance().layerTreeRoot().findGroups()


def test_multiple_selection_and_invalid_crs():
    from qgis.core import QgsProject, QgsFeature, QgsCoordinateReferenceSystem
    layer = route()
    feature = QgsFeature(next(layer.getFeatures()))
    feature.setId(-1)
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    with pytest.raises(ValueError, match='exactly one'):
        run(layer)
    layer.setCrs(QgsCoordinateReferenceSystem())
    with pytest.raises(ValueError, match='valid CRS'):
        run(layer)
    assert not QgsProject.instance().layerTreeRoot().findGroups()


@pytest.mark.parametrize('value', [float('nan'), float('inf')])
def test_nonfinite_geometry_coordinates(value):
    from Q_Pansopy.modules.pbn.pbn_enroute_gnss import build_enroute_geometry
    with pytest.raises(ValueError, match='finite'):
        build_enroute_geometry((value, 0), (1000, 0), 'rnav5')



@pytest.mark.parametrize('points', [((-87, 14), (-86, 14.5)),
                                  ((-86.8, 15), (-86, 15.3)),
                                  ((-86.5, 15.7), (-86.3, 16.3))])
@pytest.mark.parametrize('identifier,expected', [('rnav2', 9260.0), ('rnav5', 10686.04)])
@pytest.mark.parametrize('fraction', [0.0, 0.5, 1.0])
def test_local_width_and_utm_measurement_are_distinct(points, identifier, expected, fraction):
    import math
    from qgis.core import (QgsCoordinateTransform, QgsCoordinateReferenceSystem,
                           QgsProject, QgsPointXY, QgsLayerNotesUtils)
    source = route(points=points)
    output = run(source, identifier)
    transform = QgsCoordinateTransform(source.crs(), output.crs(), QgsProject.instance())
    a, b = [transform.transform(p) for p in next(source.getFeatures()).geometry().asPolyline()]
    position = QgsPointXY(a.x() + fraction * (b.x() - a.x()), a.y() + fraction * (b.y() - a.y()))
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy)
    primary, left, right = [f.geometry() for f in output.getFeatures()]

    def edge_point(geometry, start_index, end_index):
        ring = geometry.asPolygon()[0]
        first, last = ring[start_index], ring[end_index]
        return QgsPointXY(first.x() + fraction * (last.x() - first.x()),
                          first.y() + fraction * (last.y() - first.y()))

    # Sample actual longitudinal polygon edges, including their endpoint vertices.
    boundaries = ((edge_point(primary, 0, 1), expected / 2),
                  (edge_point(primary, 3, 2), expected / 2),
                  (edge_point(left, 3, 2), expected),
                  (edge_point(right, 0, 1), expected))
    for point, nominal in boundaries:
        px, py = point.x() - position.x(), point.y() - position.y()
        assert math.hypot(px, py) == pytest.approx(nominal, abs=1e-6)
        assert abs((px * dx + py * dy) / length) < 1e-6
    corner = boundaries[2][0]
    utm = QgsCoordinateTransform(output.crs(), QgsCoordinateReferenceSystem('EPSG:32616'),
                                 QgsProject.instance())
    grid_a, grid_corner = utm.transform(position), utm.transform(corner)
    grid_width = math.hypot(grid_corner.x() - grid_a.x(), grid_corner.y() - grid_a.y())
    assert 0.1 < abs(grid_width - expected) < 10
    notes = QgsLayerNotesUtils.layerNotes(output)
    assert 'local AEQD CRS' in notes and 'Cartesian' in notes
