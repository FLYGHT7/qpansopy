import math
from types import SimpleNamespace

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.qgis_runtime]


class _RecordingMessageBar:
    def __init__(self):
        self.messages = []
        self._items = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))
        self._items.append(object())

    def currentItem(self):
        return self._items[-1] if self._items else None

    def items(self):
        return list(self._items)

    def popWidget(self, item):
        self._items.remove(item)


class _DockIface:
    def __init__(self):
        self.message_bar = _RecordingMessageBar()

    def mainWindow(self):
        return None

    def messageBar(self):
        return self.message_bar

    def activeLayer(self):
        return None


@pytest.fixture(scope='module')
def qgis_app():
    try:
        from qgis.core import QgsApplication
    except ImportError:
        pytest.skip('QGIS Python bindings are not installed')

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


def _area_layer(wkt=None, crs='EPSG:32616'):
    from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer(f'Polygon?crs={crs}', 'area', 'memory')
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromWkt(wkt or (
        'POLYGON ((0 0, 500 0, 500 500, 0 500, 0 0))'
    )))
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    return layer


def _obstacle_layer(crs='EPSG:32616', records=None):
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer(f'Point?crs={crs}', 'survey', 'memory')
    layer.dataProvider().addAttributes([
        QgsField('survey_id', QVariant.String),
        QgsField('kind', QVariant.String),
        QgsField('elevation', QVariant.Double),
        QgsField('accuracy', QVariant.Double),
    ])
    layer.updateFields()
    for attributes, wkt in records or [
        (['A', 'building', 100.0, 5.0], 'POINT (100 100)'),
        (['B', 'tree', 101.0, 4.0], 'POINT (200 200)'),
        (['OUT', 'tree', 999.0, 1.0], 'POINT (600 600)'),
    ]:
        feature = QgsFeature(layer.fields())
        feature.setAttributes(attributes)
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        assert layer.dataProvider().addFeature(feature)
    return layer


def _mapping():
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping

    return FieldMapping(
        identifier='survey_id',
        obstacle_type='kind',
        elevation='elevation',
        tolerance='accuracy',
    )


def test_dockwidget_exposes_restored_assessment_controls(qgis_app):
    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_primary_area_assessment_dockwidget import (
            QPANSOPYPrimaryAreaAssessmentDockWidget,
        )

    widget = QPANSOPYPrimaryAreaAssessmentDockWidget(_DockIface())

    assert [
        widget.ocaRoundingComboBox.itemText(index)
        for index in range(widget.ocaRoundingComboBox.count())
    ] == ['1', '5', '10', '100']
    assert widget.ocaRoundingComboBox.currentText() == '100'
    assert widget.areaBufferDoubleSpinBox.value() == 0.0
    assert [
        widget.areaBufferUnitComboBox.itemText(index)
        for index in range(widget.areaBufferUnitComboBox.count())
    ] == ['NM', 'm']
    assert widget.areaBufferUnitComboBox.currentText() == 'NM'
    widget.close()


def test_dockwidget_passes_restored_assessment_options(
        qgis_app, monkeypatch):
    from qgis.core import QgsProject
    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_primary_area_assessment_dockwidget import (
            QPANSOPYPrimaryAreaAssessmentDockWidget,
        )
    from Q_Pansopy.modules.utilities import primary_area_assessment

    captured = {}

    def fake_assessment(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            assessed_count=0,
            control_count=0,
            warnings=(),
        )

    monkeypatch.setattr(
        primary_area_assessment,
        'run_primary_area_assessment',
        fake_assessment,
    )
    area = _area_layer()
    QgsProject.instance().addMapLayer(area)
    iface = _DockIface()
    widget = QPANSOPYPrimaryAreaAssessmentDockWidget(iface)
    widget.areaLayerComboBox.setLayer(area)
    widget.areaBufferDoubleSpinBox.setValue(2.0)
    widget.areaBufferUnitComboBox.setCurrentText('NM')
    widget.ocaRoundingComboBox.setCurrentText('10')
    widget.loadAllPointsCheckBox.setChecked(True)

    widget.calculate()

    assert captured['area_buffer_m'] == 3704.0
    assert captured['oca_rounding_ft'] == 10
    assert captured['load_all_points'] is True
    widget.close()


def test_missing_data_confirmation_releases_wait_cursor(
        qgis_app, monkeypatch):
    from Q_Pansopy.dockwidgets.utilities import (
        qpansopy_primary_area_assessment_dockwidget as dock_module,
    )

    state = {'cursor': object(), 'restored': 0, 'set': []}

    class _Application:
        @staticmethod
        def overrideCursor():
            return state['cursor']

        @staticmethod
        def restoreOverrideCursor():
            state['cursor'] = None
            state['restored'] += 1

        @staticmethod
        def setOverrideCursor(cursor):
            state['cursor'] = cursor
            state['set'].append(cursor)

    class _MessageBox:
        class StandardButton:
            Yes = 1
            No = 2

        @staticmethod
        def question(parent, title, message, buttons, default):
            assert state['cursor'] is None
            return _MessageBox.StandardButton.No

    monkeypatch.setattr(
        dock_module,
        'QtWidgets',
        SimpleNamespace(QApplication=_Application, QMessageBox=_MessageBox),
    )

    accepted = (
        dock_module.QPANSOPYPrimaryAreaAssessmentDockWidget._confirm_missing(
            object(), ('No terrain data was evaluated inside the mask',)
        )
    )

    assert not accepted
    assert state['restored'] == 1
    assert state['set'] == [dock_module.Qt_WaitCursor]


def test_survey_assessment_adds_annotated_group_and_tied_controls(qgis_app):
    from qgis.core import QgsLayerNotesUtils, QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    result = run_primary_area_assessment(
        None,
        _area_layer(),
        obstacle_layer=_obstacle_layer(),
        field_mapping=_mapping(),
        moc_m=75.0,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 2
    assert result.control_count == 2
    assert result.warnings == (
        'No terrain data was evaluated inside the mask',
    )
    assert QgsLayerNotesUtils.layerHasNotes(result.assessment_layer)
    assert QgsLayerNotesUtils.layerHasNotes(result.control_layer)
    assert 'MOC: 75 m' in QgsLayerNotesUtils.layerNotes(result.control_layer)
    assert result.control_layer.labelsEnabled()
    assert [
        layer.layerType()
        for layer in result.control_layer.renderer().symbol().symbolLayers()
    ] == ['GeometryGenerator', 'SvgMarker']
    assert all(
        layer.layerType() not in ('GeometryGenerator', 'SvgMarker')
        for layer in result.assessment_layer.renderer().symbol().symbolLayers()
    )
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert group.name() == 'Obstacle assessment'
    assert [node.layer().name() for node in group.children()] == [
        'Control obstacle', 'Primary assessment'
    ]
    for layer in (result.assessment_layer, result.control_layer):
        names = layer.fields().names()
        assert names.index('oca_pub_increment') + 1 == names.index('oca_pub_ft')
        assert 'oca_pub_ft' in layer.fields().names()
        assert all(
            isinstance(feature['oca_pub_ft'], int)
            and isinstance(feature['oca_pub_increment'], int)
            and feature['oca_pub_increment'] == 100
            for feature in layer.getFeatures()
        )
    assert {
        feature['oca_pub_ft']
        for feature in result.control_layer.getFeatures()
    } == {600}
    assert group.children()[0].itemVisibilityChecked()
    assert not group.children()[1].itemVisibilityChecked()


def test_zero_buffer_preserves_original_survey_mask(qgis_app):
    from qgis.core import QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    result = run_primary_area_assessment(
        None,
        _area_layer(),
        obstacle_layer=_obstacle_layer(),
        field_mapping=_mapping(),
        area_buffer_m=0.0,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 2
    identifiers = {
        feature['id'] for feature in result.assessment_layer.getFeatures()
    }
    assert identifiers == {'A', 'B'}
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert [node.layer().name() for node in group.children()] == [
        'Control obstacle', 'Primary assessment'
    ]


def test_buffer_includes_survey_point_outside_original_area(qgis_app):
    from qgis.core import QgsLayerNotesUtils, QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    result = run_primary_area_assessment(
        None,
        _area_layer(),
        obstacle_layer=_obstacle_layer(),
        field_mapping=_mapping(),
        area_buffer_m=150.0,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 3
    identifiers = {
        feature['id'] for feature in result.assessment_layer.getFeatures()
    }
    assert identifiers == {'A', 'B', 'OUT'}
    notes = QgsLayerNotesUtils.layerNotes(result.assessment_layer)
    assert 'Area buffer: 150 m' in notes
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert [node.layer().name() for node in group.children()] == [
        'Control obstacle', 'Primary assessment', 'Primary area buffer'
    ]
    assert group.children()[2].itemVisibilityChecked()


def test_positive_buffer_adds_visible_control_only_layer(qgis_app):
    from qgis.core import QgsLayerNotesUtils, QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        _build_mask_geometry,
        run_primary_area_assessment,
    )

    area = _area_layer()
    result = run_primary_area_assessment(
        None,
        area,
        obstacle_layer=_obstacle_layer(),
        field_mapping=_mapping(),
        area_buffer_m=150.0,
        load_all_points=False,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessment_layer is None
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert [node.layer().name() for node in group.children()] == [
        'Control obstacle', 'Primary area buffer'
    ]
    buffer_node = group.children()[1]
    buffer_layer = buffer_node.layer()
    assert buffer_node.itemVisibilityChecked()
    assert buffer_layer.crs() == area.crs()
    assert buffer_layer.featureCount() == 1
    buffered_feature = next(buffer_layer.getFeatures())
    assert buffered_feature.geometry().asWkb() == (
        _build_mask_geometry(area, True, 150.0).asWkb()
    )
    symbol_layer = buffer_layer.renderer().symbol().symbolLayer(0)
    assert 0 < symbol_layer.fillColor().alpha() < 255
    assert symbol_layer.strokeColor().alpha() == 255
    assert 'Area buffer: 150 m' in QgsLayerNotesUtils.layerNotes(buffer_layer)


def test_terrain_pixels_are_evaluated_without_processing_provider(
        qgis_app, tmp_path):
    from qgis.core import QgsCoordinateReferenceSystem, QgsRasterLayer
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    raster_path = tmp_path / 'terrain.asc'
    raster_path.write_text(
        'ncols 3\n'
        'nrows 3\n'
        'xllcorner 0\n'
        'yllcorner 0\n'
        'cellsize 100\n'
        'NODATA_value -9999\n'
        '1 2 3\n4 5 6\n7 8 9\n',
        encoding='ascii',
    )
    terrain = QgsRasterLayer(str(raster_path), 'terrain')
    assert terrain.isValid()
    terrain.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))

    result = run_primary_area_assessment(
        None,
        _area_layer(),
        terrain_layer=terrain,
        moc_m=75.0,
        terrain_tolerance_m=50.0,
        oca_rounding_ft=5,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 9
    assert result.control_count == 1
    control = next(result.control_layer.getFeatures())
    assert control['oca_pub_increment'] == 5
    assert control['elev'] == 9.0
    assert control['oca_m'] == 134.0
    assert control['oca_pub_ft'] == 440


def test_buffer_includes_terrain_cells_outside_original_area(
        qgis_app, tmp_path):
    from qgis.core import QgsCoordinateReferenceSystem, QgsRasterLayer
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    raster_path = tmp_path / 'buffered_terrain.asc'
    raster_path.write_text(
        'ncols 3\n'
        'nrows 3\n'
        'xllcorner 0\n'
        'yllcorner 0\n'
        'cellsize 100\n'
        'NODATA_value -9999\n'
        '1 2 3\n4 5 6\n7 8 9\n',
        encoding='ascii',
    )
    terrain = QgsRasterLayer(str(raster_path), 'terrain')
    assert terrain.isValid()
    terrain.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))

    result = run_primary_area_assessment(
        None,
        _area_layer('POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))'),
        terrain_layer=terrain,
        area_buffer_m=100.0,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 4


def test_buffer_metres_are_converted_for_foot_based_crs(qgis_app):
    from qgis.core import QgsCoordinateReferenceSystem
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        _metres_to_map_units,
    )

    distance = _metres_to_map_units(
        30.48,
        QgsCoordinateReferenceSystem('EPSG:2263'),
    )

    assert math.isclose(distance, 100.0, rel_tol=0.0, abs_tol=0.001)


@pytest.mark.parametrize('area_buffer_m', [-1.0, math.inf, math.nan])
def test_assessment_rejects_invalid_buffer_values(qgis_app, area_buffer_m):
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    with pytest.raises(ValueError, match='Area buffer'):
        run_primary_area_assessment(
            None,
            _area_layer(),
            area_buffer_m=area_buffer_m,
        )


def test_empty_buffer_result_is_rejected(qgis_app):
    from qgis.core import QgsCoordinateReferenceSystem, QgsGeometry
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        _buffer_mask_geometry,
    )

    class EmptyBufferGeometry:
        def buffer(self, distance, segments):
            assert distance == 10.0
            assert segments == 36
            return QgsGeometry()

    with pytest.raises(ValueError, match='buffer could not be created'):
        _buffer_mask_geometry(
            EmptyBufferGeometry(),
            10.0,
            QgsCoordinateReferenceSystem('EPSG:32616'),
        )


def test_declining_missing_sources_creates_no_result_group(qgis_app):
    from qgis.core import QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        AssessmentCancelled,
        run_primary_area_assessment,
    )

    with pytest.raises(AssessmentCancelled):
        run_primary_area_assessment(
            None,
            _area_layer(),
            area_buffer_m=100.0,
            confirm_missing=lambda warnings: False,
        )

    assert all(
        node.name() != 'Obstacle assessment'
        for node in QgsProject.instance().layerTreeRoot().children()
    )


@pytest.mark.parametrize('source', ['terrain', 'survey'])
def test_geographic_optional_input_creates_no_results(
        qgis_app, tmp_path, source):
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRasterLayer,
    )
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        CrsValidationError,
        run_primary_area_assessment,
    )

    kwargs = {}
    if source == 'terrain':
        raster_path = tmp_path / 'geographic-terrain.asc'
        raster_path.write_text(
            'ncols 1\n'
            'nrows 1\n'
            'xllcorner 0\n'
            'yllcorner 0\n'
            'cellsize 1\n'
            'NODATA_value -9999\n'
            '100\n',
            encoding='ascii',
        )
        layer = QgsRasterLayer(str(raster_path), 'terrain')
        assert layer.isValid()
        layer.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        kwargs['terrain_layer'] = layer
    else:
        layer = _obstacle_layer()
        layer.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        kwargs['obstacle_layer'] = layer

    with pytest.raises(CrsValidationError):
        run_primary_area_assessment(None, _area_layer(), **kwargs)

    assert all(
        node.name() != 'Obstacle assessment'
        for node in QgsProject.instance().layerTreeRoot().children()
    )


def test_dockwidget_reports_geographic_input_as_yellow_warning(qgis_app):
    from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsProject
    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_primary_area_assessment_dockwidget import (
            QPANSOPYPrimaryAreaAssessmentDockWidget,
        )

    area = _area_layer()
    survey = _obstacle_layer()
    survey.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    QgsProject.instance().addMapLayers([area, survey])
    iface = _DockIface()
    widget = QPANSOPYPrimaryAreaAssessmentDockWidget(iface)
    widget.areaLayerComboBox.setLayer(area)
    widget.obstacleLayerComboBox.setLayer(survey)
    widget.idFieldComboBox.setCurrentText('survey_id')
    widget.typeFieldComboBox.setCurrentText('kind')
    widget.overrideToleranceCheckBox.setChecked(True)

    widget.calculate()

    assert any(
        kwargs.get('level') == Qgis.Warning
        and 'survey layer' in args[1]
        and 'projected CRS' in args[1]
        for args, kwargs in iface.message_bar.messages
    )
    assert all(
        node.name() != 'Obstacle assessment'
        for node in QgsProject.instance().layerTreeRoot().children()
    )
    widget.close()


def test_accepting_empty_sources_creates_annotated_empty_layers(qgis_app):
    from qgis.core import QgsLayerNotesUtils
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    result = run_primary_area_assessment(
        None,
        _area_layer(),
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 0
    assert result.control_count == 0
    assert len(result.warnings) == 2
    notes = QgsLayerNotesUtils.layerNotes(result.assessment_layer)
    assert 'No terrain data' in notes
    assert 'No survey data' in notes


def test_control_only_assessment_loads_only_controls(qgis_app):
    from qgis.core import QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        FieldMapping,
        run_primary_area_assessment,
    )

    result = run_primary_area_assessment(
        None,
        _area_layer(),
        obstacle_layer=_obstacle_layer(),
        field_mapping=FieldMapping(
            identifier='survey_id',
            obstacle_type='kind',
            elevation='elevation',
            tolerance='accuracy',
        ),
        moc_m=75.0,
        oca_rounding_ft=10,
        load_all_points=False,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessment_layer is None
    assert result.assessed_count == 2
    assert result.control_count == 2
    assert all(
        feature['oca_pub_increment'] == 10
        for feature in result.control_layer.getFeatures()
    )
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert [node.layer().name() for node in group.children()] == [
        'Control obstacle'
    ]


def test_control_only_empty_sources_keep_warning_and_empty_control_layer(
        qgis_app):
    from qgis.core import QgsLayerNotesUtils
    from Q_Pansopy.modules.utilities.primary_area_assessment import (
        run_primary_area_assessment,
    )

    result = run_primary_area_assessment(
        None,
        _area_layer(),
        load_all_points=False,
        confirm_missing=lambda warnings: True,
    )

    assert result.assessment_layer is None
    assert result.assessed_count == 0
    assert result.control_count == 0
    assert result.control_layer.featureCount() == 0
    notes = QgsLayerNotesUtils.layerNotes(result.control_layer)
    assert 'No terrain data' in notes
    assert 'No survey data' in notes
