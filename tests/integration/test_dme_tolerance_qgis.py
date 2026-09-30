"""Runtime geometry and UI checks for non-collocated DME (issue #305)."""

import math

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsDistanceArea, QgsFeature, QgsGeometry, QgsPointXY, QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas  # noqa: E402
from qgis.PyQt.QtWidgets import QMainWindow  # noqa: E402

from Q_Pansopy.modules.conv.dme_tolerance import (  # noqa: E402
    build_tolerance_geometry, run_dme_tolerance,
)
from Q_Pansopy.dockwidgets.conv.qpansopy_dme_tolerance_dockwidget import (  # noqa: E402
    QPANSOPYDMEToleranceDockWidget,
)


class _Bar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _Iface:
    def __init__(self, crs='EPSG:32616'):
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas(self.window)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
        self.bar = _Bar()

    def mainWindow(self):
        return self.window

    def mapCanvas(self):
        return self.canvas

    def messageBar(self):
        return self.bar

    def activeLayer(self):
        return None


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


@pytest.fixture
def da():
    measure = QgsDistanceArea()
    measure.setSourceCrs(QgsCoordinateReferenceSystem('EPSG:32616'),
                         QgsProject.instance().transformContext())
    measure.setEllipsoid('NONE')
    return measure


def _point_layer(name, coordinates, crs='EPSG:32616', select=True):
    layer = QgsVectorLayer('Point?crs=' + crs, name, 'memory')
    for point in coordinates:
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*point)))
        layer.dataProvider().addFeatures([feature])
    QgsProject.instance().addMapLayer(layer)
    if select:
        layer.selectAll()
    return layer


@pytest.fixture
def points():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    project.setEllipsoid('NONE')
    dme = _point_layer('DME', [(500000, 1600000)])
    tracking = _point_layer('Tracking', [(500000, 1598500)])
    fix = _point_layer('Fix', [(510000, 1600000)])
    yield dme, tracking, fix
    project.removeAllMapLayers()


def _outputs():
    return [layer for layer in QgsProject.instance().mapLayers().values()
            if layer.name().endswith('_tolerance')]


def _geometry(dme, tracking, fix, da, rotate=5.2):
    return build_tolerance_geometry(QgsPointXY(*dme), QgsPointXY(*fix),
                                    rotate, da, tracking_geom=QgsPointXY(*tracking))


def test_collocated_equivalence(da):
    dme, fix = QgsPointXY(500000, 1600000), QgsPointXY(510000, 1600000)
    old, distance = build_tolerance_geometry(dme, fix, 5.2, da)
    new, new_distance = build_tolerance_geometry(dme, fix, 5.2, da, dme)
    assert old.isGeosValid() and new.isGeosValid()
    assert old.symDifference(new).area() < 1e-5
    assert distance == new_distance == round(10000 / 1852, 3)


def test_separate_sector_origin_and_dme_radius(da):
    dme, tracking, fix = (0, 0), (0, -2000), (10000, 0)
    area, distance = _geometry(dme, tracking, fix, da)
    assert area.isGeosValid() and area.contains(QgsPointXY(*fix))
    assert distance == round(10000 / 1852, 3)
    # Independent reference points on the nominal DME circle, near either
    # tracking boundary. A sector still centred on the DME gets these wrong.
    assert area.contains(QgsPointXY(10000 * math.cos(.094), 10000 * math.sin(.094)))
    assert not area.contains(QgsPointXY(10000 * math.cos(-.094), 10000 * math.sin(-.094)))
    tolerance = 0.25 * 1852 + .0125 * 10000
    for vertex in area.vertices():
        radius = math.hypot(vertex.x(), vertex.y())
        assert 10000 - tolerance - 2 <= radius <= 10000 + tolerance + 2


@pytest.mark.parametrize('angle', [0, 23, 23 + 1e-5, 45, 180])
def test_divergence_limit(da, angle):
    fix = (0, 0)
    dme = (-10000, 0)
    tracking = (-20000 * math.cos(math.radians(angle)),
                -20000 * math.sin(math.radians(angle)))
    if angle > 23:
        with pytest.raises(ValueError, match='divergence.*23'):
            _geometry(dme, tracking, fix, da)
    else:
        area, _ = _geometry(dme, tracking, fix, da)
        assert area.contains(QgsPointXY(*fix))


def test_divergence_wraparound(da):
    fix = QgsPointXY(0, 0)
    dme = fix.project(10000, 179)
    tracking = fix.project(15000, 181)
    area, _ = build_tolerance_geometry(dme, fix, 5.2, da, tracking)
    assert area.contains(fix)


def test_only_nominal_fix_component_is_returned(da):
    area, _ = _geometry((0, 0), (30000, 0), (-10000, 0), da)
    assert area.contains(QgsPointXY(-10000, 0))
    assert not area.contains(QgsPointXY(10000, 0))
    assert not area.isMultipart()


def test_sector_reaches_outer_ring_when_tracking_is_near_fix(da):
    area, _ = _geometry((0, 0), (9990, 0), (10000, 0), da)
    # The former ×5 reach ends at x=10040, inside the outer DME boundary.
    assert area.contains(QgsPointXY(10500, 0))


@pytest.mark.parametrize('crs', ['EPSG:4326', 'EPSG:2263'])
def test_non_collocated_requires_projected_metres(da, crs):
    da.setSourceCrs(QgsCoordinateReferenceSystem(crs),
                    QgsProject.instance().transformContext())
    with pytest.raises(ValueError, match='projected CRS in metres'):
        _geometry((0, 0), (-1000, 0), (10000, 0), da)


@pytest.mark.parametrize('dme,tracking,fix', [
    ((0, 0), (100, 0), (0, 0)),
    ((0, 0), (100, 0), (100, 0)),
    ((float('nan'), 0), (-100, 0), (1000, 0)),
    ((0, 0), (float('inf'), 0), (1000, 0)),
])
def test_invalid_points(da, dme, tracking, fix):
    with pytest.raises(ValueError):
        _geometry(dme, tracking, fix, da)


@pytest.mark.parametrize('rotate', [0, 90, float('nan')])
def test_invalid_sector_angles(da, rotate):
    with pytest.raises(ValueError, match='Sector'):
        _geometry((0, 0), (-1000, 0), (10000, 0), da, rotate)


def test_runner_attributes_and_single_feature_fallback(points):
    dme, tracking, fix = points
    for layer in points:
        layer.removeSelection()
    iface = _Iface()
    assert run_dme_tolerance(iface, dme, fix, {
        'nav_type': 'LOC/DME', 'rotate': 2.4, 'non_collocated_dme': True,
    }, tracking_layer=tracking)
    assert len(_outputs()) == 1
    output = _outputs()[0]
    feature = next(output.getFeatures())
    assert [field.name() for field in output.fields()] == [
        'Symbol', 'Distance_NM', 'Sector_Angle']
    assert feature['Symbol'] == 'LOC/DME Tolerance'
    assert feature['Distance_NM'] == round(10000 / 1852, 3)
    assert feature['Sector_Angle'] == 2.4
    assert output.crs() == iface.canvas.mapSettings().destinationCrs()
    assert feature.geometry().isGeosValid()


def test_runner_transforms_tracking_from_another_crs(points):
    dme, tracking, fix = points
    project = QgsProject.instance()
    transform = QgsCoordinateTransform(tracking.crs(),
                                       QgsCoordinateReferenceSystem('EPSG:4326'), project)
    point = transform.transform(next(tracking.getFeatures()).geometry().asPoint())
    project.removeMapLayer(tracking)
    tracking = _point_layer('WGS tracking', [(point.x(), point.y())], 'EPSG:4326')
    assert run_dme_tolerance(_Iface(), dme, fix, {'non_collocated_dme': True}, tracking)
    assert len(_outputs()) == 1


def test_runner_missing_tracking_creates_no_output(points):
    with pytest.raises(ValueError, match='Tracking Navaid'):
        run_dme_tolerance(_Iface(), points[0], points[2], {'non_collocated_dme': True})
    assert _outputs() == []


def test_runner_rejects_multiple_tracking_features(points):
    tracking = _point_layer('Multiple tracking', [(500000, 1600000), (499000, 1600000)])
    assert not run_dme_tolerance(_Iface(), points[0], points[2],
                                 {'non_collocated_dme': True}, tracking)
    assert _outputs() == []


@pytest.mark.parametrize('wkt', [
    None, 'Point EMPTY', 'MultiPoint ((500000 1600000), (500100 1600000))',
    'LineString (500000 1600000, 501000 1600000)',
])
def test_runner_rejects_invalid_feature_geometry(points, wkt):
    layer = points[1]
    feature_id = next(layer.getFeatures()).id()
    geometry = QgsGeometry() if wkt is None else QgsGeometry.fromWkt(wkt)
    assert layer.dataProvider().changeGeometryValues({feature_id: geometry})
    with pytest.raises(ValueError, match='single point'):
        run_dme_tolerance(_Iface(), points[0], points[2],
                          {'non_collocated_dme': True}, layer)
    assert _outputs() == []


def test_runner_divergence_error_creates_no_output(points):
    tracking = _point_layer('Divergent tracking', [(510000, 1590000)])
    with pytest.raises(ValueError, match='divergence.*23'):
        run_dme_tolerance(_Iface(), points[0], points[2],
                          {'non_collocated_dme': True}, tracking)
    assert _outputs() == []


def test_legacy_runner_call_still_uses_collocated_mode(points):
    assert run_dme_tolerance(_Iface(), points[0], points[2], {'nav_type': 'LOC/DME'})
    assert len(_outputs()) == 1


@pytest.fixture
def dock(points):
    iface = _Iface()
    iface.window.show()
    widget = QPANSOPYDMEToleranceDockWidget(iface)
    widget.pointLayerComboBox.setLayer(points[0])
    widget.fixLayerComboBox.setLayer(points[2])
    widget.show()
    QgsApplication.processEvents()
    yield widget
    widget.close()
    iface.window.close()


def test_type_defaults_and_tracking_selection_retained(dock, points):
    assert dock.pointLayerLabel.text() == 'DME Point Layer'
    assert not dock.nonCollocatedDmeCheckBox.isChecked()
    assert dock.trackingLayerLabel.isHidden()
    assert dock.trackingLayerComboBox.currentLayer() is None
    dock.trackingLayerComboBox.setLayer(points[1])
    for index, rotate, enabled in [(1, 6.9, False), (2, 2.4, True), (0, 5.2, False)]:
        dock.toleranceTypeComboBox.setCurrentIndex(index)
        assert dock.rotateDoubleSpinBox.value() == rotate
        assert dock.nonCollocatedDmeCheckBox.isChecked() == enabled
        assert dock.trackingLayerLabel.isHidden() == (not enabled)
        assert dock.trackingLayerComboBox.currentLayer() == points[1]
        assert dock.pointLayerComboBox.currentLayer() == points[0]
    dock.nonCollocatedDmeCheckBox.setChecked(True)
    assert not dock.trackingLayerComboBox.isHidden()


def test_preview_matches_result_and_tracks_selection(dock, points):
    dock.trackingLayerComboBox.setLayer(points[1])
    dock.nonCollocatedDmeCheckBox.setChecked(True)
    preview = dock._preview_band.asGeometry()
    assert not preview.isEmpty()
    dock.calculate()
    output = next(_outputs()[0].getFeatures()).geometry()
    assert output.symDifference(preview).area() < 1e-5
    assert dock._preview_band.asGeometry().isEmpty()
    points[1].removeSelection()
    assert dock._preview_band.asGeometry().isEmpty()
    points[1].selectAll()
    assert not dock._preview_band.asGeometry().isEmpty()
    dock.hide()
    assert dock._preview_band.asGeometry().isEmpty()
    dock.show()
    assert not dock._preview_band.asGeometry().isEmpty()


def test_tracking_connections_are_conditional_and_deduplicated(dock, points):
    dock.trackingLayerComboBox.setLayer(points[1])
    assert points[1] not in dock._connected_layers
    dock.nonCollocatedDmeCheckBox.setChecked(True)
    assert points[1] in dock._connected_layers
    dock.nonCollocatedDmeCheckBox.setChecked(False)
    assert points[1] not in dock._connected_layers
    dock.nonCollocatedDmeCheckBox.setChecked(True)
    dock.trackingLayerComboBox.setLayer(points[0])
    assert len(dock._connected_layers) == 2
    assert points[1] not in dock._connected_layers
    dock.nonCollocatedDmeCheckBox.setChecked(False)
    assert len(dock._connected_layers) == 2


@pytest.mark.parametrize('failure', ['divergence', 'missing', 'crs', 'transform'])
def test_dock_warns_and_clears_preview_without_creating_layer(dock, points, failure):
    dock.trackingLayerComboBox.setLayer(points[1])
    dock.nonCollocatedDmeCheckBox.setChecked(True)
    assert not dock._preview_band.asGeometry().isEmpty()
    if failure == 'divergence':
        tracking = _point_layer('Bad angle', [(510000, 1590000)])
        dock.trackingLayerComboBox.setLayer(tracking)
    elif failure == 'missing':
        dock.trackingLayerComboBox.setLayer(None)
    elif failure == 'transform':
        tracking = _point_layer('Invalid latitude', [(-87, 100)], 'EPSG:4326')
        dock.trackingLayerComboBox.setLayer(tracking)
    else:
        dock.iface.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    assert dock._preview_band.asGeometry().isEmpty()
    assert dock.iface.bar.messages == []  # Preview does not repeatedly warn.
    dock.calculate()
    assert _outputs() == []
    assert dock.iface.bar.messages[-1][1]['level'] == Qgis.Warning
    message = dock.iface.bar.messages[-1][0][1]
    assert message in dock.logTextEdit.toPlainText()
    if failure == 'divergence':
        assert '90' in message and '23' in message
