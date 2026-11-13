"""Real Qt6/QGIS widgets and signals used as gates for every migration batch."""
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsFeature,
    QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas, QgsMessageBar  # noqa: E402
from qgis.PyQt import uic  # noqa: E402
from qgis.PyQt.QtCore import QSettings, QT_VERSION_STR  # noqa: E402
from qgis.PyQt.QtWidgets import QMainWindow, QMessageBox  # noqa: E402


TOOLS = (
    'VSS', 'ILS_BASIC', 'WindSpiral', 'ILS_OAS', 'LNAV_APCH', 'PBN_TARGET',
    'DME_DME_COVERAGE', 'PBN_ENROUTE_GNSS', 'GNSS_WAYPOINT', 'VOR_CONV',
    'NDB_CONV', 'CONV_INITIAL', 'DME_TOL', 'OVERHEAD_TOL', 'RADIAL_BEARING_TOL',
    'ENROUTE_VOR_VOR', 'ObjectSelection', 'PrimaryAreaAssessment',
    'SlopePrimaryAreaAssessment', 'SecondaryAreaAssessment', 'AMAGrid',
    'PointFilter', 'FeatureMerge', 'Holding', 'CIRCLING', 'SID_INITIAL',
    'OMNIDIRECTIONAL_SID',
)
UI_ROOT = Path(__file__).resolve().parents[2] / 'Q_Pansopy/ui'


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    assert 40000 <= Qgis.QGIS_VERSION_INT < 50000
    assert QT_VERSION_STR.split('.')[0] == '6'
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


@pytest.fixture
def plugin(qgis_app, monkeypatch, tmp_path):
    from Q_Pansopy import qpansopy

    def unexpected_dialog(*args, **kwargs):
        pytest.fail(f'Unexpected modal dialog: {args[1:]}')

    for name in ('critical', 'warning', 'information'):
        monkeypatch.setattr(QMessageBox, name, unexpected_dialog)
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(qpansopy, 'QSettings', lambda: settings)
    window = QMainWindow()
    window.resize(1200, 900)
    canvas = QgsMapCanvas(window)
    canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:32616'))
    window.setCentralWidget(canvas)
    bar = QgsMessageBar(window)
    selected = []
    iface = SimpleNamespace(
        mainWindow=lambda: window, mapCanvas=lambda: canvas,
        messageBar=lambda: bar, activeLayer=lambda: None,
        addToolBar=window.addToolBar, addDockWidget=window.addDockWidget,
        removeDockWidget=window.removeDockWidget,
        layerTreeView=lambda: SimpleNamespace(selectedLayers=lambda: selected),
    )
    assert not qpansopy._IMPORT_ERRORS
    from Q_Pansopy import classFactory
    instance = classFactory(iface)
    instance.initGui()
    window.show()
    qgis_app.processEvents()
    try:
        yield instance, selected
    finally:
        for entry in instance.modules.values():
            dock = entry['GUI_INSTANCE']
            if dock is not None:
                dock.close()
        instance.unload()
        window.close()
        window.deleteLater()
        QgsProject.instance().removeAllMapLayers()
        qgis_app.processEvents()


def test_all_tools_are_registered_with_connected_actions(plugin):
    instance, _ = plugin
    assert set(instance.modules) == set(TOOLS)
    assert len(instance.actions) == len(TOOLS)
    assert all(action.isEnabled() for action in instance.actions)


@pytest.mark.parametrize('tool', [name for name in TOOLS if name != 'FeatureMerge'])
def test_toolbar_opens_hides_reopens_and_closes_same_dock(plugin, qgis_app, tool):
    instance, _ = plugin
    index = list(instance.modules).index(tool)
    action = instance.actions[index]
    action.trigger()
    qgis_app.processEvents()
    dock = instance.modules[tool]['GUI_INSTANCE']
    assert dock is not None and dock.isVisible()
    assert dock.widget() is not None
    action.trigger()
    qgis_app.processEvents()
    assert not dock.isVisible()
    action.trigger()
    qgis_app.processEvents()
    assert instance.modules[tool]['GUI_INSTANCE'] is dock
    assert dock.isVisible()
    closed = []
    dock.closingPlugin.connect(lambda: closed.append(True))
    dock.close()
    qgis_app.processEvents()
    assert closed and not dock.isVisible()


@pytest.mark.parametrize('form', sorted(p.relative_to(UI_ROOT) for p in UI_ROOT.rglob('*.ui')))
def test_form_loads_with_qt6_uic(form):
    form_class, base_class = uic.loadUiType(str(UI_ROOT / form))
    assert callable(form_class.setupUi)
    assert base_class is not None


def test_feature_merge_toolbar_action_merges_selected_layers(plugin, qgis_app):
    instance, selected = plugin
    for index in range(2):
        layer = QgsVectorLayer('Point?crs=EPSG:32616&field=name:string', f'input{index}', 'memory')
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000 + index, 1600000)))
        feature['name'] = f'point{index}'
        assert layer.dataProvider().addFeatures([feature])[0]
        QgsProject.instance().addMapLayer(layer)
        selected.append(layer)
    instance.actions[list(instance.modules).index('FeatureMerge')].trigger()
    qgis_app.processEvents()
    outputs = [layer for layer in QgsProject.instance().mapLayers().values()
               if layer not in selected]
    assert len(outputs) == 1
    assert outputs[0].featureCount() == 2
    assert {f['name'] for f in outputs[0].getFeatures()} == {'point0', 'point1'}


def test_legacy_feature_merge_dock_still_loads(plugin, qgis_app):
    from Q_Pansopy.dockwidgets.utilities.qpansopy_feature_merge_dockwidget import (
        QPANSOPYFeatureMergeDockWidget,
    )
    instance, _ = plugin
    dock = QPANSOPYFeatureMergeDockWidget(instance.iface)
    dock.show()
    qgis_app.processEvents()
    assert dock.isVisible() and dock.widget() is not None
    dock.close()
    dock.deleteLater()


@pytest.mark.parametrize('geometry,kind', [
    ('Point', Qgis.GeometryType.Point),
    ('LineString', Qgis.GeometryType.Line),
    ('Polygon', Qgis.GeometryType.Polygon),
])
def test_transitional_preseed_uses_real_qgis_layer_combo(plugin, geometry, kind):
    from qgis.gui import QgsMapLayerComboBox
    from Q_Pansopy import qt_compat
    from Q_Pansopy.utils import preseed_active_layer

    assert qt_compat.get_qt_backend() == 'qgis.PyQt'
    assert qt_compat.preseed_active_layer is preseed_active_layer
    instance, _ = plugin
    layer = QgsVectorLayer(f'{geometry}?crs=EPSG:32616', 'active', 'memory')
    assert layer.isValid()
    QgsProject.instance().addMapLayer(layer)
    combo = QgsMapLayerComboBox(instance.iface.mainWindow())
    combo.setFilters(qt_compat.MLPM_VectorLayer)
    combo.setAllowEmptyLayer(True)
    combo.setLayer(None)
    preseed_active_layer(SimpleNamespace(activeLayer=lambda: layer), combo, kind)
    assert combo.currentLayer() is layer


def test_switching_tools_reuses_docks_and_applies_log_visibility(plugin, qgis_app):
    instance, _ = plugin
    instance.toggle_dock('VSS')
    first = instance.modules['VSS']['GUI_INSTANCE']
    instance.toggle_dock('ILS_BASIC')
    second = instance.modules['ILS_BASIC']['GUI_INSTANCE']
    assert second.isVisible() and not first.isVisible()
    instance._apply_log_visibility(False)
    assert second.logTextEdit.isHidden()
    instance._apply_log_visibility(True)
    qgis_app.processEvents()
    assert not second.logTextEdit.isHidden()
    instance.toggle_dock('VSS')
    assert instance.modules['VSS']['GUI_INSTANCE'] is first
    assert first.isVisible() and not second.isVisible()


def test_log_drag_uses_qt6_mouse_events_and_clamps_height(plugin):
    from qgis.PyQt.QtCore import Qt, QEvent, QPointF
    from qgis.PyQt.QtGui import QMouseEvent
    from qgis.PyQt.QtWidgets import QGroupBox

    instance, _ = plugin
    instance.toggle_dock('VSS')
    dock = instance.modules['VSS']['GUI_INSTANCE']
    group = next(g for g in dock.findChildren(QGroupBox)
                 if hasattr(g, '_qpansopy_logHandleFilter'))
    handler = group._qpansopy_logHandleFilter
    handle = group._qpansopy_logHandle

    def event(kind, y):
        return QMouseEvent(kind, QPointF(2, 2), QPointF(20, y),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)

    assert handler.eventFilter(handle, event(QEvent.Type.MouseButtonPress, 100))
    start_height = dock.logTextEdit.height()
    assert handler.eventFilter(handle, event(QEvent.Type.MouseMove, 120))
    assert dock.logTextEdit.height() == start_height + 20
    assert handler.eventFilter(handle, event(QEvent.Type.MouseMove, 1000))
    assert dock.logTextEdit.height() == 260
    assert handler.eventFilter(handle, event(QEvent.Type.MouseMove, -1000))
    assert dock.logTextEdit.height() == 60
    assert handler.eventFilter(handle, event(QEvent.Type.MouseButtonRelease, 100))
    assert not handler.eventFilter(handle, event(QEvent.Type.MouseMove, 150))
