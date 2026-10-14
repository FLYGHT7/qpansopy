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


def _survey_layer():
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
    feature.setGeometry(QgsGeometry.fromWkt('POINT (1000 1589.152)'))
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


def test_moc_is_full_at_axis_and_zero_at_outer_edge(qgis_app):
    from qgis.core import QgsPointXY
    from Q_Pansopy.modules.utilities.secondary_area_assessment import (
        _moc_for_point,
    )

    spec = {'sign': 1, 'outer': 1000.0, 'factor': 1.0}
    origin = QgsPointXY(0, 0)
    on_axis = _moc_for_point(QgsPointXY(20, 0), spec, origin, 1, 0, 75)
    on_edge = _moc_for_point(QgsPointXY(20, 1000), spec, origin, 1, 0, 75)

    assert on_axis[0] == 75.0
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
