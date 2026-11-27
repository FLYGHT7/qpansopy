"""Real-QGIS output preservation gates for PBN Target's Qt6 migration."""
import math
from pathlib import Path

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402
from .test_qt6_plugin_runtime import plugin, qgis_app  # noqa: F401,E402


def point_layer(crs='EPSG:32616', populated=True):
    layer = QgsVectorLayer(f'Point?crs={crs}', 'ARP', 'memory')
    if populated:
        features = []
        for x in (500000, 600000):
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, 1600000)))
            features.append(feature)
        assert layer.dataProvider().addFeatures(features)[0]
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.mark.parametrize('selected', [False, True])
def test_calculate_button_preserves_rings_fields_selection_and_style(plugin, monkeypatch, selected):
    instance, _ = plugin
    layer = point_layer()
    points = list(layer.getFeatures())
    chosen = points[1] if selected else points[0]
    if selected:
        layer.selectByIds([chosen.id()])
    center = chosen.geometry().asPoint()
    zooms = []
    monkeypatch.setattr(instance.iface.mapCanvas(), 'zoomToSelected',
                        lambda output: zooms.append(output.selectedFeatureCount()))
    instance.toggle_dock('PBN_TARGET')
    dock = instance.modules['PBN_TARGET']['GUI_INSTANCE']
    dock.pointLayerComboBox.setLayer(layer)
    dock.calculateButton.click()
    outputs = [l for l in QgsProject.instance().mapLayers().values() if l.name() == 'PBN_target']
    assert len(outputs) == 1
    output = outputs[0]
    assert output.crs() == layer.crs()
    assert output.featureCount() == 2
    assert output.fields().names() == ['target']
    assert output.fields()[0].type() == QMetaType.Type.QString
    for feature in output.getFeatures():
        radius = {'15 NM ARP': 27780, '30 NM ARP': 55560}[feature['target']]
        geometry = feature.geometry()
        assert geometry.isGeosValid()
        assert geometry.centroid().asPoint().distance(center) < 1e-6
        assert geometry.area() == pytest.approx(math.pi * radius**2, rel=1e-5)
        assert all(math.hypot(v.x()-center.x(), v.y()-center.y()) == pytest.approx(radius)
                   for v in geometry.vertices())
    reference = QgsVectorLayer('Polygon?crs=EPSG:32616', 'reference', 'memory')
    style = Path(__file__).resolve().parents[2] / 'Q_Pansopy/styles/pbn_target.qml'
    assert reference.loadNamedStyle(str(style))[1]
    def categories(renderer):
        return [(category.value(), category.label(), category.symbol().opacity(),
                 [part.properties() for part in category.symbol().symbolLayers()])
                for category in renderer.categories()]

    assert output.renderer().classAttribute() == reference.renderer().classAttribute()
    assert categories(output.renderer()) == categories(reference.renderer())
    assert output.labelsEnabled() == reference.labelsEnabled()
    assert zooms == [2] and output.selectedFeatureCount() == 0
    assert layer.selectedFeatureIds() == ([chosen.id()] if selected else [])
    assert 'created successfully' in dock.logTextEdit.toPlainText()


@pytest.mark.parametrize('invalid', ['missing', 'empty', 'geographic'])
def test_rejected_inputs_create_no_output(plugin, invalid):
    from Q_Pansopy.modules.pbn.pbn_target import run_pbn_target

    instance, _ = plugin
    layer = (None if invalid == 'missing' else
             point_layer(crs='EPSG:4326' if invalid == 'geographic' else 'EPSG:32616',
                         populated=invalid != 'empty'))
    before = set(QgsProject.instance().mapLayers())
    assert run_pbn_target(instance.iface, layer) is None
    assert set(QgsProject.instance().mapLayers()) == before


def test_dock_requires_a_point_layer(plugin):
    instance, _ = plugin
    instance.toggle_dock('PBN_TARGET')
    dock = instance.modules['PBN_TARGET']['GUI_INSTANCE']
    dock.pointLayerComboBox.setAllowEmptyLayer(True)
    dock.pointLayerComboBox.setLayer(None)
    dock.calculateButton.click()
    assert 'Please select a point layer' in dock.logTextEdit.toPlainText()
    assert not QgsProject.instance().mapLayers()
