"""QGIS runtime checks for the HoldingBasicArea table action."""

import json

import pytest

pytest.importorskip('qgis')

from qgis.PyQt.QtWidgets import QMainWindow  # noqa: E402
from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProject, QgsVectorLayer,
)

from Q_Pansopy.dockwidgets.utilities.qpansopy_holding_dockwidget import (  # noqa: E402
    QPANSOPYHoldingDockWidget,
)
from Q_Pansopy.modules.utilities.holding import (  # noqa: E402
    build_holding_feature_parameters, build_holding_table_views,
    run_holding_pattern,
)
from Q_Pansopy import parameters_inspector_dialog  # noqa: E402


class _Iface:
    def __init__(self):
        self.window = QMainWindow()
        self.messages = []

    def mainWindow(self):
        return self.window

    def activeLayer(self):
        return None

    def mapCanvas(self):
        return self

    def mapSettings(self):
        return self

    def destinationCrs(self):
        return QgsCoordinateReferenceSystem('EPSG:32616')

    def messageBar(self):
        return self

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


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
def routing():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    layer = QgsVectorLayer('LineString?crs=EPSG:32616', 'routing', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(500000, 1600000), QgsPointXY(501000, 1600000),
    ]))
    layer.dataProvider().addFeatures([feature])
    layer.selectByIds([next(layer.getFeatures()).id()])
    yield layer
    project.removeAllMapLayers()


def _calculate(iface, routing_layer, show_circles=False):
    return run_holding_pattern(iface, routing_layer, {
        'IAS': 195, 'altitude': 10000, 'altitude_unit': 'ft',
        'isa_var': 0, 'bank_angle': 25, 'leg_time_min': 1,
        'turn': 'R', 'show_circles': show_circles,
    })


def test_area_action_and_dock_show_same_table(routing, monkeypatch):
    iface = _Iface()
    result = _calculate(iface, routing, show_circles=True)
    assert result
    layers = list(QgsProject.instance().mapLayers().values())
    area = next(layer for layer in layers if layer.name() == 'HoldingBasicArea')
    circles = next(layer for layer in layers if layer.name() == 'HoldingWindCircles')
    nominal = result['layer']
    assert len(circles.actions().actions()) == 0
    assert len(nominal.actions().actions()) == 0
    assert nominal.fields().indexFromName('parameters') == -1
    assert len(area.actions().actions()) == 1
    action = area.actions().actions()[0]
    assert action.name() == 'view parameters as HTML Table'
    assert action.actionScopes() == {'Feature', 'Canvas'}

    feature = next(area.getFeatures())
    expected = build_holding_feature_parameters(result['summary'])
    assert json.loads(feature['parameters']) == expected
    shown = []
    monkeypatch.setattr(
        parameters_inspector_dialog, 'show_web_popup',
        lambda title, sections, **kwargs: shown.append((title, sections, kwargs)))
    dock = QPANSOPYHoldingDockWidget(iface)
    dock.last_summary = result['summary']
    dock.show_parameters_table()
    dock.close()
    parameters_inspector_dialog.show_parameters_inspector(area.id(), feature.id())
    dock_views = shown[0][2]['table_views']
    action_views = shown[1][2]['table_views']
    assert [name for name, _content in dock_views] == ['Complete', 'Short']
    assert [name for name, _content in action_views] == ['Complete', 'Short']
    assert [content for _name, content in dock_views] == [
        content for _name, content in action_views]


def test_no_area_means_no_new_action(routing, monkeypatch):
    holding = __import__('Q_Pansopy.modules.utilities.holding', fromlist=['holding'])
    monkeypatch.setattr(holding, '_build_wind_circles', lambda *args: [])
    iface = _Iface()
    result = _calculate(iface, routing)
    assert result
    assert all(layer.name() != 'HoldingBasicArea'
               for layer in QgsProject.instance().mapLayers().values())
    assert len(result['layer'].actions().actions()) == 0
