"""Real QGIS proof of refined straight VOR/VOR geometry and workflow."""

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
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import run_enroute_vor_vor_refined

    messages = []
    iface = SimpleNamespace(messageBar=lambda: SimpleNamespace(
        pushMessage=lambda *args, **kwargs: messages.append(args)))
    assert run_enroute_vor_vor_refined(iface, layer, {'include_construction_lines': include})
    return _outputs()


def _outputs():
    from qgis.core import QgsProject

    group = next(group for group in QgsProject.instance().layerTreeRoot().findGroups(True)
                 if group.name().startswith('Refined ENR VOR/VOR'))
    return {node.name(): node.layer() for node in group.children()}


def test_case_one_has_exact_capsule_radii_and_disjoint_secondary():
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import build_enroute_geometry

    result = build_enroute_geometry((0, 0), (100000, 0))
    primary, secondary = result.primary, result.secondary
    exterior = primary.combine(secondary)
    assert result.profile.case == 1
    assert result.construction_lines == ()
    for geometry, radius in ((primary, 7400), (exterior, 14800)):
        bounds = geometry.boundingBox()
        assert bounds.xMinimum() == pytest.approx(-radius)
        assert bounds.xMaximum() == pytest.approx(100000 + radius)
        assert bounds.yMinimum() == pytest.approx(-radius)
        assert bounds.yMaximum() == pytest.approx(radius)
        expected_area = 2 * radius * 100000 + math.pi * radius ** 2
        assert geometry.area() == pytest.approx(expected_area, rel=2e-6)
        assert geometry.isGeosValid()
    assert primary.intersection(secondary).area() == pytest.approx(0, abs=1e-5)
    assert secondary.area() == pytest.approx(exterior.area() - primary.area(), abs=1e-4)


def test_case_two_preserves_round_ends_and_has_a_perpendicular_3700m_margin():
    from qgis.core import QgsGeometry, QgsPointXY
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import build_enroute_geometry

    result = build_enroute_geometry((0, 0), (200000, 0))
    exterior = result.primary.combine(result.secondary)
    assert result.profile.case == 2
    assert result.primary.boundingBox().yMaximum() == pytest.approx(10000.0)
    assert exterior.boundingBox().yMaximum() == pytest.approx(19747.06071474696)
    assert exterior.boundingBox().xMinimum() == pytest.approx(-14800)
    assert exterior.boundingBox().xMaximum() == pytest.approx(214800)
    upper = 0.16 * 95000 + 3700 * math.hypot(1, 0.16)
    point = QgsGeometry.fromPointXY(QgsPointXY(95000, upper))
    splay = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(100000, 16000)])
    assert point.distance(splay) == pytest.approx(3700.0, abs=1e-8)
    assert exterior.closestSegmentWithContext(QgsPointXY(95000, upper))[0] == pytest.approx(0.0, abs=1e-12)
    assert result.primary.isGeosValid() and result.secondary.isGeosValid()
    assert result.primary.intersection(result.secondary).area() == pytest.approx(0, abs=1e-5)
    assert len(result.construction_lines) == 9
    assert [line.splay_pct for line in result.construction_lines].count(10) == 4
    assert [line.splay_pct for line in result.construction_lines].count(16) == 4


@pytest.mark.parametrize('angle', [0, 37, -62, 180])
def test_geometry_is_symmetric_under_station_reversal_and_rotation(angle):
    from qgis.core import QgsPointXY
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import build_enroute_geometry

    origin = (500000, 1600000)
    theta = math.radians(angle)
    end = (origin[0] + 200000 * math.cos(theta), origin[1] + 200000 * math.sin(theta))
    forward = build_enroute_geometry(origin, end)
    reverse = build_enroute_geometry(end, origin)
    base = build_enroute_geometry((0, 0), (200000, 0))
    for name in ('primary', 'secondary'):
        geometry = getattr(forward, name)
        assert geometry.hausdorffDistance(getattr(reverse, name)) < 1e-6
        expected = getattr(base, name)
        expected.rotate(-angle, QgsPointXY(0, 0))
        expected.translate(*origin)
        assert geometry.hausdorffDistance(expected) < 1e-6


@pytest.mark.parametrize('distance,case,include', [
    (100000, 1, False), (100000, 1, True),
    (200000, 2, False), (200000, 2, True),
    (75 * 1852 - 0.1, 1, False), (75 * 1852 + 0.1, 2, True),
])
def test_two_separate_layers_and_optional_case_two_construction(distance, case, include):
    from qgis.core import QgsLayerNotesUtils, QgsProject

    outputs = _run(_pair(distance), include)
    expected = {'Primary area', 'Secondary area'}
    if include and case == 2:
        expected.add('VOR/VOR construction lines')
    assert set(outputs) == expected
    primary, secondary = outputs['Primary area'], outputs['Secondary area']
    for name, layer in (('Primary area', primary), ('Secondary area', secondary)):
        assert layer.featureCount() == 1
        feature = next(layer.getFeatures())
        assert feature['area_type'] == name
        assert feature['case'] == case
        assert feature['distance_nm'] == pytest.approx(distance / 1852, abs=1e-8)
        assert feature.geometry().isGeosValid()
        assert '7400/14800' in QgsLayerNotesUtils.layerNotes(layer)
    assert primary.renderer().symbol().color().name() == '#ffffff'
    assert secondary.renderer().symbol().color().name() == '#cdcdcd'
    assert all(node.isVisible() for node in QgsProject.instance().layerTreeRoot().findGroups()[0].children())
    if include and case == 2:
        lines = outputs['VOR/VOR construction lines']
        assert lines.featureCount() == 9
        assert sum(f['splay_pct'] == 10 for f in lines.getFeatures()) == 4


def test_construction_option_does_not_change_output_polygons():
    pair = _pair()
    without = _run(pair, False)
    with_lines = _run(pair, True)
    for name in ('Primary area', 'Secondary area'):
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
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import run_enroute_vor_vor_refined

    pair = _pair()
    ids = [feature.id() for feature in pair.getFeatures()]
    pair.selectByIds([ids[index] for index in selection])
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError, match='exactly two'):
        run_enroute_vor_vor_refined(None, pair)
    assert set(QgsProject.instance().mapLayers()) == before
    assert not QgsProject.instance().layerTreeRoot().findGroups()


def test_selecting_more_than_two_stations_is_rejected():
    from qgis.core import QgsFeature, QgsProject
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import run_enroute_vor_vor_refined

    pair = _pair()
    feature = QgsFeature(pair.fields())
    feature.setGeometry(next(pair.getFeatures()).geometry())
    assert pair.dataProvider().addFeature(feature)
    pair.selectAll()
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError, match='exactly two'):
        run_enroute_vor_vor_refined(None, pair)
    assert set(QgsProject.instance().mapLayers()) == before


@pytest.mark.parametrize('invalid', ['coincident', 'empty', 'invalid_crs', 'multipart'])
def test_invalid_station_inputs_create_no_outputs(invalid):
    from qgis.core import QgsCoordinateReferenceSystem, QgsGeometry, QgsProject
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import run_enroute_vor_vor_refined

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
        run_enroute_vor_vor_refined(None, pair)
    assert set(QgsProject.instance().mapLayers()) == before
    assert not QgsProject.instance().layerTreeRoot().findGroups()


def test_dock_creates_both_outputs_and_restores_its_controls(qgis_app):
    from qgis.PyQt import QtWidgets
    from qgis.gui import QgsMessageBar
    from Q_Pansopy.dockwidgets.conv.qpansopy_enroute_vor_vor_refined_dockwidget import (
        QPANSOPYEnrouteVorVorRefinedDockWidget,
    )

    pair = _pair()
    window = QtWidgets.QMainWindow()
    bar = QgsMessageBar(window)
    iface = SimpleNamespace(mainWindow=lambda: window, messageBar=lambda: bar, activeLayer=lambda: pair)
    widget = QPANSOPYEnrouteVorVorRefinedDockWidget(iface)
    try:
        assert not widget.constructionCheckBox.isChecked()
        assert widget.formScrollArea.widgetResizable()
        widget.vorLayerComboBox.setLayer(pair)
        widget.calculate()
        assert set(_outputs()) == {'Primary area', 'Secondary area'}, widget.logTextEdit.toPlainText()
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
                      if a.text() == 'Refined ENR — VOR/VOR (straight)')
        assert action in plugin.toolbars['CONV'].actions()
        assert not action.icon().isNull()
        action.trigger()
        widget = plugin.modules['ENROUTE_VOR_VOR_REFINED']['GUI_INSTANCE']
        assert isinstance(widget, plugin_module.QPANSOPYEnrouteVorVorRefinedDockWidget)
        assert not widget.constructionCheckBox.isChecked()
        widget.close()
        assert plugin.modules['ENROUTE_VOR_VOR_REFINED']['GUI_INSTANCE'] is None
    finally:
        plugin.unload()
        window.close()
        window.deleteLater()
        qgis_app.processEvents()


@pytest.mark.parametrize('distance,case,primary_peak,exterior_peak', [
    (100000, 1, 7400, 14800),
    (138900, 1, 7400, 14800),
    (140000, 2, 7400, 14947.06071474696),
    (148000, 2, 7400, 15587.06071474696),
    (160000, 2, 8000, 16547.06071474696),
])
def test_measured_cross_sections_match_the_refined_diagrams(distance, case, primary_peak, exterior_peak):
    from qgis.core import QgsGeometry, QgsPointXY
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import build_enroute_geometry

    result = build_enroute_geometry((0, 0), (distance, 0))
    assert result.profile.case == case
    section = QgsGeometry.fromPolylineXY([
        QgsPointXY(distance / 2, -30000), QgsPointXY(distance / 2, 30000),
    ])
    exterior = result.primary.combine(result.secondary)
    for area, expected in ((result.primary, primary_peak), (exterior, exterior_peak)):
        bounds = area.intersection(section).boundingBox()
        assert bounds.yMaximum() == pytest.approx(expected, abs=1e-7)
        assert bounds.yMinimum() == pytest.approx(-expected, abs=1e-7)


def test_case_two_axis_crosses_the_primary_round_ends():
    from Q_Pansopy.modules.conv.enroute_vor_vor_refined import build_enroute_geometry

    result = build_enroute_geometry((0, 0), (160000, 0))
    axis = next(line for line in result.construction_lines if line.role == 'Axis')
    assert axis.start == (-7400, 0)
    assert axis.end == (167400, 0)
    for line in result.construction_lines:
        if line.splay_pct:
            assert line.start in ((0, 0), (160000, 0))
            assert abs(line.end[1] / (line.end[0] - line.start[0])) == pytest.approx(line.splay_pct / 100)


@pytest.mark.parametrize('placement', ['root', 'nested', 'exclusive'])
@pytest.mark.parametrize('custom_order', [False, True])
def test_vor_stays_visible_above_opaque_areas_in_existing_drawing_order(placement, custom_order):
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor
    from qgis.core import (
        QgsCoordinateTransform, QgsMapRendererParallelJob, QgsMapSettings,
        QgsMarkerSymbol, QgsProject, QgsSingleSymbolRenderer, QgsVectorLayer,
    )

    pair = _pair(160000)
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    background = QgsVectorLayer('Point?crs=EPSG:4326', 'Other input', 'memory')
    project.addMapLayer(background)
    source_group = None
    if placement != 'root':
        source_group = root.insertGroup(0, 'Stations')
        node = root.findLayer(pair.id())
        source_group.addChildNode(node.clone())
        root.removeChildNode(node)
        if placement == 'exclusive':
            source_group.setIsMutuallyExclusive(True)
    if custom_order:
        root.setCustomLayerOrder(list(reversed(root.layerOrder())))
        root.setHasCustomLayerOrder(True)
    previous_order = list(root.layerOrder())
    station_node = root.findLayer(pair.id())
    station_parent = station_node.parent()
    pair.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple({
        'name': 'square', 'color': '255,0,0,255', 'outline_style': 'no', 'size': '7',
    })))
    outputs = _run(pair, True)
    group = root.findLayer(outputs['Primary area'].id()).parent()
    assert group.parent() == (root if placement in ('root', 'exclusive') else source_group)
    assert station_node.parent() == station_parent and station_node.isVisible()
    assert all(node.isVisible() for node in group.children())
    ordered_outputs = [node.layer() for node in group.children()]
    index = previous_order.index(pair) + 1
    assert root.layerOrder() == previous_order[:index] + ordered_outputs + previous_order[index:]
    assert root.hasCustomLayerOrder() == custom_order

    # Rendering the real tree order must preserve the source symbols over opaque fills.
    pair.removeSelection()
    settings = QgsMapSettings()
    settings.setDestinationCrs(outputs['Primary area'].crs())
    settings.setLayers(root.layerOrder())
    settings.setOutputSize(QSize(800, 320))
    settings.setBackgroundColor(QColor('white'))
    extent = outputs['Secondary area'].extent()
    extent.scale(1.1)
    settings.setExtent(extent)
    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    rendered = job.renderedImage()
    transform = QgsCoordinateTransform(pair.crs(), settings.destinationCrs(), project)
    for feature in pair.getFeatures():
        point = transform.transform(feature.geometry().asPoint())
        pixel = settings.mapToPixel().transform(point)
        assert rendered.pixelColor(round(pixel.x()), round(pixel.y())).name() == '#ff0000'


def test_dock_explains_automatic_case_selection(qgis_app):
    from qgis.PyQt import QtWidgets
    from Q_Pansopy.dockwidgets.conv.qpansopy_enroute_vor_vor_refined_dockwidget import (
        QPANSOPYEnrouteVorVorRefinedDockWidget,
    )

    window = QtWidgets.QMainWindow()
    iface = SimpleNamespace(mainWindow=lambda: window, activeLayer=lambda: None)
    widget = QPANSOPYEnrouteVorVorRefinedDockWidget(iface)
    try:
        hint = widget.outputDescriptionLabel.text()
        assert '75 NM' in hint and 'Case 1' in hint and 'Case 2' in hint and 'automatically' in hint
        assert not widget.constructionCheckBox.isChecked()
    finally:
        widget.close()
        window.close()
        widget.deleteLater()
        window.deleteLater()
        qgis_app.processEvents()
