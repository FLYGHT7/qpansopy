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


def _make_dockwidget_layers():
    from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer

    points = QgsVectorLayer(
        'Point?crs=EPSG:32616&field=name:string', 'obstacles', 'memory'
    )
    point = QgsFeature(points.fields())
    point.setGeometry(QgsGeometry.fromWkt('POINT (100 100)'))
    point.setAttribute('name', 'inside')
    added, stored_points = points.dataProvider().addFeatures([point])
    assert added

    surfaces = QgsVectorLayer(
        'Polygon?crs=EPSG:32616', 'surfaces', 'memory'
    )
    surface = QgsFeature()
    surface.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((0 0, 500 0, 500 500, 0 500, 0 0))'
    ))
    added, stored_surfaces = surfaces.dataProvider().addFeatures([surface])
    assert added

    QgsProject.instance().addMapLayers([points, surfaces])
    return points, stored_points[0], surfaces, stored_surfaces[0]


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

    surfaces = QgsVectorLayer(
        'Polygon?crs=EPSG:32616', 'surfaces', 'memory'
    )
    surface = QgsFeature()
    surface.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((0 0, 500 0, 500 500, 0 500, 0 0))'
    ))
    added, _ = surfaces.dataProvider().addFeatures([surface])
    assert added
    surfaces.selectAll()
    assert points.selectedFeatureCount() == 0
    assert surfaces.selectedFeatureCount() == 1

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


def test_selection_only_uses_selected_surfaces_not_selected_points(qgis_app):
    """Reproduce issue #229's selected-surface workflow with real QGIS."""
    from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer

    from Q_Pansopy.modules.utilities.selection_of_objects import extract_objects

    project = QgsProject.instance()
    project.clear()

    points = QgsVectorLayer(
        'Point?crs=EPSG:32616&field=name:string',
        'obstacles',
        'memory',
    )
    point_features = []
    for name, wkt in (
        ('inside-selected-surface-1', 'POINT (100 100)'),
        ('inside-selected-surface-2', 'POINT (200 200)'),
        ('inside-unselected-surface', 'POINT (1100 100)'),
        ('outside-all-surfaces', 'POINT (2000 2000)'),
    ):
        feature = QgsFeature(points.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        feature.setAttribute('name', name)
        point_features.append(feature)
    added, stored_points = points.dataProvider().addFeatures(point_features)
    assert added

    surfaces = QgsVectorLayer(
        'Polygon?crs=EPSG:32616', 'surfaces', 'memory'
    )
    surface_features = []
    for wkt in (
        'POLYGON ((0 0, 500 0, 500 500, 0 500, 0 0))',
        'POLYGON ((1000 0, 1500 0, 1500 500, 1000 500, 1000 0))',
    ):
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        surface_features.append(feature)
    added, stored_surfaces = surfaces.dataProvider().addFeatures(
        surface_features
    )
    assert added

    # Match the reported workflow: the first surface is selected. Selecting a
    # point in the other surface makes this a regression test for which input
    # layer "Use selection only" actually filters.
    surfaces.select(stored_surfaces[0].id())
    points.select(stored_points[2].id())
    assert surfaces.selectedFeatureCount() == 1
    assert points.selectedFeatureCount() == 1

    result = extract_objects(
        _Iface(), points, surfaces, use_selection_only=True
    )
    output = project.mapLayersByName('Extracted Objects')[0]

    assert result['count'] == 2
    assert output.featureCount() == 2
    assert {feature['name'] for feature in output.getFeatures()} == {
        'inside-selected-surface-1',
        'inside-selected-surface-2',
    }


def test_selected_surface_prefilter_is_safe_across_different_crs(qgis_app):
    from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer

    from Q_Pansopy.modules.utilities.selection_of_objects import extract_objects

    project = QgsProject.instance()
    project.clear()

    points = QgsVectorLayer(
        'Point?crs=EPSG:4326&field=name:string',
        'obstacles',
        'memory',
    )
    point_features = []
    for name, wkt in (
        ('inside', 'POINT (0 0)'),
        ('outside', 'POINT (10 10)'),
    ):
        feature = QgsFeature(points.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        feature.setAttribute('name', name)
        point_features.append(feature)
    added, _ = points.dataProvider().addFeatures(point_features)
    assert added

    surfaces = QgsVectorLayer(
        'Polygon?crs=EPSG:3857', 'surfaces', 'memory'
    )
    surface = QgsFeature()
    surface.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((-1000 -1000, 1000 -1000, 1000 1000, '
        '-1000 1000, -1000 -1000))'
    ))
    added, _ = surfaces.dataProvider().addFeatures([surface])
    assert added
    surfaces.selectAll()

    result = extract_objects(
        _Iface(), points, surfaces, use_selection_only=True
    )
    output = project.mapLayersByName('Extracted Objects')[0]

    assert result['count'] == 1
    assert [feature['name'] for feature in output.getFeatures()] == ['inside']


def test_dockwidget_warns_when_selected_surface_is_missing(
        qgis_app, monkeypatch):
    from qgis.core import Qgis, QgsProject

    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_object_selection_dockwidget import (
            QPANSOPYObjectSelectionDockWidget,
        )
    from Q_Pansopy.modules.utilities import selection_of_objects

    project = QgsProject.instance()
    project.clear()
    points, point, surfaces, _ = _make_dockwidget_layers()
    points.select(point.id())

    called = []

    def unexpected_extraction(*args, **kwargs):
        called.append(True)
        return {'count': 0}

    monkeypatch.setattr(
        selection_of_objects, 'extract_objects', unexpected_extraction
    )
    iface = _DockIface()
    widget = QPANSOPYObjectSelectionDockWidget(iface)
    widget.pointLayerComboBox.setLayer(points)
    widget.surfaceLayerComboBox.setLayer(surfaces)
    widget.useSelectionOnlyCheckBox.setChecked(True)

    widget.extract_objects()

    assert not called
    assert not project.mapLayersByName('Extracted Objects')
    assert "no features are selected in the surface layer" in (
        widget.logTextEdit.toPlainText()
    )
    assert any(
        kwargs.get('level') == Qgis.MessageLevel.Warning
        and 'surface layer' in args[1]
        for args, kwargs in iface.message_bar.messages
    )
    widget.close()


def test_dockwidget_exposes_and_restores_busy_state(
        qgis_app, monkeypatch):
    from qgis.PyQt import QtWidgets
    from qgis.core import Qgis, QgsProject

    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_object_selection_dockwidget import (
            QPANSOPYObjectSelectionDockWidget,
        )
    from Q_Pansopy.modules.utilities import selection_of_objects

    QgsProject.instance().clear()
    points, point, surfaces, surface = _make_dockwidget_layers()
    points.select(point.id())
    surfaces.select(surface.id())
    iface = _DockIface()
    widget = QPANSOPYObjectSelectionDockWidget(iface)
    widget.pointLayerComboBox.setLayer(points)
    widget.surfaceLayerComboBox.setLayer(surfaces)
    widget.useSelectionOnlyCheckBox.setChecked(True)

    observed = {}
    processed_events = []

    def failing_extraction(*args, **kwargs):
        observed['button_enabled'] = widget.calculateButton.isEnabled()
        observed['extracting'] = getattr(widget, '_extracting', False)
        observed['had_info_message'] = any(
            message_kwargs.get('level') == Qgis.MessageLevel.Info
            for _, message_kwargs in iface.message_bar.messages
        )
        raise RuntimeError('controlled extraction failure')

    monkeypatch.setattr(
        selection_of_objects, 'extract_objects', failing_extraction
    )
    monkeypatch.setattr(
        QtWidgets.QApplication,
        'processEvents',
        lambda: processed_events.append(True),
    )

    widget.extract_objects()

    assert observed == {
        'button_enabled': False,
        'extracting': True,
        'had_info_message': True,
    }
    assert processed_events == [True]
    assert widget.calculateButton.isEnabled()
    assert not widget._extracting
    assert 'controlled extraction failure' in widget.logTextEdit.toPlainText()
    assert iface.message_bar.messages[-1][1].get('level') == Qgis.MessageLevel.Critical
    widget.close()


def test_result_layer_converts_unsupported_fields_without_losing_rows(qgis_app):
    from qgis.PyQt.QtCore import QMetaType, QUrl
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
    fields.append(QgsField('name', QMetaType.Type.QString))
    fields.append(QgsField('url', QMetaType.Type.QUrl))
    fields.append(QgsField('height', QMetaType.Type.Double))

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
    from qgis.PyQt.QtCore import QMetaType
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
    fields.append(QgsField('height', QMetaType.Type.Double))

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


def test_extraction_styles_output_and_exports_kml(qgis_app, tmp_path):
    from pathlib import Path

    from qgis.PyQt.QtGui import QColor
    from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer

    from Q_Pansopy.modules.utilities.selection_of_objects import extract_objects

    project = QgsProject.instance()
    project.clear()
    points = QgsVectorLayer(
        'PointZ?crs=EPSG:32616&field=name:string', 'obstacles', 'memory'
    )
    point_features = []
    for name, wkt in (('inside', 'POINT Z (100 100 10)'),
                      ('outside', 'POINT Z (900 900 40)')):
        feature = QgsFeature(points.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        feature.setAttribute('name', name)
        point_features.append(feature)
    assert points.dataProvider().addFeatures(point_features)[0]
    surfaces = QgsVectorLayer('Polygon?crs=EPSG:32616', 'surfaces', 'memory')
    surface = QgsFeature()
    surface.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((0 0, 500 0, 500 500, 0 500, 0 0))'
    ))
    assert surfaces.dataProvider().addFeatures([surface])[0]
    project.addMapLayers([points, surfaces])
    iface = _DockIface()

    result = extract_objects(
        iface, points, surfaces, export_kml=True, output_dir=str(tmp_path)
    )

    assert result['count'] == 1
    kml_path = Path(result['kml_path'])
    assert kml_path.parent == tmp_path
    assert kml_path.name.startswith('extracted_objects_')
    assert kml_path.suffix == '.kml'
    text = kml_path.read_text(encoding='utf-8')
    assert text.count('<Placemark') == 1
    assert '<altitudeMode>absolute</altitudeMode>' in text
    assert iface.message_bar.messages == []
    output = project.mapLayersByName('Extracted Objects')[0]
    symbol = output.renderer().symbol()
    assert symbol.symbolLayerCount() == 1
    marker = symbol.symbolLayer(0)
    assert marker.layerType() == 'SimpleMarker'
    assert marker.color() == QColor('red')
    assert marker.size() == 3
    assert marker.strokeColor().alpha() == 0
    assert marker.strokeWidth() == 0


def test_unreprojectable_points_are_skipped_with_warning(qgis_app):
    from qgis.core import (
        Qgis,
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsGeometry,
        QgsProject,
        QgsVectorLayer,
    )

    from Q_Pansopy.modules.utilities.selection_of_objects import extract_objects

    project = QgsProject.instance()
    project.clear()
    points = QgsVectorLayer(
        'Point?crs=EPSG:4326&field=name:string', 'obstacles', 'memory'
    )
    point_features = []
    # (180 0) lies on the far side of the orthographic projection and cannot
    # be transformed into the surface CRS.
    for name, wkt in (('inside', 'POINT (0 0)'), ('far-side', 'POINT (180 0)')):
        feature = QgsFeature(points.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        feature.setAttribute('name', name)
        point_features.append(feature)
    assert points.dataProvider().addFeatures(point_features)[0]
    surfaces = QgsVectorLayer('Polygon', 'surfaces', 'memory')
    surfaces.setCrs(QgsCoordinateReferenceSystem.fromProj(
        '+proj=ortho +lat_0=0 +lon_0=0 +ellps=WGS84 +units=m +no_defs'
    ))
    surface = QgsFeature()
    surface.setGeometry(QgsGeometry.fromWkt(
        'POLYGON ((-7000000 -7000000, 7000000 -7000000, 7000000 7000000, '
        '-7000000 7000000, -7000000 -7000000))'
    ))
    assert surfaces.dataProvider().addFeatures([surface])[0]
    project.addMapLayers([points, surfaces])
    iface = _DockIface()

    result = extract_objects(iface, points, surfaces)

    assert result['count'] == 1
    output = project.mapLayersByName('Extracted Objects')[0]
    assert [feature['name'] for feature in output.getFeatures()] == ['inside']
    assert [
        (args, kwargs.get('level')) for args, kwargs in iface.message_bar.messages
    ] == [(
        ('QPANSOPY:', '1 obstacle point(s) could not be reprojected to the '
                      'surface CRS and were skipped'),
        Qgis.MessageLevel.Warning,
    )]


def test_dockwidget_filters_wait_cursor_and_success_message(
        qgis_app, monkeypatch):
    from qgis.PyQt import QtWidgets
    from qgis.PyQt.QtCore import Qt
    from qgis.core import Qgis, QgsMapLayerProxyModel, QgsProject

    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_object_selection_dockwidget import (
            QPANSOPYObjectSelectionDockWidget,
        )
    from Q_Pansopy.modules.utilities import selection_of_objects

    QgsProject.instance().clear()
    points, _, surfaces, _ = _make_dockwidget_layers()
    iface = _DockIface()
    widget = QPANSOPYObjectSelectionDockWidget(iface)
    assert widget.pointLayerComboBox.filters() == \
        QgsMapLayerProxyModel.Filter.PointLayer
    assert widget.surfaceLayerComboBox.filters() == \
        QgsMapLayerProxyModel.Filter.PolygonLayer
    widget.pointLayerComboBox.setLayer(points)
    widget.surfaceLayerComboBox.setLayer(surfaces)
    assert not widget.useSelectionOnlyCheckBox.isChecked()

    real_extraction = selection_of_objects.extract_objects
    observed = []

    def recording_extraction(*args, **kwargs):
        observed.append(QtWidgets.QApplication.overrideCursor().shape())
        return real_extraction(*args, **kwargs)

    monkeypatch.setattr(
        selection_of_objects, 'extract_objects', recording_extraction
    )
    QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
    try:
        widget.extract_objects()
        assert observed == [Qt.CursorShape.WaitCursor]
        assert QtWidgets.QApplication.overrideCursor().shape() == \
            Qt.CursorShape.CrossCursor
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()
    assert QtWidgets.QApplication.overrideCursor() is None
    assert widget.calculateButton.isEnabled()
    assert 'Extracted 1 objects' in widget.logTextEdit.toPlainText()
    assert [
        (args[1], kwargs.get('level'))
        for args, kwargs in iface.message_bar.messages
    ] == [
        ('Extracting objects...', Qgis.MessageLevel.Info),
        ('Extracted 1 objects', Qgis.MessageLevel.Success),
    ]
    output = QgsProject.instance().mapLayersByName('Extracted Objects')[0]
    assert output.featureCount() == 1
    widget.close()


def test_dockwidget_requires_both_layers(qgis_app):
    from qgis.core import QgsProject

    from Q_Pansopy.dockwidgets.utilities \
        .qpansopy_object_selection_dockwidget import (
            QPANSOPYObjectSelectionDockWidget,
        )

    QgsProject.instance().clear()
    iface = _DockIface()
    widget = QPANSOPYObjectSelectionDockWidget(iface)
    assert widget.pointLayerComboBox.currentLayer() is None

    widget.extract_objects()

    assert 'Error: Please select both input layers' in \
        widget.logTextEdit.toPlainText()
    assert iface.message_bar.messages == []
    assert widget.calculateButton.isEnabled()
    assert not QgsProject.instance().mapLayersByName('Extracted Objects')
    widget.close()
