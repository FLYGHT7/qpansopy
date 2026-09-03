import pytest


pytestmark = [pytest.mark.integration, pytest.mark.qgis_runtime]


@pytest.fixture(scope='module')
def qgis_app():
    """Start a headless QGIS application when bindings are available."""
    try:
        from qgis.core import QgsApplication
    except ImportError:
        pytest.skip('QGIS Python bindings are not installed')

    existing_app = QgsApplication.instance()
    app = existing_app or QgsApplication([], False)
    if existing_app is None:
        app.initQgis()

    yield app

    from qgis.core import QgsProject
    QgsProject.instance().clear()
    if existing_app is None:
        app.exitQgis()


class _MessageBar:
    def pushMessage(self, *args, **kwargs):
        pass


class _Iface:
    def messageBar(self):
        return _MessageBar()


def test_selected_intersections_create_every_matching_feature(qgis_app):
    from qgis.core import (
        QgsFeature,
        QgsGeometry,
        QgsProject,
        QgsVectorLayer,
        QgsWkbTypes,
    )

    from Q_Pansopy.modules.utilities.selection_of_objects import extract_objects

    project = QgsProject.instance()
    project.clear()

    points = QgsVectorLayer(
        'PointZ?crs=EPSG:32616&field=name:string',
        'obstacles',
        'memory',
    )
    point_features = []
    for name, wkt in (
        ('inside-1', 'POINT Z (100 100 10)'),
        ('inside-2', 'POINT Z (200 200 20)'),
        ('inside-3', 'POINT Z (300 300 30)'),
        ('outside', 'POINT Z (900 900 40)'),
    ):
        feature = QgsFeature(points.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        feature.setAttribute('name', name)
        point_features.append(feature)
    added, _ = points.dataProvider().addFeatures(point_features)
    assert added
    points.selectAll()

    surfaces = QgsVectorLayer(
        'Polygon?crs=EPSG:32616', 'surfaces', 'memory'
    )
    surface = QgsFeature()
    surface.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((0 0, 500 0, 500 500, 0 500, 0 0))'
    ))
    added, _ = surfaces.dataProvider().addFeatures([surface])
    assert added

    result = extract_objects(
        _Iface(), points, surfaces, use_selection_only=True
    )
    output = project.mapLayersByName('Extracted Objects')[0]

    assert result['count'] == 3
    assert output.featureCount() == 3
    assert output.wkbType() == points.wkbType()
    assert {feature['name'] for feature in output.getFeatures()} == {
        'inside-1', 'inside-2', 'inside-3'
    }
    assert all(
        QgsWkbTypes.hasZ(feature.geometry().wkbType())
        for feature in output.getFeatures()
    )


def test_result_layer_converts_unsupported_fields_without_losing_rows(qgis_app):
    from qgis.PyQt.QtCore import QMetaType, QUrl, QVariant
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsFields,
        QgsGeometry,
    )

    from Q_Pansopy.modules.utilities.selection_of_objects import (
        _create_result_layer,
    )

    try:
        url_type = QMetaType.Type.QUrl
    except AttributeError:
        url_type = QVariant.Url

    fields = QgsFields()
    fields.append(QgsField('name', QVariant.String))
    fields.append(QgsField('url', url_type))
    fields.append(QgsField('height', QVariant.Double))

    features = []
    for index in range(2):
        feature = QgsFeature(fields)
        feature.setGeometry(QgsGeometry.fromWkt(
            'POINT Z ({0} {0} {0})'.format(index + 1)
        ))
        feature.setAttributes([
            'point-{0}'.format(index + 1),
            QUrl('https://example.com/{0}'.format(index + 1)),
            float(index + 1),
        ])
        features.append(feature)

    class _SourceLayerSchema:
        def fields(self):
            return fields

        def wkbType(self):
            return features[0].geometry().wkbType()

        def crs(self):
            return QgsCoordinateReferenceSystem('EPSG:32616')

    output = _create_result_layer(_SourceLayerSchema(), features)

    assert output.featureCount() == 2
    assert output.wkbType() == features[0].geometry().wkbType()
    assert [field.name() for field in output.fields()] == [
        'name', 'url', 'height'
    ]
    assert [
        (feature['name'], feature['url'], feature['height'])
        for feature in output.getFeatures()
    ] == [
        ('point-1', 'https://example.com/1', 1.0),
        ('point-2', 'https://example.com/2', 2.0),
    ]


def test_result_layer_rolls_back_and_reports_partial_insert(qgis_app):
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsFields,
        QgsGeometry,
    )

    from Q_Pansopy.modules.utilities.selection_of_objects import (
        _create_result_layer,
    )

    fields = QgsFields()
    fields.append(QgsField('height', QVariant.Double))

    valid_feature = QgsFeature(fields)
    valid_feature.setGeometry(QgsGeometry.fromWkt('POINT (1 1)'))
    valid_feature.setAttributes([1.0])
    invalid_feature = QgsFeature(fields)
    invalid_feature.setGeometry(QgsGeometry.fromWkt('POINT (2 2)'))
    invalid_feature.setAttributes(['not-a-number'])
    features = [valid_feature, invalid_feature]

    class _SourceLayerSchema:
        def fields(self):
            return fields

        def wkbType(self):
            return features[0].geometry().wkbType()

        def crs(self):
            return QgsCoordinateReferenceSystem('EPSG:32616')

    with pytest.raises(
            RuntimeError,
            match=r'expected 2, stored 0.*Could not convert value'):
        _create_result_layer(_SourceLayerSchema(), features)
