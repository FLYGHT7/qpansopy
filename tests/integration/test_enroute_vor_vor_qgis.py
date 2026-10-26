"""Real QGIS proof of simplified straight VOR/VOR geometry and workflow."""

import math
from types import SimpleNamespace

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.qgis_runtime]


@pytest.fixture(scope='session')
def qgis_app():
    from qgis.core import QgsApplication

    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


@pytest.fixture(autouse=True)
def clear_project(qgis_app):
    from qgis.core import QgsProject

    QgsProject.instance().clear()
    yield
    QgsProject.instance().clear()


def _pair(distance_m=200000.0, crs='EPSG:4326', origin=(-87.0, 14.0), bearing=90):
    from qgis.core import (
        QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea,
        QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
    )

    project = QgsProject.instance()
    source_crs = QgsCoordinateReferenceSystem('EPSG:4326')
    layer = QgsVectorLayer(f'Point?crs={crs}', 'VOR stations', 'memory')
    da = QgsDistanceArea()
    da.setSourceCrs(source_crs, project.transformContext())
    da.setEllipsoid('WGS84')
    a = QgsPointXY(*origin)
    b = da.computeSpheroidProject(a, distance_m, math.radians(bearing))
    transform = QgsCoordinateTransform(source_crs, layer.crs(), project)
    for point in (a, b):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(transform.transform(point)))
        assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    project.addMapLayer(layer)
    return layer


def _run(layer, include=False):
    from Q_Pansopy.modules.conv.enroute_vor_vor import run_enroute_vor_vor

    messages = []
    iface = SimpleNamespace(messageBar=lambda: SimpleNamespace(
        pushMessage=lambda *args, **kwargs: messages.append(args)))
    assert run_enroute_vor_vor(iface, layer, {'include_construction_lines': include})
    return _outputs()


def _outputs():
    from qgis.core import QgsProject

    group = QgsProject.instance().layerTreeRoot().children()[0]
    return {node.name(): node.layer() for node in group.children()}


def test_case_one_has_exact_capsule_radii_and_disjoint_buffer():
    from Q_Pansopy.modules.conv.enroute_vor_vor import build_enroute_geometry

    result = build_enroute_geometry((0, 0), (150000, 0))
    primary, buffer = result.primary, result.buffer
    exterior = primary.combine(buffer)
    assert result.profile.case == 1
    assert len(result.construction_lines) == 1
    axis = result.construction_lines[0]
    assert (axis.role, axis.splay_pct, axis.start, axis.end) == ('Axis', 0, (0, 0), (150000, 0))
    for geometry, radius in ((primary, 9300), (exterior, 18500)):
        bounds = geometry.boundingBox()
        assert bounds.xMinimum() == pytest.approx(-radius)
        assert bounds.xMaximum() == pytest.approx(150000 + radius)
        assert bounds.yMinimum() == pytest.approx(-radius)
        assert bounds.yMaximum() == pytest.approx(radius)
        expected_area = 2 * radius * 150000 + math.pi * radius ** 2
        assert geometry.area() == pytest.approx(expected_area, rel=2e-6)
        assert geometry.isGeosValid()
    assert primary.intersection(buffer).area() == pytest.approx(0, abs=1e-5)
    assert buffer.area() == pytest.approx(exterior.area() - primary.area(), abs=1e-4)


def test_case_two_preserves_round_ends_and_has_a_perpendicular_3700m_margin():
    from qgis.core import QgsGeometry, QgsPointXY
    from Q_Pansopy.modules.conv.enroute_vor_vor import build_enroute_geometry

    result = build_enroute_geometry((0, 0), (200000, 0))
    exterior = result.primary.combine(result.buffer)
    assert result.profile.case == 2
    assert result.primary.boundingBox().yMaximum() == pytest.approx(10000.0)
    assert exterior.boundingBox().yMaximum() == pytest.approx(19747.06071474696)
    assert exterior.boundingBox().xMinimum() == pytest.approx(-18500)
    assert exterior.boundingBox().xMaximum() == pytest.approx(218500)
    upper = 0.16 * 95000 + 3700 * math.hypot(1, 0.16)
    point = QgsGeometry.fromPointXY(QgsPointXY(95000, upper))
    splay = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(100000, 16000)])
    assert point.distance(splay) == pytest.approx(3700.0, abs=1e-8)
    assert exterior.closestSegmentWithContext(QgsPointXY(95000, upper))[0] == pytest.approx(0.0, abs=1e-12)
    assert result.primary.isGeosValid() and result.buffer.isGeosValid()
    assert result.primary.intersection(result.buffer).area() == pytest.approx(0, abs=1e-5)
    assert len(result.construction_lines) == 9
    assert [line.splay_pct for line in result.construction_lines].count(10) == 4
    assert [line.splay_pct for line in result.construction_lines].count(16) == 4


@pytest.mark.parametrize('angle', [0, 37, -62, 180])
def test_geometry_is_symmetric_under_station_reversal_and_rotation(angle):
    from qgis.core import QgsPointXY
    from Q_Pansopy.modules.conv.enroute_vor_vor import build_enroute_geometry

    origin = (500000, 1600000)
    theta = math.radians(angle)
    end = (origin[0] + 200000 * math.cos(theta), origin[1] + 200000 * math.sin(theta))
    forward = build_enroute_geometry(origin, end)
    reverse = build_enroute_geometry(end, origin)
    base = build_enroute_geometry((0, 0), (200000, 0))
    for name in ('primary', 'buffer'):
        geometry = getattr(forward, name)
        assert geometry.hausdorffDistance(getattr(reverse, name)) < 1e-6
        expected = getattr(base, name)
        expected.rotate(-angle, QgsPointXY(0, 0))
        expected.translate(*origin)
        assert geometry.hausdorffDistance(expected) < 1e-6


@pytest.mark.parametrize('distance,case,include', [
    (150000, 1, False), (150000, 1, True),
    (200000, 2, False), (200000, 2, True),
    (99.6 * 1852 - 0.1, 1, False), (99.6 * 1852 + 0.1, 2, True),
])
def test_two_separate_layers_and_optional_construction(distance, case, include):
    from qgis.core import QgsLayerNotesUtils, QgsProject

    outputs = _run(_pair(distance), include)
    expected = {'Primary area', 'Buffer area'}
    if include:
        expected.add('VOR/VOR construction lines')
    assert set(outputs) == expected
    primary, buffer = outputs['Primary area'], outputs['Buffer area']
    for name, layer in (('Primary area', primary), ('Buffer area', buffer)):
        assert layer.featureCount() == 1
        feature = next(layer.getFeatures())
        assert feature['area_type'] == name
        assert feature['case'] == case
        assert feature['distance_nm'] == pytest.approx(distance / 1852, abs=1e-8)
        assert feature.geometry().isGeosValid()
        assert '9300/18500' in QgsLayerNotesUtils.layerNotes(layer)
    assert primary.renderer().symbol().color().name() == '#ffffff'
    assert buffer.renderer().symbol().color().name() == '#cdcdcd'
    assert all(node.isVisible() for node in QgsProject.instance().layerTreeRoot().children()[0].children())
    if include:
        lines = outputs['VOR/VOR construction lines']
        assert lines.featureCount() == (1 if case == 1 else 9)
        if case == 2:
            assert sum(f['splay_pct'] == 10 for f in lines.getFeatures()) == 4
            assert sum(f['splay_pct'] == 16 for f in lines.getFeatures()) == 4


@pytest.mark.parametrize('distance', [150000, 200000])
def test_construction_option_does_not_change_output_polygons(distance):
    pair = _pair(distance)
    without = _run(pair, False)
    with_lines = _run(pair, True)
    for name in ('Primary area', 'Buffer area'):
        first = next(without[name].getFeatures()).geometry()
        second = next(with_lines[name].getFeatures()).geometry()
        assert first.asWkb() == second.asWkb()


@pytest.mark.parametrize('crs', ['EPSG:4326', 'EPSG:32616', 'EPSG:3857', 'EPSG:2227'])
def test_input_crs_does_not_change_geodesic_distance_or_criteria(crs):
    outputs = _run(_pair(crs=crs))
    feature = next(outputs['Primary area'].getFeatures())
    assert feature['distance_nm'] == pytest.approx(200000 / 1852, abs=1e-7)
    assert feature['case'] == 2
    assert outputs['Primary area'].crs().isValid()
    assert outputs['Primary area'].crs().mapUnits().name == 'Meters'


@pytest.mark.parametrize('origin,bearing', [((179.5, 10), 90), ((30, 75), 130)])
def test_local_crs_handles_antimeridian_and_high_latitude_routes(origin, bearing):
    outputs = _run(_pair(origin=origin, bearing=bearing))
    assert next(outputs['Primary area'].getFeatures())['distance_nm'] == pytest.approx(200000 / 1852, abs=1e-7)


@pytest.mark.parametrize('selection', [[], [0]])
def test_invalid_selection_has_no_partial_outputs(selection):
    from qgis.core import QgsProject
    from Q_Pansopy.modules.conv.enroute_vor_vor import run_enroute_vor_vor

    pair = _pair()
    ids = [feature.id() for feature in pair.getFeatures()]
    pair.selectByIds([ids[index] for index in selection])
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError, match='exactly two'):
        run_enroute_vor_vor(None, pair)
    assert set(QgsProject.instance().mapLayers()) == before
    assert not QgsProject.instance().layerTreeRoot().findGroups()


def test_selecting_more_than_two_stations_is_rejected():
    from qgis.core import QgsFeature, QgsProject
    from Q_Pansopy.modules.conv.enroute_vor_vor import run_enroute_vor_vor

    pair = _pair()
    feature = QgsFeature(pair.fields())
    feature.setGeometry(next(pair.getFeatures()).geometry())
    assert pair.dataProvider().addFeature(feature)
    pair.selectAll()
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError, match='exactly two'):
        run_enroute_vor_vor(None, pair)
    assert set(QgsProject.instance().mapLayers()) == before


@pytest.mark.parametrize('invalid', ['coincident', 'empty', 'invalid_crs', 'multipart'])
def test_invalid_station_inputs_create_no_outputs(invalid):
    from qgis.core import QgsCoordinateReferenceSystem, QgsGeometry, QgsProject
    from Q_Pansopy.modules.conv.enroute_vor_vor import run_enroute_vor_vor

    pair = _pair()
    if invalid == 'invalid_crs':
        pair.setCrs(QgsCoordinateReferenceSystem())
    else:
        features = list(pair.getFeatures())
        geometry = {
            'coincident': features[0].geometry(),
            'empty': QgsGeometry(),
            'multipart': QgsGeometry.fromWkt('MULTIPOINT ((-87 14), (-86 14))'),
        }[invalid]
        assert pair.startEditing()
        assert pair.changeGeometry(features[1].id(), geometry)
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError):
        run_enroute_vor_vor(None, pair)
    assert set(QgsProject.instance().mapLayers()) == before
    assert not QgsProject.instance().layerTreeRoot().findGroups()


def test_dock_creates_both_outputs_and_restores_its_controls(qgis_app):
    from qgis.PyQt import QtWidgets
    from qgis.gui import QgsMessageBar
    from Q_Pansopy.dockwidgets.conv.qpansopy_enroute_vor_vor_dockwidget import QPANSOPYEnrouteVorVorDockWidget

    pair = _pair()
    window = QtWidgets.QMainWindow()
    bar = QgsMessageBar(window)
    iface = SimpleNamespace(mainWindow=lambda: window, messageBar=lambda: bar, activeLayer=lambda: pair)
    widget = QPANSOPYEnrouteVorVorDockWidget(iface)
    try:
        assert not widget.constructionCheckBox.isChecked()
        assert widget.formScrollArea.widgetResizable()
        widget.vorLayerComboBox.setLayer(pair)
        widget.calculate()
        assert set(_outputs()) == {'Primary area', 'Buffer area'}, widget.logTextEdit.toPlainText()
        assert 'Case 2' in widget.logTextEdit.toPlainText()
        assert widget.calculateButton.isEnabled() and not widget._calculating
        assert QtWidgets.QApplication.overrideCursor() is None
        widget.constructionCheckBox.setChecked(True)
        widget.calculate()
        assert 'VOR/VOR construction lines' in _outputs()
        pair.removeSelection()
        widget.calculate()
        assert 'exactly two' in widget.logTextEdit.toPlainText()
        assert widget.calculateButton.isEnabled() and not widget._calculating
        assert QtWidgets.QApplication.overrideCursor() is None
    finally:
        widget.close()
        window.close()
        widget.deleteLater()
        window.deleteLater()
        qgis_app.processEvents()


def test_conv_menu_and_toolbar_open_the_registered_dock(qgis_app, monkeypatch):
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
        action = next(a for a in plugin.submenus['CONV'].actions()
                      if a.text() == 'Simplified ENR — VOR/VOR (straight)')
        assert action in plugin.toolbars['CONV'].actions()
        assert not action.icon().isNull()
        action.trigger()
        widget = plugin.modules['ENROUTE_VOR_VOR']['GUI_INSTANCE']
        assert isinstance(widget, plugin_module.QPANSOPYEnrouteVorVorDockWidget)
        assert not widget.constructionCheckBox.isChecked()
        widget.close()
        assert plugin.modules['ENROUTE_VOR_VOR']['GUI_INSTANCE'] is None
    finally:
        plugin.unload()
        window.close()
        window.deleteLater()
        qgis_app.processEvents()


@pytest.mark.parametrize('reverse', [False, True])
def test_case_one_centerline_follows_oblique_station_order(reverse):
    from Q_Pansopy.modules.conv.enroute_vor_vor import build_enroute_geometry

    a, b = (500000, 1600000), (560000, 1680000)
    if reverse:
        a, b = b, a
    result = build_enroute_geometry(a, b)
    assert result.profile.case == 1
    assert len(result.construction_lines) == 1
    axis = result.construction_lines[0]
    assert (axis.role, axis.splay_pct, axis.start, axis.end) == ('Axis', 0, a, b)


@pytest.mark.parametrize('offset,case,count', [(0, 1, 1), (0.1, 2, 9)])
def test_construction_at_case_boundary(offset, case, count):
    from Q_Pansopy.modules.conv.enroute_vor_vor import CASE_ONE_LIMIT_M, build_enroute_geometry

    result = build_enroute_geometry((0, 0), (CASE_ONE_LIMIT_M + offset, 0))
    assert result.profile.case == case
    assert len(result.construction_lines) == count


@pytest.mark.parametrize('crs', ['EPSG:4326', 'EPSG:32616'])
def test_case_one_construction_layer_matches_station_centers(crs):
    from qgis.core import QgsCoordinateTransform, QgsProject

    pair = _pair(150000, crs=crs, bearing=37)
    outputs = _run(pair, True)
    lines = outputs['VOR/VOR construction lines']
    assert lines.crs() == outputs['Primary area'].crs()
    assert lines.crs().mapUnits().name == 'Meters'
    assert lines.featureCount() == 1
    feature = next(lines.getFeatures())
    assert feature['role'] == 'Axis' and feature['splay_pct'] == 0
    vertices = feature.geometry().asPolyline()
    assert len(vertices) == 2
    transform = QgsCoordinateTransform(pair.crs(), lines.crs(), QgsProject.instance())
    stations = sorted(pair.selectedFeatures(), key=lambda station: station.id())
    for vertex, station in zip(vertices, stations):
        expected = transform.transform(station.geometry().asPoint())
        assert vertex.x() == pytest.approx(expected.x(), abs=1e-4)
        assert vertex.y() == pytest.approx(expected.y(), abs=1e-4)


def test_case_one_dock_loads_centerline(qgis_app):
    from qgis.PyQt import QtWidgets
    from qgis.gui import QgsMessageBar
    from Q_Pansopy.dockwidgets.conv.qpansopy_enroute_vor_vor_dockwidget import QPANSOPYEnrouteVorVorDockWidget

    pair = _pair(150000)
    window = QtWidgets.QMainWindow()
    bar = QgsMessageBar(window)
    iface = SimpleNamespace(mainWindow=lambda: window, messageBar=lambda: bar, activeLayer=lambda: pair)
    widget = QPANSOPYEnrouteVorVorDockWidget(iface)
    try:
        assert not widget.constructionCheckBox.isChecked()
        assert widget.constructionCheckBox.text() == 'Load construction lines'
        widget.vorLayerComboBox.setLayer(pair)
        widget.constructionCheckBox.setChecked(True)
        widget.calculate()
        assert _outputs()['VOR/VOR construction lines'].featureCount() == 1
        assert 'Loaded the centerline between the two VOR stations.' in widget.logTextEdit.toPlainText()
        assert 'eight 10%/16%' not in widget.logTextEdit.toPlainText()
        assert widget.calculateButton.isEnabled() and not widget._calculating
        assert QtWidgets.QApplication.overrideCursor() is None
    finally:
        widget.close()
        window.close()
        widget.deleteLater()
        window.deleteLater()
        qgis_app.processEvents()
