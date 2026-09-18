from types import SimpleNamespace

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.qgis_runtime]


class _RecordingMessageBar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


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


def _area_layer():
    from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer('Polygon?crs=EPSG:32616', 'area', 'memory')
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((0 0, 500 0, 500 500, 0 500, 0 0))'
    ))
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    return layer


def _obstacle_layer():
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer('Point?crs=EPSG:32616', 'survey', 'memory')
    layer.dataProvider().addAttributes([
        QgsField('survey_id', QVariant.String),
        QgsField('kind', QVariant.String),
        QgsField('elevation', QVariant.Double),
        QgsField('accuracy', QVariant.Double),
    ])
    layer.updateFields()
    for attributes, wkt in [
        (['A', 'building', 100.0, 5.0], 'POINT (100 100)'),
        (['B', 'tree', 101.0, 4.0], 'POINT (200 200)'),
        (['OUT', 'tree', 999.0, 1.0], 'POINT (600 600)'),
    ]:
        feature = QgsFeature(layer.fields())
        feature.setAttributes(attributes)
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        assert layer.dataProvider().addFeature(feature)
    return layer


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
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 2
    assert result.control_count == 2
    assert result.warnings == (
        'No terrain data was evaluated inside the mask',
    )
    assert QgsLayerNotesUtils.layerHasNotes(result.assessment_layer)
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert group.name() == 'Obstacle assessment'
    assert [node.layer().name() for node in group.children()] == [
        'Control obstacle', 'Primary assessment'
    ]
    for layer in (result.assessment_layer, result.control_layer):
        assert 'oca_pub_ft' in layer.fields().names()
        assert all(
            isinstance(feature['oca_pub_ft'], int)
            for feature in layer.getFeatures()
        )
    assert {
        feature['oca_pub_ft']
        for feature in result.control_layer.getFeatures()
    } == {600}
    assert group.children()[0].itemVisibilityChecked()
    assert not group.children()[1].itemVisibilityChecked()


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
    assert control['elev'] == 9.0
    assert control['oca_m'] == 134.0
    assert control['oca_pub_ft'] == 440


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
    iface = _DockIface()
    widget = QPANSOPYPrimaryAreaAssessmentDockWidget(iface)
    widget.areaLayerComboBox.setLayer(area)
    widget.obstacleLayerComboBox.setLayer(survey)
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
