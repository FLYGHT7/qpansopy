"""Real-QGIS output gates for the CONV Initial Approach tool's Qt6 migration."""
import math

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    Qgis, QgsFeature, QgsGeometry, QgsMapLayerProxyModel, QgsPointXY, QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402
from .test_qt6_plugin_runtime import plugin, qgis_app  # noqa: F401,E402

FIX = (500000.0, 1600000.0)
LENGTH = 20000.0
HALF = 2.5 * 1852  # Primary half-width and secondary width in metres.
OUTPUT = 'CONV Initial Approach Areas'


def offset(along, right, track_deg):
    """Point `along` metres on the track and `right` metres to its right of FIX."""
    a = math.radians(track_deg)
    return (FIX[0] + along * math.sin(a) + right * math.cos(a),
            FIX[1] + along * math.cos(a) - right * math.sin(a))


def expected_areas(z_primary, z_outer):
    """(Symbol, area_side, ring as (along, right, z)).

    Secondary Z is preserved as produced today: the inner edge (2.5 NM) carries
    z_outer and the outer edge (5 NM) carries z_primary.
    """
    length, half = LENGTH, HALF
    zp, zo = z_primary, z_outer
    return [
        ('Primary Area', '-', [
            (length, half, zp), (length, 0, zp), (length, -half, zp), (0, -half, zp),
            (0, 0, zp), (0, half, zp), (length, half, zp)]),
        ('Secondary Area', 'Left', [
            (length, -half, zo), (length, -2 * half, zp), (0, -2 * half, zp),
            (0, -half, zo), (length, -half, zo)]),
        ('Secondary Area', 'Right', [
            (length, 2 * half, zp), (length, half, zo), (0, half, zo),
            (0, 2 * half, zp), (length, 2 * half, zp)]),
    ]


def routing_layer(track_deg, select=True):
    layer = QgsVectorLayer('LineString?crs=EPSG:32616', 'routing', 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(*FIX), QgsPointXY(*offset(LENGTH, 0, track_deg))]))
    assert layer.dataProvider().addFeatures([feature])[0]
    QgsProject.instance().addMapLayer(layer)
    if select:
        layer.selectAll()
    return layer


def capture_messages(instance, monkeypatch):
    messages = []
    monkeypatch.setattr(instance.iface.messageBar(), 'pushMessage',
                        lambda *args, **kwargs: messages.append((args, kwargs['level'])))
    return messages


def outputs():
    return [layer for layer in QgsProject.instance().mapLayers().values()
            if layer.name() == OUTPUT]


def assert_areas(layer, track_deg, z_primary, z_outer, proc_alt_ft, moc, moc_unit):
    assert layer.wkbType() == Qgis.WkbType.PolygonZ
    assert layer.crs().authid() == 'EPSG:32616'
    assert [(field.name(), field.type()) for field in layer.fields()] == [
        ('Symbol', QMetaType.Type.QString), ('area_side', QMetaType.Type.QString),
        ('proc_alt_ft', QMetaType.Type.Double), ('moc', QMetaType.Type.Double),
        ('moc_unit', QMetaType.Type.QString),
    ]
    features = list(layer.getFeatures())
    expected = expected_areas(z_primary, z_outer)
    assert len(features) == len(expected)
    for feature, (symbol, side, ring) in zip(features, expected):
        assert feature.attributes() == [symbol, side, proc_alt_ft, moc, moc_unit]
        geometry = feature.geometry()
        assert geometry.wkbType() == Qgis.WkbType.PolygonZ
        assert geometry.isGeosValid()
        width = 2 * HALF if symbol == 'Primary Area' else HALF
        assert geometry.area() == pytest.approx(width * LENGTH, rel=1e-9)
        vertices = list(geometry.vertices())
        assert len(vertices) == len(ring)
        for vertex, (along, right, z) in zip(vertices, ring):
            assert (vertex.x(), vertex.y()) == pytest.approx(
                offset(along, right, track_deg), abs=1e-6)
            assert vertex.z() == pytest.approx(z)
    renderer = layer.renderer()
    assert renderer.type() == 'categorizedSymbol'
    assert renderer.classAttribute() == 'Symbol'
    assert [category.value() for category in renderer.categories()] == [
        'Primary Area', 'Secondary Area', '']
    assert layer.selectedFeatureCount() == 0


@pytest.mark.parametrize('track_deg', [0, 45, 90, 300])
def test_module_builds_3d_primary_and_secondary_areas(plugin, monkeypatch, track_deg):
    from Q_Pansopy.modules.conv.conv_initial_approach import run_conv_initial_approach

    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    assert run_conv_initial_approach(instance.iface, routing_layer(track_deg)) is True
    assert len(outputs()) == 1
    assert_areas(outputs()[0], track_deg, 213.36, 304.8, 1000.0, 300.0, 'ft')
    assert messages == [
        (('QPANSOPY:', 'Executing CONV Initial Approach Segment Straight'),
         Qgis.MessageLevel.Info),
        (('QPANSOPY:', 'Finished CONV Initial Approach Segment - 3 areas created '
                       '(Z_primary=213.36 m, Z_outer=304.80 m)'),
         Qgis.MessageLevel.Success),
    ]


def test_moc_in_metres_sets_primary_and_outer_z(plugin, monkeypatch):
    from Q_Pansopy.modules.conv.conv_initial_approach import run_conv_initial_approach

    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    assert run_conv_initial_approach(instance.iface, routing_layer(90), {
        'procedure_altitude_ft': 2000, 'moc_value': 150, 'moc_unit': 'm'})
    assert_areas(outputs()[0], 90, 459.6, 609.6, 2000.0, 150.0, 'm')
    assert messages[-1] == (
        ('QPANSOPY:', 'Finished CONV Initial Approach Segment - 3 areas created '
                      '(Z_primary=459.60 m, Z_outer=609.60 m)'),
        Qgis.MessageLevel.Success)


def test_module_exports_styled_kml(plugin, monkeypatch, tmp_path):
    from Q_Pansopy.modules.conv.conv_initial_approach import run_conv_initial_approach

    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    assert run_conv_initial_approach(
        instance.iface, routing_layer(0), export_kml=True, output_dir=str(tmp_path))
    exported = sorted(tmp_path.glob('conv_initial_approach_*.kml'))
    assert len(exported) == 1
    text = exported[0].read_text(encoding='utf-8')
    assert text.count('<Placemark') == 3
    assert '<altitudeMode>absolute</altitudeMode>' in text
    assert '7f00c800' in text
    assert messages[-1] == (('Success', f'KML exported: {exported[0]}'),
                            Qgis.MessageLevel.Success)


@pytest.mark.parametrize('case,message', [
    ('missing', 'No routing layer provided'),
    ('unselected', 'No features selected in routing layer'),
])
def test_module_rejects_missing_layer_or_selection(plugin, monkeypatch, case, message):
    from Q_Pansopy.modules.conv.conv_initial_approach import run_conv_initial_approach

    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    layer = None if case == 'missing' else routing_layer(0, select=False)
    assert run_conv_initial_approach(instance.iface, layer) is False
    assert not outputs()
    assert messages == [((message,), Qgis.MessageLevel.Critical)]


def test_dock_calculates_with_default_parameters(plugin, monkeypatch):
    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    route = routing_layer(45)
    instance.toggle_dock('CONV_INITIAL')
    dock = instance.modules['CONV_INITIAL']['GUI_INSTANCE']
    assert dock.routingLayerComboBox.filters() == QgsMapLayerProxyModel.Filter.LineLayer
    assert dock.procAltSpinBox.value() == 1000.0
    assert dock.mocSpinBox.value() == 300.0
    units = [dock.mocUnitComboBox.itemText(i) for i in range(dock.mocUnitComboBox.count())]
    assert units == ['ft', 'm'] and dock.mocUnitComboBox.currentText() == 'ft'
    assert not dock.exportKmlCheckBox.isChecked()
    dock.routingLayerComboBox.setLayer(route)
    dock.calculateButton.click()
    assert len(outputs()) == 1
    assert_areas(outputs()[0], 45, 213.36, 304.8, 1000.0, 300.0, 'ft')
    assert [level for _, level in messages] == [
        Qgis.MessageLevel.Info, Qgis.MessageLevel.Success]
    assert dock.logTextEdit.toPlainText().splitlines()[-1] == \
        'CONV Initial Approach Areas calculation completed successfully'


def test_dock_requires_a_selected_segment(plugin, monkeypatch):
    instance, _ = plugin
    messages = capture_messages(instance, monkeypatch)
    route = routing_layer(0, select=False)
    instance.toggle_dock('CONV_INITIAL')
    dock = instance.modules['CONV_INITIAL']['GUI_INSTANCE']
    dock.routingLayerComboBox.setLayer(route)
    dock.calculateButton.click()
    assert dock.logTextEdit.toPlainText().splitlines()[-1] == \
        'Error: Please select at least one segment in the map before calculation'
    assert messages == []
    assert not outputs()


def test_dock_preseeds_active_line_layer(plugin):
    from Q_Pansopy.dockwidgets.conv.qpansopy_conv_initial_dockwidget import (
        QPANSOPYConvInitialDockWidget,
    )

    instance, _ = plugin
    route = routing_layer(0)
    instance.iface.activeLayer = lambda: route
    dock = QPANSOPYConvInitialDockWidget(instance.iface)
    try:
        assert dock.routingLayerComboBox.currentLayer() is route
    finally:
        dock.close()
        dock.deleteLater()
