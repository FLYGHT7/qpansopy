"""Execute the legacy Holding/Racetrack console script with controlled routing."""
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
from qgis.PyQt.QtGui import QColor  # noqa: E402

SCRIPT = (Path(__file__).resolve().parents[2]
          / 'Q_Pansopy/modules/utilities/conventional_holding_navaid.py')
FIX = QgsPointXY(500000, 1600000)
# holding_basic_area(195, 10000, 0, 15, 25, 1)[10]: one-minute outbound leg in NM.
LEG_NM = 3.886223684724363
LEG_M = LEG_NM * 1852


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
    """Point `along` metres on the inbound track and `right` metres to its right of FIX."""
    a = math.radians(track_deg)
    return (FIX.x() + along * math.sin(a) + right * math.cos(a),
            FIX.y() + along * math.cos(a) - right * math.sin(a))


@pytest.mark.parametrize('track_deg', [0, 45, 90, 300])
def test_legacy_script_preserves_racetrack_schema_style_and_console_context(track_deg, capsys):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    route = QgsVectorLayer('LineString?crs=EPSG:32616', 'routing', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(*offset(-20000, 0, track_deg)), FIX]))
    assert route.dataProvider().addFeatures([feature])[0]
    project.addMapLayer(route)
    route.selectAll()
    original_selection = route.selectedFeatureIds()
    messages = []
    crs = QgsCoordinateReferenceSystem('EPSG:32616')
    canvas = SimpleNamespace(
        mapSettings=lambda: SimpleNamespace(destinationCrs=lambda: crs))
    iface = SimpleNamespace(
        mapCanvas=lambda: canvas,
        messageBar=lambda: SimpleNamespace(
            pushMessage=lambda *args, **kwargs: messages.append((args, kwargs['level']))))
    sentinel = object()
    # The QGIS Python console supplies iface and math to the legacy script.
    namespace = {'iface': iface, 'math': math, 'sentinel': sentinel}
    try:
        exec(compile(SCRIPT.read_text(encoding='utf-8-sig'), str(SCRIPT), 'exec'), namespace)
        assert repr(LEG_NM) in capsys.readouterr().out.split()
        outputs = [layer for layer in project.mapLayers().values() if layer is not route]
        assert len(outputs) == 1
        output = outputs[0]
        assert output.name() == 'HLDG/RACETRACK 195KTS'
        assert output.crs() == crs
        assert output.wkbType() == Qgis.WkbType.LineString
        assert output.fields().names() == ['segment']
        assert output.fields()[0].type() == QMetaType.Type.QString
        leg = LEG_M
        # (geometry type, vertices as (along, right) offsets from FIX, length).
        # The pattern turns to the LEFT of the inbound track (pre-existing behaviour).
        expected = [
            (Qgis.WkbType.LineString, [(-leg, 0), (0, 0)], leg),
            (Qgis.WkbType.CircularString,
             [(0, 0), (leg / 2, -leg / 2), (0, -leg)], math.pi * leg / 2),
            (Qgis.WkbType.LineString, [(0, -leg), (-leg, -leg)], leg),
            (Qgis.WkbType.CircularString,
             [(-leg, -leg), (-1.5 * leg, -leg / 2), (-leg, 0)], math.pi * leg / 2),
        ]
        segments = list(output.getFeatures())
        assert len(segments) == len(expected)
        for segment, (wkb_type, vertices, length) in zip(segments, expected):
            geometry = segment.geometry()
            assert segment.attributes() == [None]
            assert geometry.wkbType() == wkb_type
            assert geometry.length() == pytest.approx(length, rel=1e-9)
            actual = [(v.x(), v.y()) for v in geometry.vertices()]
            assert len(actual) == len(vertices)
            for point, (along, right) in zip(actual, vertices):
                assert point == pytest.approx(offset(along, right, track_deg), abs=1e-6)
        symbol = output.renderer().symbol()
        assert symbol.color() == QColor('magenta')
        assert symbol.width() == pytest.approx(0.7)
        assert route.selectedFeatureIds() == original_selection
        assert messages == [
            (('QPANSOPY:', 'Holding/Racetrack Basic Area'), Qgis.MessageLevel.Info),
            (('QPANSOPY:', 'Finished Holding/Racetrack'), Qgis.MessageLevel.Success),
        ]
        # Caller objects survive; script globals are deleted ('g' is the cleanup
        # loop variable the original script leaves behind).
        assert namespace['iface'] is iface and namespace['sentinel'] is sentinel
        assert namespace['math'] is math
        assert set(namespace) - {'__builtins__'} == {
            '__doc__', 'g', 'iface', 'math', 'myglobals', 'sentinel'}
    finally:
        project.removeAllMapLayers()
