"""Execute the legacy straight CONV console script with controlled routing."""
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsFeature,
    QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


@pytest.mark.parametrize('dx,dy', [(0, 20000), (20000, 0), (20000, 20000)])
def test_legacy_script_preserves_areas_schema_zoom_and_console_context(dx, dy):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    route = QgsVectorLayer('LineString?crs=EPSG:32616', 'routing', 'memory')
    origin = QgsPointXY(500000, 1600000)
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        origin, QgsPointXY(origin.x()+dx, origin.y()+dy)]))
    assert route.dataProvider().addFeatures([feature])[0]
    project.addMapLayer(route)
    route.selectAll()
    original_selection = route.selectedFeatureIds()
    messages, zooms = [], []
    crs = QgsCoordinateReferenceSystem('EPSG:32616')
    canvas = SimpleNamespace(
        mapSettings=lambda: SimpleNamespace(destinationCrs=lambda: crs),
        zoomToSelected=lambda layer: zooms.append(layer.selectedFeatureCount()))
    iface = SimpleNamespace(
        mapCanvas=lambda: canvas,
        messageBar=lambda: SimpleNamespace(pushMessage=lambda *args, **kwargs: messages.append(kwargs['level'])))
    sentinel = object()
    # The original script relies on math being supplied by the console.
    namespace = {'iface': iface, 'math': math, 'sentinel': sentinel}
    script = Path(__file__).resolve().parents[2] / 'Q_Pansopy/modules/conv/conv_initial_approach_straight.py'
    try:
        exec(compile(script.read_text(encoding='utf-8-sig'), str(script), 'exec'), namespace)
        outputs = [layer for layer in project.mapLayers().values()
                   if layer.name() == 'Initial Approach Area']
        assert len(outputs) == 1
        output = outputs[0]
        assert output.crs() == crs and output.featureCount() == 3
        assert output.fields().names() == ['Symbol']
        assert output.fields()[0].type() == QMetaType.Type.QString
        length = math.hypot(dx, dy)
        along = (dx/length, dy/length)
        across = (dy/length, -dx/length)
        areas = list(output.getFeatures())
        assert sorted(f['Symbol'] for f in areas) == ['Primary Area', 'Secondary Area', 'Secondary Area']
        for f in areas:
            geom = f.geometry()
            primary = f['Symbol'] == 'Primary Area'
            assert geom.isGeosValid()
            assert geom.area() == pytest.approx(length * (5 if primary else 2.5) * 1852)
            center = geom.centroid().asPoint()
            cx, cy = center.x()-origin.x(), center.y()-origin.y()
            assert cx*along[0]+cy*along[1] == pytest.approx(length/2)
            assert abs(cx*across[0]+cy*across[1]) == pytest.approx(0 if primary else 3.75*1852, abs=1e-6)
            for vertex in geom.vertices():
                x, y = vertex.x()-origin.x(), vertex.y()-origin.y()
                longitudinal = x*along[0]+y*along[1]
                lateral = x*across[0]+y*across[1]
                assert min(abs(longitudinal), abs(longitudinal-length)) < 1e-6
                assert abs(lateral) <= (2.5 if primary else 5)*1852 + 1e-6
        assert zooms == [3] and output.selectedFeatureCount() == 0
        assert route.selectedFeatureIds() == original_selection
        assert messages == [Qgis.MessageLevel.Info, Qgis.MessageLevel.Success]
        assert namespace['iface'] is iface and namespace['sentinel'] is sentinel
        assert namespace['math'] is math
        assert 'pts' not in namespace and 'QgsGeometry' not in namespace
    finally:
        project.removeAllMapLayers()
