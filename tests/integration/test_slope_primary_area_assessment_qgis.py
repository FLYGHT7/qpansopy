"""Real-QGIS proof of slope geometry, data sources, output, and dock wiring."""

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


def _geometry_layer(kind, wkt, crs='EPSG:32616'):
    from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer(f'{kind}?crs={crs}', kind, 'memory')
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    return layer


def _area(crs='EPSG:32616', wkt=None):
    return _geometry_layer('Polygon', wkt or (
        'POLYGON ((-10000 -10000, 10000 -10000, 10000 10000, '
        '-10000 10000, -10000 -10000))'
    ), crs)


def _reference(wkt='LINESTRING (0 0, 10 0)', crs='EPSG:32616'):
    return _geometry_layer('LineString', wkt, crs)


def _survey(rows=None, crs='EPSG:32616'):
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer(f'Point?crs={crs}', 'survey', 'memory')
    layer.dataProvider().addAttributes([
        QgsField('id', QVariant.String), QgsField('obstacle_type', QVariant.String),
        QgsField('elev', QVariant.Double), QgsField('tolerances', QVariant.Double),
    ])
    layer.updateFields()
    for index, (wkt, elevation, tolerance) in enumerate(
        [('POINT (1500 4679.075)', 1106.0, 0.0)] if rows is None else rows
    ):
        feature = QgsFeature(layer.fields())
        feature.setAttributes([str(index), 'building', elevation, tolerance])
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        assert layer.dataProvider().addFeature(feature)
    return layer


def _run(area=None, reference=None, survey=None, **kwargs):
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import run_slope_primary_area_assessment

    return run_slope_primary_area_assessment(
        None, _area() if area is None else area,
        _reference() if reference is None else reference,
        obstacle_layer=_survey() if survey is None else survey,
        field_mapping=FieldMapping('id', 'obstacle_type', 'elev', 'tolerances'),
        **kwargs,
    )


def test_video_example_loads_all_points_with_slope_fields_and_style():
    from qgis.core import QgsCategorizedSymbolRenderer, QgsLayerNotesUtils, QgsProject

    result = _run(surface_elevation_m=1008.0, slope_angle_deg=1.88)
    layer = result.assessment_layer
    point = next(layer.getFeatures())

    assert point['x_dist'] == pytest.approx(4679.075)
    assert point['surface_z'] == pytest.approx(1161.585820458, abs=1e-9)
    assert point['clearance'] == pytest.approx(55.585820458, abs=1e-9)
    assert point['penetrates'] == 'clear'
    assert point['area_eval'] == 'slope primary area'
    assert result.assessed_count == 1
    assert result.penetration_count == 0
    assert layer.fields().names() == [
        'id', 'layer_type', 'obstacle_type', 'elev', 'tolerances',
        'applied_tolerance', 'area_eval', 'x_dist', 'surface_z',
        'clearance', 'penetrates',
    ]
    assert isinstance(layer.renderer(), QgsCategorizedSymbolRenderer)
    assert layer.renderer().classAttribute() == 'penetrates'
    assert [category.value() for category in layer.renderer().categories()] == ['clear', 'penetrates']
    assert [category.symbol().color().name() for category in layer.renderer().categories()] == ['#238b45', '#d71920']
    assert 'Slope angle: 1.88' in QgsLayerNotesUtils.layerNotes(layer)
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert group.children()[0].isVisible()
    assert [node.name() for node in group.children()] == ['Slope primary assessment']


@pytest.mark.parametrize('axis,point,distance', [
    ('LINESTRING (0 0, 10 0)', 'POINT (1500 -50)', 50.0),
    ('LINESTRING (10 0, 0 0)', 'POINT (-1500 50)', 50.0),
    ('LINESTRING (0 0, 0 10)', 'POINT (-50 1500)', 50.0),
    ('LINESTRING (0 0, 10 10)', 'POINT (20 10)', math.sqrt(50.0)),
    ('LINESTRING (10 10, 0 0)', 'POINT (20 10)', math.sqrt(50.0)),
    ('LINESTRING (0 0, 5 0, 10 0)', 'POINT (30 0)', 0.0),
])
def test_distance_is_absolute_perpendicular_to_extended_axis(axis, point, distance):
    result = _run(reference=_reference(axis), survey=_survey([(point, 0.0, 0.0)]), slope_angle_deg=-45.0)
    feature = next(result.assessment_layer.getFeatures())

    assert feature['x_dist'] == pytest.approx(distance)
    assert feature['surface_z'] == pytest.approx(-distance)


def test_feet_crs_is_converted_to_metres():
    crs = 'EPSG:2227'
    result = _run(
        area=_area(crs), reference=_reference(crs=crs),
        survey=_survey([('POINT (500 100)', 0.0, 0.0)], crs),
        slope_angle_deg=45.0,
    )
    feature = next(result.assessment_layer.getFeatures())
    assert feature['x_dist'] == pytest.approx(30.48006096)
    assert feature['surface_z'] == pytest.approx(30.48006096)


def test_buffer_includes_outside_points_and_displays_the_exact_mask():
    from qgis.core import QgsGeometry, QgsLayerNotesUtils, QgsProject

    area = _area(wkt='POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))')
    survey = _survey([('POINT (5 5)', 10.0, 0.0), ('POINT (11 5)', 11.0, 0.0)])
    original = _run(area=area, survey=survey)
    buffered = _run(area=area, survey=survey, area_buffer_m=2.0)

    assert original.assessed_count == 1
    assert original.buffer_layer is None
    assert buffered.assessed_count == 2
    assert buffered.penetration_count == 2
    assert buffered.buffer_layer.name() == 'Slope primary area buffer'
    mask = next(buffered.buffer_layer.getFeatures()).geometry()
    assert mask.intersects(QgsGeometry.fromWkt('POINT (11 5)'))
    assert 'Area buffer: 2 m' in QgsLayerNotesUtils.layerNotes(buffered.buffer_layer)
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert all(node.isVisible() for node in group.children())


def test_terrain_and_survey_keep_source_tolerances_and_skip_nodata(tmp_path):
    from qgis.core import QgsCoordinateReferenceSystem, QgsRasterLayer

    path = tmp_path / 'terrain.asc'
    path.write_text(
        'ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 10\n'
        'NODATA_value -9999\n100 -9999\n110 120\n', encoding='utf-8',
    )
    terrain = QgsRasterLayer(str(path), 'terrain')
    terrain.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    assert terrain.isValid()
    result = _run(
        survey=_survey([('POINT (8 8)', 100.0, 3.0)]),
        terrain_layer=terrain, terrain_tolerance_m=7.0,
        override_tolerance_m=12.0, surface_elevation_m=115.0,
    )
    points = list(result.assessment_layer.getFeatures())
    survey_point = next(point for point in points if point['layer_type'] == 'survey')
    terrain_points = [point for point in points if point['layer_type'] == 'DTM']

    assert result.assessed_count == 4
    assert result.penetration_count == 2
    assert result.warnings == ()
    assert survey_point['tolerances'] == 3.0
    assert survey_point['applied_tolerance'] == 12.0
    assert survey_point['clearance'] == 3.0
    assert len(terrain_points) == 3
    assert all(point['applied_tolerance'] == 7.0 for point in terrain_points)
    assert sorted(point['elev'] for point in terrain_points) == [100.0, 110.0, 120.0]


@pytest.mark.parametrize('wkt', [
    'LINESTRING (0 0, 5 2, 10 0)',
    'LINESTRING (0 0, 0 0)',
    'MULTILINESTRING ((0 0, 10 0), (0 1, 10 1))',
    'LINESTRING EMPTY',
])
def test_invalid_reference_geometry_creates_no_outputs(wkt):
    from qgis.core import QgsProject

    kind = 'MultiLineString' if wkt.startswith('MULTI') else 'LineString'
    reference = _geometry_layer(kind, wkt)
    with pytest.raises(ValueError):
        _run(reference=reference)
    assert not QgsProject.instance().mapLayers()
    assert not QgsProject.instance().layerTreeRoot().children()


def test_reference_requires_exactly_one_selected_feature():
    reference = _reference()
    reference.removeSelection()
    with pytest.raises(ValueError, match='exactly one'):
        _run(reference=reference)


@pytest.mark.parametrize('target,crs', [
    ('area', 'EPSG:4326'), ('survey', 'EPSG:32617'), ('reference', 'EPSG:32617'),
])
def test_crs_validation_precedes_result_creation(target, crs):
    from qgis.core import QgsCoordinateReferenceSystem, QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import CrsValidationError

    layers = {'area': _area(), 'reference': _reference(), 'survey': _survey()}
    layers[target].setCrs(QgsCoordinateReferenceSystem(crs))
    with pytest.raises(CrsValidationError):
        _run(**layers)
    assert not QgsProject.instance().mapLayers()


def test_declining_missing_data_leaves_project_unchanged():
    from qgis.core import QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import AssessmentCancelled

    with pytest.raises(AssessmentCancelled):
        _run(confirm_missing=lambda warnings: False)
    assert not QgsProject.instance().mapLayers()
    assert not QgsProject.instance().layerTreeRoot().children()


def test_accepting_empty_sources_loads_an_annotated_empty_result():
    from qgis.core import QgsLayerNotesUtils

    result = _run(survey=_survey([]), confirm_missing=lambda warnings: True)
    assert result.assessed_count == result.penetration_count == 0
    assert result.assessment_layer.featureCount() == 0
    assert len(result.warnings) == 2
    assert 'No terrain data' in QgsLayerNotesUtils.layerNotes(result.assessment_layer)


def test_at_least_one_source_is_required():
    from Q_Pansopy.modules.utilities.slope_primary_area_assessment import run_slope_primary_area_assessment

    with pytest.raises(ValueError, match='terrain or survey'):
        run_slope_primary_area_assessment(None, _area(), _reference())


def test_area_selection_and_overlap_do_not_duplicate_survey_points():
    from qgis.core import QgsFeature, QgsGeometry

    area = _area(wkt='POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))')
    first_id = next(area.getFeatures()).id()
    for wkt in (
        'POLYGON ((5 0, 15 0, 15 10, 5 10, 5 0))',
        'POLYGON ((20 0, 30 0, 30 10, 20 10, 20 0))',
    ):
        feature = QgsFeature(area.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        assert area.dataProvider().addFeature(feature)
    area.selectByIds([first_id])
    survey = _survey([('POINT (8 5)', 0.0, 0.0), ('POINT (25 5)', 0.0, 0.0)])

    assert _run(area=area, survey=survey).assessed_count == 1
    assert _run(area=area, survey=survey, use_selected_area=False).assessed_count == 2


@pytest.mark.parametrize('kwargs', [
    {'slope_angle_deg': 90.0}, {'surface_elevation_m': float('nan')},
    {'terrain_tolerance_m': -1.0}, {'override_tolerance_m': -1.0},
    {'area_buffer_m': -1.0}, {'terrain_band': 0},
])
def test_invalid_parameters_leave_project_unchanged(kwargs):
    from qgis.core import QgsProject

    with pytest.raises(ValueError):
        _run(**kwargs)
    assert not QgsProject.instance().mapLayers()


def test_dock_wires_the_video_inputs_and_restores_processing_state(qgis_app):
    from qgis.PyQt import QtWidgets
    from qgis.PyQt.QtCore import Qt
    from qgis.core import QgsProject
    from qgis.gui import QgsMessageBar
    from Q_Pansopy.dockwidgets.utilities.qpansopy_slope_primary_area_assessment_dockwidget import (
        QPANSOPYSlopePrimaryAreaAssessmentDockWidget,
    )

    window = QtWidgets.QMainWindow()
    bar = QgsMessageBar(window)
    area, reference, survey = _area(), _reference(), _survey()
    QgsProject.instance().addMapLayers([area, reference, survey])
    iface = SimpleNamespace(mainWindow=lambda: window, messageBar=lambda: bar, activeLayer=lambda: area)
    widget = QPANSOPYSlopePrimaryAreaAssessmentDockWidget(iface)
    try:
        assert widget.surfaceElevationDoubleSpinBox.value() == 0.0
        assert widget.slopeAngleDoubleSpinBox.value() == 0.0
        assert widget.terrainToleranceDoubleSpinBox.value() == 50.0
        widget.areaLayerComboBox.setLayer(area)
        widget.referenceLayerComboBox.setLayer(reference)
        widget.obstacleLayerComboBox.setLayer(survey)
        widget.surfaceElevationDoubleSpinBox.setValue(1008.0)
        widget.slopeAngleDoubleSpinBox.setValue(1.88)
        widget._confirm_missing = lambda warnings: True
        widget.calculate()
        layers = QgsProject.instance().mapLayersByName('Slope primary assessment')
        assert len(layers) == 1, widget.logTextEdit.toPlainText()
        feature = next(layers[0].getFeatures())
        assert feature['surface_z'] == pytest.approx(1161.585820458, abs=1e-9)
        assert '1 point(s), 0 penetrating point(s)' in widget.logTextEdit.toPlainText()
        assert widget.calculateButton.isEnabled()
        assert not widget._assessing
        assert widget._processing_message is None
        assert QtWidgets.QApplication.overrideCursor() is None
        assert widget.scrollArea.widgetResizable()
        assert widget.scrollArea.widget().isAncestorOf(widget.calculateButton)
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, widget)
        window.resize(550, 350)
        window.show()
        qgis_app.processEvents()
        assert widget.scrollArea.verticalScrollBar().maximum() > 0
    finally:
        widget.close()
        window.close()
        widget.deleteLater()
        window.deleteLater()
        qgis_app.processEvents()


def test_plugin_registers_the_tool_in_generic_menu_and_utilities_toolbar(qgis_app, monkeypatch):
    from qgis.PyQt import QtWidgets
    from qgis.gui import QgsMessageBar
    import Q_Pansopy.qpansopy as plugin_module

    assert not plugin_module._IMPORT_ERRORS
    window = QtWidgets.QMainWindow()
    bar = QgsMessageBar(window)

    def add_toolbar(name):
        toolbar = QtWidgets.QToolBar(name, window)
        window.addToolBar(toolbar)
        return toolbar

    def fail_dialog(*args):
        pytest.fail(str(args))

    monkeypatch.setattr(plugin_module.QMessageBox, 'critical', fail_dialog)
    iface = SimpleNamespace(
        mainWindow=lambda: window, addToolBar=add_toolbar,
        messageBar=lambda: bar, activeLayer=lambda: None,
        addDockWidget=window.addDockWidget, removeDockWidget=window.removeDockWidget,
    )
    plugin = plugin_module.Qpansopy(iface)
    try:
        plugin.initGui()
        actions = [action for action in plugin.submenus['GENERIC'].actions()
                   if action.text() == 'Slope Primary Area Assessment']
        assert len(actions) == 1
        assert not actions[0].icon().isNull()
        assert actions[0] in plugin.toolbars['UTILITIES'].actions()
        actions[0].trigger()
        widget = plugin.modules['SlopePrimaryAreaAssessment']['GUI_INSTANCE']
        assert widget is not None
        assert widget.windowTitle() == 'QPANSOPY - Slope Primary Area Assessment'
        widget.close()
        assert plugin.modules['SlopePrimaryAreaAssessment']['GUI_INSTANCE'] is None
    finally:
        plugin.unload()
        window.close()
        window.deleteLater()
        qgis_app.processEvents()


@pytest.fixture
def slope_dock(qgis_app):
    from qgis.PyQt import QtWidgets
    from qgis.core import QgsProject
    from qgis.gui import QgsMessageBar
    from Q_Pansopy.dockwidgets.utilities.qpansopy_slope_primary_area_assessment_dockwidget import (
        QPANSOPYSlopePrimaryAreaAssessmentDockWidget,
    )

    window = QtWidgets.QMainWindow()
    bar = QgsMessageBar(window)
    area, reference, survey = _area(), _reference(), _survey()
    QgsProject.instance().addMapLayers([area, reference, survey])
    iface = SimpleNamespace(mainWindow=lambda: window, messageBar=lambda: bar, activeLayer=lambda: area)
    widget = QPANSOPYSlopePrimaryAreaAssessmentDockWidget(iface)
    widget.areaLayerComboBox.setLayer(area)
    widget.referenceLayerComboBox.setLayer(reference)
    widget.obstacleLayerComboBox.setLayer(survey)
    widget.surfaceElevationDoubleSpinBox.setValue(1008.0)
    widget._confirm_missing = lambda warnings: True
    yield widget
    widget.close()
    window.close()
    widget.deleteLater()
    window.deleteLater()
    qgis_app.processEvents()


def _evaluate_dock(widget):
    from qgis.core import QgsProject

    project = QgsProject.instance()
    before = set(project.mapLayers())
    widget.calculate()
    layers = [layer for key, layer in project.mapLayers().items() if key not in before]
    assert len(layers) == 1, widget.logTextEdit.toPlainText()
    return next(layers[0].getFeatures()), layers[0]


def test_slope_units_default_to_degrees_and_preserve_existing_precision(slope_dock):
    assert slope_dock.slopeUnitComboBox.currentText() == '°'
    assert slope_dock.slopeAngleDoubleSpinBox.value() == 0.0
    assert slope_dock.slopeAngleDoubleSpinBox.decimals() == 4
    assert slope_dock.slopeAngleDoubleSpinBox.minimum() == -89.9999
    assert slope_dock.slopeAngleDoubleSpinBox.maximum() == 89.9999


@pytest.mark.parametrize('angle,percent', [(45.0, 100.0), (-45.0, -100.0), (0.0, 0.0)])
def test_slope_unit_switch_converts_the_visible_value(slope_dock, angle, percent):
    slope_dock.slopeAngleDoubleSpinBox.setValue(angle)
    slope_dock.slopeUnitComboBox.setCurrentText('%')
    assert slope_dock.slopeAngleDoubleSpinBox.value() == percent
    slope_dock.slopeUnitComboBox.setCurrentText('°')
    assert slope_dock.slopeAngleDoubleSpinBox.value() == angle


@pytest.mark.parametrize('percent', [100.0, -100.0, 200.0])
def test_percent_runs_the_complete_assessment_and_records_both_units(slope_dock, percent):
    from qgis.core import QgsLayerNotesUtils

    slope_dock.slopeUnitComboBox.setCurrentText('%')
    slope_dock.slopeAngleDoubleSpinBox.setValue(percent)
    feature, layer = _evaluate_dock(slope_dock)
    expected_surface = 1008.0 + 4679.075 * percent / 100.0
    assert feature['surface_z'] == pytest.approx(expected_surface, abs=1e-9)
    assert feature['clearance'] == pytest.approx(expected_surface - 1106.0, abs=1e-9)
    assert feature['penetrates'] == ('penetrates' if expected_surface < 1106.0 else 'clear')
    notes = QgsLayerNotesUtils.layerNotes(layer)
    assert f'Slope gradient: {percent:g} %' in notes
    assert 'Slope angle:' in notes and 'degrees' in notes


@pytest.mark.parametrize('unit,value', [('°', 1.88), ('%', 3.3)])
def test_repeated_unit_switches_preserve_the_unrounded_assessment(slope_dock, unit, value):
    slope_dock.slopeUnitComboBox.setCurrentText(unit)
    slope_dock.slopeAngleDoubleSpinBox.setValue(value)
    first, _ = _evaluate_dock(slope_dock)
    for _ in range(10):
        slope_dock.slopeUnitComboBox.setCurrentText('%')
        slope_dock.slopeUnitComboBox.setCurrentText('°')
    second, _ = _evaluate_dock(slope_dock)
    for field in ('x_dist', 'surface_z', 'clearance', 'penetrates'):
        assert second[field] == first[field]


def test_switching_units_cannot_flip_a_near_zero_penetration(slope_dock):
    # Rounding 1.88 degrees to 3.2824 percent would incorrectly clear this point.
    elevation = 1008.0 + 4679.075 * math.tan(math.radians(1.88)) + 0.00001
    survey = _survey([('POINT (1500 4679.075)', elevation, 0.0)])
    from qgis.core import QgsProject

    QgsProject.instance().addMapLayer(survey)
    slope_dock.obstacleLayerComboBox.setLayer(survey)
    slope_dock.slopeAngleDoubleSpinBox.setValue(1.88)
    first, _ = _evaluate_dock(slope_dock)
    slope_dock.slopeUnitComboBox.setCurrentText('%')
    assert slope_dock.slopeAngleDoubleSpinBox.value() == 3.2824
    second, _ = _evaluate_dock(slope_dock)
    assert first['penetrates'] == second['penetrates'] == 'penetrates'
    assert first['clearance'] == second['clearance']
    assert second['clearance'] < 0


def test_editing_percent_after_conversion_updates_the_canonical_slope(slope_dock):
    slope_dock.slopeAngleDoubleSpinBox.setValue(45.0)
    slope_dock.slopeUnitComboBox.setCurrentText('%')
    slope_dock.slopeAngleDoubleSpinBox.setValue(25.0)
    slope_dock.slopeUnitComboBox.setCurrentText('°')
    assert slope_dock.slopeAngleDoubleSpinBox.value() == pytest.approx(14.0362)
    feature, _ = _evaluate_dock(slope_dock)
    assert feature['surface_z'] == pytest.approx(1008.0 + 4679.075 * 0.25, abs=1e-9)


@pytest.mark.parametrize('angle', [-89.9999, 89.9999])
def test_unit_switch_keeps_the_existing_angular_limits(slope_dock, angle):
    slope_dock.slopeAngleDoubleSpinBox.setValue(angle)
    slope_dock.slopeUnitComboBox.setCurrentText('%')
    assert slope_dock.slopeAngleDoubleSpinBox.value() == pytest.approx(
        100.0 * math.tan(math.radians(angle)), abs=0.00005,
    )
    slope_dock.slopeUnitComboBox.setCurrentText('°')
    assert slope_dock.slopeAngleDoubleSpinBox.value() == angle
