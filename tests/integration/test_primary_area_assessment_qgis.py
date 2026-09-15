import math

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.qgis_runtime]


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
    group = QgsProject.instance().layerTreeRoot().children()[0]
    assert group.name() == 'Obstacle assessment'
    assert [node.layer().name() for node in group.children()] == [
        'Control obstacle', 'Primary assessment'
    ]
    assert group.children()[0].itemVisibilityChecked()
    assert not group.children()[1].itemVisibilityChecked()


def test_zero_buffer_preserves_original_survey_mask(qgis_app):
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


def test_buffer_includes_survey_point_outside_original_area(qgis_app):
    from qgis.core import QgsLayerNotesUtils
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
        confirm_missing=lambda warnings: True,
    )

    assert result.assessed_count == 9
    assert result.control_count == 1
    control = next(result.control_layer.getFeatures())
    assert control['elev'] == 9.0
    assert control['oca_m'] == 134.0


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
            confirm_missing=lambda warnings: False,
        )

    assert all(
        node.name() != 'Obstacle assessment'
        for node in QgsProject.instance().layerTreeRoot().children()
    )


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
    assert 'No obstacle data' in notes
