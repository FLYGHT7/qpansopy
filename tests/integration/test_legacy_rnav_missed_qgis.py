"""Execute the legacy RNAV 1/2 missed-approach console script with a controlled iface."""
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

SCRIPT = (Path(__file__).resolve().parents[2]
          / 'Q_Pansopy/modules/pbn/rnav1_2_missed_less_15nm.py')
FIX = QgsPointXY(500000, 1600000)
LENGTH = 20000
NM = 1852
# Script points m0..m9 as (along, right) offsets from the first route vertex.
POINTS = {
    'm0': (LENGTH, 0), 'm1': (0, 0),
    'm2': (LENGTH, NM), 'm3': (LENGTH, 2 * NM), 'm4': (LENGTH, -NM), 'm5': (LENGTH, -2 * NM),
    'm6': (0, NM), 'm7': (0, 2 * NM), 'm8': (0, -NM), 'm9': (0, -2 * NM),
}
# (Symbol, ring vertices, area). The script's "Left"/"Right" comments are preserved as-is.
AREAS = [
    ('Primary Area', ['m2', 'm0', 'm4', 'm8', 'm1', 'm6', 'm2'], 2 * NM * LENGTH),
    ('Secondary Area', ['m3', 'm2', 'm6', 'm7', 'm3'], NM * LENGTH),
    ('Secondary Area', ['m4', 'm5', 'm9', 'm8', 'm4'], NM * LENGTH),
]


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


def offset(along, right, track_deg):
    """Point `along` metres on the track and `right` metres to its right of FIX."""
    a = math.radians(track_deg)
    return (FIX.x() + along * math.sin(a) + right * math.cos(a),
            FIX.y() + along * math.cos(a) - right * math.sin(a))


@pytest.mark.parametrize('track_deg', [0, 45, 90, 300])
def test_legacy_script_preserves_areas_schema_zoom_and_console_context(track_deg, capsys):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    route = QgsVectorLayer('LineString?crs=EPSG:32616', 'missed', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        FIX, QgsPointXY(*offset(LENGTH, 0, track_deg))]))
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
        activeLayer=lambda: route, mapCanvas=lambda: canvas,
        messageBar=lambda: SimpleNamespace(
            pushMessage=lambda *args, **kwargs: messages.append((args, kwargs['level']))))
    sentinel = object()
    # The QGIS Python console supplies iface and math to the legacy script.
    namespace = {'iface': iface, 'math': math, 'sentinel': sentinel}
    try:
        exec(compile(SCRIPT.read_text(encoding='utf-8-sig'), str(SCRIPT), 'exec'), namespace)
        printed = capsys.readouterr().out
        assert all(f"'m{i}': <QgsPoint: Point" in printed for i in range(10))
        outputs = [layer for layer in project.mapLayers().values() if layer is not route]
        assert len(outputs) == 1
        output = outputs[0]
        assert output.name() == 'PBN RNAV 1/2'
        assert output.crs() == crs
        assert output.wkbType() == Qgis.WkbType.PolygonZ
        assert output.fields().names() == ['Symbol']
        assert output.fields()[0].type() == QMetaType.Type.QString
        assert output.renderer().type() == 'singleSymbol'
        features = list(output.getFeatures())
        assert len(features) == len(AREAS)
        for area_feature, (symbol, ring, area) in zip(features, AREAS):
            geometry = area_feature.geometry()
            assert area_feature.attributes() == [symbol]
            assert geometry.wkbType() == Qgis.WkbType.Polygon
            assert geometry.isGeosValid()
            assert geometry.area() == pytest.approx(area, rel=1e-9)
            actual = [(v.x(), v.y()) for v in geometry.vertices()]
            assert len(actual) == len(ring)
            for point, name in zip(actual, ring):
                assert point == pytest.approx(offset(*POINTS[name], track_deg), abs=1e-6)
        assert zooms == [3] and output.selectedFeatureCount() == 0
        assert route.selectedFeatureIds() == original_selection
        assert messages == [
            (('QPANSOPY:', 'Executing CONV Initial Approach Segment Straight'),
             Qgis.MessageLevel.Info),
            (('QPANSOPY:', 'Finished RNAV1/2 <30NM'), Qgis.MessageLevel.Success),
        ]
        # Caller objects survive; script globals are deleted ('g' is the cleanup
        # loop variable the original script leaves behind).
        assert namespace['iface'] is iface and namespace['sentinel'] is sentinel
        assert namespace['math'] is math
        assert set(namespace) - {'__builtins__'} == {
            '__doc__', 'g', 'iface', 'math', 'myglobals', 'sentinel'}
    finally:
        project.removeAllMapLayers()
