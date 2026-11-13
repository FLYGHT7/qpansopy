"""Execute the legacy console script with controlled QGIS data, never import it."""
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


@pytest.mark.parametrize('dx,dy', [(0, 10000), (10000, 0), (10000, 10000)])
def test_script_preserves_tolerance_geometry_schema_style_and_console_context(dx, dy):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    center = QgsPointXY(500000, 1600000)
    point = QgsVectorLayer('Point?crs=EPSG:32616', 'waypoint', 'memory')
    route = QgsVectorLayer('LineString?crs=EPSG:32616', 'routing', 'memory')
    for layer, geometry in [
        (point, QgsGeometry.fromPointXY(center)),
        (route, QgsGeometry.fromPolylineXY([center, QgsPointXY(center.x()+dx, center.y()+dy)])),
    ]:
        feature = QgsFeature()
        feature.setGeometry(geometry)
        assert layer.dataProvider().addFeatures([feature])[0]
        project.addMapLayer(layer)
        layer.selectAll()
    messages, refreshed = [], []
    crs = QgsCoordinateReferenceSystem('EPSG:32616')
    iface = SimpleNamespace(
        activeLayer=lambda: point,
        mapCanvas=lambda: SimpleNamespace(mapSettings=lambda: SimpleNamespace(destinationCrs=lambda: crs)),
        messageBar=lambda: SimpleNamespace(pushMessage=lambda *args, **kwargs: messages.append(kwargs['level'])),
        layerTreeView=lambda: SimpleNamespace(refreshLayerSymbology=refreshed.append),
    )
    sentinel = object()
    namespace = {'iface': iface, 'sentinel': sentinel}
    script = Path(__file__).resolve().parents[2] / 'Q_Pansopy/modules/utilities/fix_tolerances/GNSS_waypoint.py'
    try:
        exec(compile(script.read_text(encoding='utf-8-sig'), str(script), 'exec'), namespace)
        outputs = [layer for layer in project.mapLayers().values() if layer.name() == 'Tolerances']
        assert len(outputs) == 1
        output = outputs[0]
        assert output.crs() == crs and output.featureCount() == 1
        assert output.fields().names() == ['XTT', 'ATT']
        assert all(field.type() == QMetaType.Type.QString for field in output.fields())
        feature = next(output.getFeatures())
        assert feature.attributes() == ['1.0 NM', '0.8 NM']
        geometry = feature.geometry()
        assert geometry.isGeosValid()
        assert geometry.area() == pytest.approx(3704 * 2963.2)
        assert geometry.centroid().asPoint().distance(center) < 1e-7
        angle = math.atan2(dx, dy)
        for x, y in [(-1852, -1481.6), (-1852, 1481.6), (1852, -1481.6), (1852, 1481.6)]:
            expected = QgsPointXY(center.x()+x*math.cos(angle)+y*math.sin(angle),
                                  center.y()-x*math.sin(angle)+y*math.cos(angle))
            assert min(math.hypot(v.x()-expected.x(), v.y()-expected.y())
                       for v in geometry.vertices()) < 1e-6
        symbol = output.renderer().symbol()
        assert symbol.opacity() == pytest.approx(.3)
        assert symbol.color().name() == '#0000ff'
        assert refreshed == [point.id()]
        assert messages == [Qgis.MessageLevel.Info, Qgis.MessageLevel.Success]
        assert namespace['iface'] is iface and namespace['sentinel'] is sentinel
        assert 'polygon' not in namespace and 'QgsGeometry' not in namespace
    finally:
        project.removeAllMapLayers()
