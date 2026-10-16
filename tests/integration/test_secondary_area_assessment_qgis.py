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


def _polygon_layer(wkt=None):
    from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer('Polygon?crs=EPSG:32616', 'secondary', 'memory')
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromWkt(wkt or (
        'POLYGON ((0 0, 4000 0, 4000 3129.733, 0 3129.733, 0 0))'
    )))
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    return layer


def _reference_layer(wkt='LINESTRING (0 0, 4000 0)'):
    from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

    layer = QgsVectorLayer('LineString?crs=EPSG:32616', 'axis', 'memory')
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    assert layer.dataProvider().addFeature(feature)
    layer.selectAll()
    return layer


def _survey_layer(point_wkt='POINT (1000 1589.152)'):
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
    feature = QgsFeature(layer.fields())
    feature.setAttributes(['A', 'building', 1642.0, 31.0])
    feature.setGeometry(QgsGeometry.fromWkt(point_wkt))
    assert layer.dataProvider().addFeature(feature)
    return layer


def test_video_example_uses_axis_to_exterior_variable_moc(qgis_app):
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    result = run_secondary_area_assessment(
        None,
        _polygon_layer(),
        _reference_layer(),
        obstacle_layer=_survey_layer(),
        field_mapping=FieldMapping(
            'survey_id', 'kind', 'elevation', 'accuracy'
        ),
        moc_m=75.0,
        load_all_points=True,
    )

    feature = next(result.assessment_layer.getFeatures())
    fields = result.assessment_layer.fields()

    def value(name):
        return feature[fields.indexFromName(name)]

    expected_moc = 75.0 * 1540.581 / 3129.733
    assert math.isclose(value('y_dist'), 1589.152, abs_tol=0.002)
    assert math.isclose(value('e_dist'), 1540.581, abs_tol=0.002)
    assert math.isclose(value('ws'), 3129.733, abs_tol=0.002)
    assert math.isclose(value('moc_m'), expected_moc, abs_tol=0.001)
    assert math.isclose(value('oca_m'), 1642.0 + 31.0 + expected_moc,
                        abs_tol=0.001)
    assert result.assessed_count == 1
    assert result.control_count == 1


def test_moc_is_full_at_inner_aoi_edge_and_zero_at_outer_edge(qgis_app):
    from qgis.core import QgsGeometry, QgsPointXY
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        _moc_for_point,
    )

    spec = {
        'sign': 1, 'outer': 1000.0, 'factor': 1.0,
        'geometry': QgsGeometry.fromWkt(
            'POLYGON ((0 100, 100 100, 100 1000, 0 1000, 0 100))'
        ),
    }
    origin = QgsPointXY(0, 0)
    on_inner_edge = _moc_for_point(QgsPointXY(20, 100), spec, origin, 1, 0, 75)
    on_edge = _moc_for_point(QgsPointXY(20, 1000), spec, origin, 1, 0, 75)

    assert on_inner_edge[0] == 75.0
    assert on_edge[0] == 0.0


def test_secondary_dockwidget_loads_assessment_controls(qgis_app):
    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_secondary_area_assessment_dockwidget import (
            QPANSOPYSecondaryAreaAssessmentDockWidget,
        )

    iface = SimpleNamespace(
        mainWindow=lambda: None,
        activeLayer=lambda: None,
    )
    widget = QPANSOPYSecondaryAreaAssessmentDockWidget(iface)

    assert widget.referenceLineComboBox is not None
    assert widget.mocDoubleSpinBox.value() == 75.0
    assert widget.loadAllPointsCheckBox.isChecked() is False
    assert widget.loadExteriorLinesCheckBox.isChecked() is False
    assert not hasattr(widget, 'areaBufferDoubleSpinBox')
    widget.close()


def test_rejects_area_component_crossing_the_reference_line(qgis_app):
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    area = _polygon_layer(
        'POLYGON ((0 -100, 4000 -100, 4000 100, 0 100, 0 -100))'
    )
    with pytest.raises(ValueError, match='crosses the reference line'):
        run_secondary_area_assessment(
            None, area, _reference_layer(),
            obstacle_layer=_survey_layer(),
            field_mapping=FieldMapping(
                'survey_id', 'kind', 'elevation', 'accuracy'
            ),
        )


def test_rejects_a_bent_reference_line(qgis_app):
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    with pytest.raises(ValueError, match='reference line must be straight'):
        run_secondary_area_assessment(
            None, _polygon_layer(),
            _reference_layer('LINESTRING (0 0, 2000 10, 4000 0)'),
            obstacle_layer=_survey_layer(),
            field_mapping=FieldMapping(
                'survey_id', 'kind', 'elevation', 'accuracy'
            ),
        )


@pytest.mark.parametrize('wkt,point_wkt,y_dist,e_dist', [
    ('POLYGON ((0 100, 1000 100, 1000 300, 0 300, 0 100))',
     'POINT (500 180)', 80.0, 120.0),
    ('POLYGON ((0 100, 1000 200, 1000 500, 0 300, 0 100))',
     'POINT (500 250)', 100.0, 150.0),
    ('POLYGON ((0 100, 1000 100, 1000 300, 0 300, 0 100), '
     '(400 140, 400 160, 600 160, 600 140, 400 140))',
     'POINT (500 180)', 20.0, 120.0),
    ('POLYGON ((0 100, 1000 100, 1000 300, 0 300, 0 100), '
     '(400 200, 400 220, 600 220, 600 200, 400 200))',
     'POINT (500 180)', 80.0, 20.0),
])
def test_perpendicular_distances_stop_at_aoi_boundary(
        qgis_app, wkt, point_wkt, y_dist, e_dist):
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )
    from qgis.core import QgsGeometry

    area = _polygon_layer(wkt)
    survey = _survey_layer(point_wkt)
    result = run_secondary_area_assessment(
        None, area, _reference_layer(), obstacle_layer=survey,
        field_mapping=FieldMapping('survey_id', 'kind', 'elevation', 'accuracy'),
        load_all_points=True,
    )
    point = next(result.assessment_layer.getFeatures())
    assert point['y_dist'] == pytest.approx(y_dist)
    assert point['e_dist'] == pytest.approx(e_dist)
    assert point['ws'] == pytest.approx(y_dist + e_dist)
    expected_moc = 75.0 * e_dist / (y_dist + e_dist)
    assert point['moc_m'] == pytest.approx(expected_moc)
    assert point['oca_m'] == pytest.approx(1642 + 31 + expected_moc)
    for layer, expected in (
            (result.axis_perpendicular_layer, y_dist),
            (result.wall_perpendicular_layer, e_dist)):
        feature = next(layer.getFeatures())
        assert feature['id'] == 'A'
        assert feature['layer_type'] == 'survey'
        assert feature['area_fid'] == point['area_fid']
        assert feature['area_part'] == point['area_part']
        assert feature['distance_m'] == pytest.approx(expected)
        geometry = feature.geometry()
        assert geometry.length() == pytest.approx(expected)
        assert geometry.difference(QgsGeometry.fromWkt(wkt)).length() < 1e-6
        assert geometry.distance(point.geometry()) < 1e-6
        vertices = geometry.asPolyline()
        assert vertices[0].x() == pytest.approx(vertices[-1].x())


def test_two_asymmetric_aoi_sides_use_their_own_exterior_walls(qgis_app):
    from qgis.core import QgsFeature, QgsGeometry
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    area = _polygon_layer(
        'POLYGON ((0 100, 1000 100, 1000 1000, 0 1000, 0 100))'
    )
    other_area = QgsFeature(area.fields())
    other_area.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((0 -100, 1000 -100, 1000 -50, 0 -50, 0 -100))'
    ))
    assert area.dataProvider().addFeature(other_area)
    area.selectAll()
    survey = _survey_layer('POINT (500 180)')
    other_point = QgsFeature(survey.fields())
    other_point.setAttributes(['B', 'building', 1642.0, 31.0])
    other_point.setGeometry(QgsGeometry.fromWkt('POINT (500 -75)'))
    assert survey.dataProvider().addFeature(other_point)
    result = run_secondary_area_assessment(
        None, area, _reference_layer(), obstacle_layer=survey,
        field_mapping=FieldMapping('survey_id', 'kind', 'elevation', 'accuracy'),
        load_all_points=True,
    )

    records = {feature['id']: feature
               for feature in result.assessment_layer.getFeatures()}
    assert records['A']['y_dist'] == pytest.approx(80)
    assert records['A']['e_dist'] == pytest.approx(820)
    assert records['B']['y_dist'] == pytest.approx(25)
    assert records['B']['e_dist'] == pytest.approx(25)
    walls = {feature['id']: feature.geometry().asPolyline()
             for feature in result.wall_perpendicular_layer.getFeatures()}
    assert walls['A'][-1].y() == pytest.approx(1000)
    assert walls['B'][-1].y() == pytest.approx(-100)


@pytest.mark.parametrize('angle,reverse', [(37, False), (-52, True), (0, True)])
def test_perpendicular_measurements_survive_axis_rotation_and_reversal(
        qgis_app, angle, reverse):
    from qgis.core import QgsPointXY
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    area = _polygon_layer(
        'POLYGON ((0 100, 1000 100, 1000 300, 0 300, 0 100))'
    )
    reference = _reference_layer(
        'LINESTRING (4000 0, 0 0)' if reverse else 'LINESTRING (0 0, 4000 0)'
    )
    survey = _survey_layer('POINT (500 180)')
    for layer in (area, reference, survey):
        for feature in layer.getFeatures():
            geometry = feature.geometry()
            geometry.rotate(angle, QgsPointXY(0, 0))
            assert layer.dataProvider().changeGeometryValues({feature.id(): geometry})
    result = run_secondary_area_assessment(
        None, area, reference, obstacle_layer=survey,
        field_mapping=FieldMapping('survey_id', 'kind', 'elevation', 'accuracy'),
        load_all_points=True,
    )
    feature = next(result.assessment_layer.getFeatures())
    assert feature['y_dist'] == pytest.approx(80)
    assert feature['e_dist'] == pytest.approx(120)
    assert feature['moc_m'] == pytest.approx(45)
    axis = next(reference.getFeatures()).geometry().asPolyline()
    axis_dx = axis[-1].x() - axis[0].x()
    axis_dy = axis[-1].y() - axis[0].y()
    for layer in (result.axis_perpendicular_layer, result.wall_perpendicular_layer):
        line = next(layer.getFeatures()).geometry().asPolyline()
        dot = ((line[-1].x() - line[0].x()) * axis_dx
               + (line[-1].y() - line[0].y()) * axis_dy)
        assert abs(dot) < 1e-6


@pytest.mark.parametrize('height,moc,axis_count,wall_count', [
    (100, 75, 0, 1), (300, 0, 1, 0),
])
def test_boundary_points_keep_zero_distances_without_zero_length_features(
        qgis_app, height, moc, axis_count, wall_count):
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    result = run_secondary_area_assessment(
        None, _polygon_layer(
            'POLYGON ((0 100, 1000 100, 1000 300, 0 300, 0 100))'
        ), _reference_layer(),
        obstacle_layer=_survey_layer(f'POINT (500 {height})'),
        field_mapping=FieldMapping('survey_id', 'kind', 'elevation', 'accuracy'),
    )
    feature = next(result.control_layer.getFeatures())
    assert feature['moc_m'] == pytest.approx(moc)
    assert result.axis_perpendicular_layer.featureCount() == axis_count
    assert result.wall_perpendicular_layer.featureCount() == wall_count


def test_zero_width_stops_before_outputs_with_obstacle_and_area_context(qgis_app):
    from qgis.core import QgsProject
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    with pytest.raises(ValueError, match="Obstacle 'A', area .*width"):
        run_secondary_area_assessment(
            None, _polygon_layer(
                'POLYGON ((0 200, 1000 100, 1000 300, 0 200))'
            ), _reference_layer(),
            obstacle_layer=_survey_layer('POINT (0 200)'),
            field_mapping=FieldMapping('survey_id', 'kind', 'elevation', 'accuracy'),
        )
    assert not QgsProject.instance().mapLayers()


def test_distances_use_metres_in_a_foot_based_crs(qgis_app):
    from qgis.core import QgsCoordinateReferenceSystem
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        _linear_unit_factor, run_secondary_area_assessment,
    )

    area = _polygon_layer(
        'POLYGON ((0 100, 1000 100, 1000 300, 0 300, 0 100))'
    )
    axis = _reference_layer()
    survey = _survey_layer('POINT (500 180)')
    crs = QgsCoordinateReferenceSystem('EPSG:2227')
    for layer in (area, axis, survey):
        layer.setCrs(crs)
    result = run_secondary_area_assessment(
        None, area, axis, obstacle_layer=survey,
        field_mapping=FieldMapping('survey_id', 'kind', 'elevation', 'accuracy'),
    )
    factor = _linear_unit_factor(crs)
    assert factor == pytest.approx(0.3048006096)
    feature = next(result.control_layer.getFeatures())
    assert feature['y_dist'] == pytest.approx(80 * factor)
    assert feature['e_dist'] == pytest.approx(120 * factor)
    for layer in (result.axis_perpendicular_layer, result.wall_perpendicular_layer):
        line = next(layer.getFeatures())
        assert line.geometry().length() * factor == pytest.approx(line['distance_m'])


@pytest.mark.parametrize('load_all,load_exterior', [(False, False), (True, True)])
def test_both_layers_always_include_all_terrain_and_survey_points(
        qgis_app, tmp_path, load_all, load_exterior):
    from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsRasterLayer
    from Q_Pansopy.modules.utilities.primary_area_assessment import FieldMapping
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        run_secondary_area_assessment,
    )

    path = tmp_path / 'secondary_terrain.asc'
    path.write_text(
        'ncols 2\nnrows 2\nxllcorner 400\nyllcorner 100\n'
        'cellsize 100\nNODATA_value -9999\n1000 990\n980 970\n',
        encoding='ascii',
    )
    terrain = QgsRasterLayer(str(path), 'terrain')
    assert terrain.isValid()
    terrain.setCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    result = run_secondary_area_assessment(
        None, _polygon_layer(
            'POLYGON ((0 100, 1000 100, 1000 300, 0 300, 0 100))'
        ), _reference_layer(), terrain_layer=terrain,
        obstacle_layer=_survey_layer('POINT (500 180)'),
        field_mapping=FieldMapping('survey_id', 'kind', 'elevation', 'accuracy'),
        override_tolerance_m=10, load_all_points=load_all,
        load_exterior_lines=load_exterior,
    )
    assert result.assessed_count == 5
    assert (result.assessment_layer is not None) == load_all
    assert (result.exterior_layer is not None) == load_exterior
    assert next(result.control_layer.getFeatures())['oca_m'] == pytest.approx(1697)
    for layer in (result.axis_perpendicular_layer, result.wall_perpendicular_layer):
        assert layer.featureCount() == result.assessed_count
        assert {feature['layer_type'] for feature in layer.getFeatures()} == {'DTM', 'survey'}
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        assert node.itemVisibilityChecked()
