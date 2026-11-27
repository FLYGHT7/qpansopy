"""Real-QGIS behavior gates for the NDB and VOR Qt6 migrations."""
import math
import importlib
from pathlib import Path

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402
from .test_qt6_plugin_runtime import plugin, qgis_app  # noqa: F401,E402


@pytest.fixture(params=[
    dict(name='NDB', limit=15, half_start=.625, outer_start=1.25, angle=10.3),
    dict(name='VOR', limit=20, half_start=.5, outer_start=1.0, angle=7.8),
], ids=['ndb', 'vor'])
def approach(request):
    return request.param


def calculation(approach):
    name = approach['name'].lower()
    return getattr(importlib.import_module(f'Q_Pansopy.modules.conv.{name}_approach'),
                   f'run_{name}_approach')


def route_layer(distance_nm=5, direction=(0, 1), selected=True, empty_geometry=False):
    layer = QgsVectorLayer('LineString?crs=EPSG:32616', 'routing', 'memory')
    feature = QgsFeature()
    if not empty_geometry:
        origin = QgsPointXY(500000, 1600000)
        end = QgsPointXY(origin.x()+direction[0]*distance_nm*1852,
                         origin.y()+direction[1]*distance_nm*1852)
        feature.setGeometry(QgsGeometry.fromPolylineXY([origin, end]))
    assert layer.dataProvider().addFeatures([feature])[0]
    QgsProject.instance().addMapLayer(layer)
    if selected:
        layer.selectAll()
    return layer


@pytest.mark.parametrize('distance_case', ['short', 'limit', 'long'])
@pytest.mark.parametrize('direction', [(0, 1), (1, 0), (math.sqrt(.5), math.sqrt(.5))])
def test_template_geometry_fields_style_and_zoom(plugin, monkeypatch, approach, distance_case, direction):
    distance_nm = {'short': 5, 'limit': approach['limit'], 'long': approach['limit'] + 5}[distance_case]

    instance, _ = plugin
    route = route_layer(distance_nm, direction)
    selected = route.selectedFeatureIds()
    zooms, scales = [], []
    canvas = instance.iface.mapCanvas()
    monkeypatch.setattr(canvas, 'zoomToSelected', lambda layer: zooms.append(layer.selectedFeatureCount()))
    initial_scale = 100000 if distance_nm < 15 else 400000
    monkeypatch.setattr(canvas, 'scale', lambda: initial_scale)
    monkeypatch.setattr(canvas, 'zoomScale', scales.append)
    assert calculation(approach)(instance.iface, route) is True
    outputs = [l for l in QgsProject.instance().mapLayers().values() if l.name() == f"{approach['name']} Approach Areas"]
    assert len(outputs) == 1
    output = outputs[0]
    assert output.crs() == route.crs() and output.featureCount() == 3
    assert output.fields().names() == ['Symbol']
    assert output.fields()[0].type() == QMetaType.Type.QString
    features = list(output.getFeatures())
    assert sorted(f['Symbol'] for f in features) == ['Primary Area', 'Secondary Area', 'Secondary Area']
    length_nm = min(distance_nm, approach['limit'])
    length = length_nm*1852
    outer_end = (approach['outer_start'] + length_nm*math.tan(math.radians(approach['angle'])))*1852
    primary_end = outer_end/2
    expected_primary_area = length*(approach['half_start']*1852 + primary_end)
    secondary_sides = []
    for f in features:
        geom = f.geometry()
        primary = f['Symbol'] == 'Primary Area'
        assert geom.isGeosValid()
        assert geom.area() == pytest.approx(expected_primary_area*(1 if primary else .5))
        for vertex in geom.vertices():
            x, y = vertex.x()-500000, vertex.y()-1600000
            along = x*direction[0]+y*direction[1]
            across = x*direction[1]-y*direction[0]
            at_start = abs(along) < 1e-6
            assert at_start or abs(along-length) < 1e-6
            inner = approach['half_start']*1852 if at_start else primary_end
            outer = approach['outer_start']*1852 if at_start else outer_end
            assert min(abs(abs(across)-width) for width in ([inner] if primary else [inner, outer])) < 1e-6
        if not primary:
            center = geom.centroid().asPoint()
            secondary_sides.append((center.x()-500000)*direction[1]-(center.y()-1600000)*direction[0])
    assert secondary_sides[0] == pytest.approx(-secondary_sides[1])
    reference = QgsVectorLayer('PolygonZ?crs=EPSG:32616', 'reference', 'memory')
    style = Path(__file__).resolve().parents[2] / 'Q_Pansopy/styles/primary_secondary_areas.qml'
    assert reference.loadNamedStyle(str(style))[1]
    def categories(renderer):
        return [(c.value(), c.label(), [part.properties() for part in c.symbol().symbolLayers()])
                for c in renderer.categories()]
    assert output.renderer().classAttribute() == reference.renderer().classAttribute()
    actual, expected = categories(output.renderer()), categories(reference.renderer())
    assert len(actual) == len(expected)
    for a, b in zip(actual, expected):
        assert a[:2] == b[:2]
        assert len(a[2]) == len(b[2])
        for pa, pb in zip(a[2], b[2]):
            # QGIS generates a new point-pattern seed on every style load.
            assert {k: v for k, v in pa.items() if k != 'seed'} == {
                k: v for k, v in pb.items() if k != 'seed'}
    assert zooms == [3] and output.selectedFeatureCount() == 0
    assert scales == [max(200000, initial_scale)]
    assert route.selectedFeatureIds() == selected


@pytest.mark.parametrize('invalid_geometry', [False, True])
def test_no_output_without_selection_or_with_empty_geometry(plugin, approach, invalid_geometry):

    instance, _ = plugin
    layer = route_layer(selected=invalid_geometry, empty_geometry=invalid_geometry)
    before = set(QgsProject.instance().mapLayers())
    assert calculation(approach)(instance.iface, layer) is False
    assert set(QgsProject.instance().mapLayers()) == before


def test_dock_preseeds_active_route_and_calculates(plugin, monkeypatch, approach):
    instance, _ = plugin
    layer = route_layer()
    monkeypatch.setattr(instance.iface, 'activeLayer', lambda: layer)
    instance.toggle_dock(f"{approach['name']}_CONV")
    dock = instance.modules[f"{approach['name']}_CONV"]['GUI_INSTANCE']
    assert dock.routingLayerComboBox.currentLayer() is layer
    dock.calculateButton.click()
    assert 'completed successfully' in dock.logTextEdit.toPlainText()
    assert len([l for l in QgsProject.instance().mapLayers().values() if l.name() == f"{approach['name']} Approach Areas"]) == 1


def test_dock_missing_route_and_cancelled_folder_browser(plugin, monkeypatch, approach):
    from qgis.PyQt.QtWidgets import QFileDialog

    instance, _ = plugin
    instance.toggle_dock(f"{approach['name']}_CONV")
    dock = instance.modules[f"{approach['name']}_CONV"]['GUI_INSTANCE']
    dock.routingLayerComboBox.setAllowEmptyLayer(True)
    dock.routingLayerComboBox.setLayer(None)
    dock.calculateButton.click()
    assert 'Please select a routing layer' in dock.logTextEdit.toPlainText()
    previous = dock.outputFolderLineEdit.text()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: '')
    dock.browseButton.click()
    assert dock.outputFolderLineEdit.text() == previous
    assert not QgsProject.instance().mapLayers()
