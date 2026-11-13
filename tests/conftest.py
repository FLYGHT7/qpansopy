import json
import pathlib
import sys
import types
import contextlib
from enum import IntEnum, IntFlag
import pytest

# Ensure the project root is on sys.path so tests can import Q_Pansopy modules
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_FIXTURES_DIR = pathlib.Path(__file__).parent / 'fixtures' / 'json'


@contextlib.contextmanager
def _install_qgis_stubs():
    qgis = types.ModuleType('qgis')

    core = types.ModuleType('qgis.core')

    class _Dummy:
        def __init__(self, *a, **kw): pass
        def __call__(self, *a, **kw): return self
        def __getattr__(self, name): return _Dummy()

    for name in [
        # Geometry & CRS
        'QgsProject', 'QgsVectorLayer', 'QgsFeature', 'QgsGeometry',
        'QgsCoordinateReferenceSystem', 'QgsCoordinateTransform', 'QgsPointXY',
        'QgsWkbTypes', 'QgsField', 'QgsFields', 'QgsPoint', 'QgsLineString',
        'QgsPolygon', 'QgsVectorFileWriter', 'QgsCircularString',
        'QgsFeatureSink', 'QgsMemoryProviderUtils',
        # Renderers & symbols
        'QgsRuleBasedRenderer', 'QgsFillSymbol', 'QgsSymbol',
        'QgsCategorizedSymbolRenderer', 'QgsRendererCategory',
        'QgsSimpleFillSymbolLayer',
        # Map layer
        'QgsMapLayerProxyModel', 'QgsMapLayerComboBox', 'QgsAction',
        # Additional geometry/query classes
        'QgsRectangle', 'QgsFeatureRequest', 'QgsSpatialIndex',
        'QgsLayerTreeGroup', 'QgsLayerTreeLayer',
        'QgsLayerNotesUtils',
        # Symbol layers
        'QgsSimpleMarkerSymbolLayer', 'QgsMarkerSymbol',
        'QgsPalLayerSettings', 'QgsVectorLayerSimpleLabeling',
    ]:
        setattr(core, name, _Dummy)

    # Scoped Qt6/QGIS4 enums; flat aliases remain only for pending consumers.
    message_levels = IntEnum('MessageLevel', {'Info': 0, 'Warning': 1,
                                             'Critical': 2, 'Success': 3})
    core.Qgis = type('Qgis', (), {
        'QGIS_VERSION_INT': 40203, 'MessageLevel': message_levels,
        'GeometryType': IntEnum('GeometryType', {'Point': 0, 'Line': 1,
            'Polygon': 2, 'Unknown': 3, 'Null': 4}),
        'LayerType': IntEnum('LayerType', {'Vector': 0, 'Raster': 1}),
        'DistanceUnit': IntEnum('DistanceUnit', {'Meters': 0}),
        **message_levels.__members__, 'NoError': 0,
    })

    # qgis.PyQt stubs
    PyQt = types.ModuleType('qgis.PyQt')
    qtcore = types.ModuleType('qgis.PyQt.QtCore')
    qtgui = types.ModuleType('qgis.PyQt.QtGui')
    qtwidgets = types.ModuleType('qgis.PyQt.QtWidgets')
    _QVariant = type('QVariant', (), {
        'String': 10, 'Double': 6, 'Int': 2, 'Bool': 1, 'LongLong': 4,
        'StringList': 11, 'Invalid': 0,
    })
    qtcore.QVariant = _QVariant
    qtcore.Qt = type('Qt', (), {
        'Orientation': IntEnum('Orientation', {'Horizontal': 1, 'Vertical': 2}),
        'AlignmentFlag': IntFlag('AlignmentFlag', {'AlignLeft': 1,
            'AlignRight': 2, 'AlignHCenter': 4, 'AlignTop': 32,
            'AlignBottom': 64, 'AlignVCenter': 128, 'AlignCenter': 132}),
        'PenStyle': IntEnum('PenStyle', {'NoPen': 0, 'SolidLine': 1}),
        'Horizontal': 1, 'Vertical': 2, 'AlignLeft': 1,
    })
    qtcore.QMetaType = type('QMetaType', (), {
        'Type': type('Type', (), {
            'Double': 6, 'QString': 10, 'Int': 2, 'Bool': 1, 'LongLong': 4,
        }),
        'Double': 6, 'QString': 10, 'Int': 2,
    })
    qtcore.QT_VERSION_STR = '6.12.0'
    qtcore.PYQT_VERSION_STR = '6.12.0'
    qtcore.pyqtSignal = lambda *a, **kw: None
    qtcore.pyqtSlot = lambda *a, **kw: (lambda fn: fn)
    qtcore.QObject = _Dummy
    qtcore.QMimeData = _Dummy
    qtgui.QColor = _Dummy

    # uic stub — needed by dockwidget modules that call uic.loadUiType()
    uic = types.ModuleType('qgis.PyQt.uic')
    uic.loadUiType = lambda *a, **kw: (_Dummy, None)
    PyQt.uic = uic

    # QtWebEngineWidgets / QtWebChannel stubs — needed by parameters_inspector_dialog.py
    webengine = types.ModuleType('qgis.PyQt.QtWebEngineWidgets')
    webengine.QWebEngineView = _Dummy

    webchannel = types.ModuleType('qgis.PyQt.QtWebChannel')
    webchannel.QWebChannel = _Dummy

    for widget_name in [
        'QFileDialog', 'QDialog', 'QFormLayout', 'QLineEdit', 'QComboBox',
        'QDialogButtonBox', 'QMessageBox', 'QWidget', 'QApplication',
        'QDockWidget', 'QPushButton', 'QTextEdit', 'QGroupBox', 'QVBoxLayout',
        'QHBoxLayout', 'QTextBrowser', 'QLabel',
    ]:
        setattr(qtwidgets, widget_name, _Dummy)

    # qgis.gui stub — some conv modules do `from qgis.gui import *`
    gui = types.ModuleType('qgis.gui')
    gui.__all__ = []
    gui.QgsRubberBand = _Dummy

    utils = types.ModuleType('qgis.utils')
    utils.iface = object()

    to_restore = {}
    for mod, name in [
        (qgis,            'qgis'),
        (core,            'qgis.core'),
        (gui,             'qgis.gui'),
        (PyQt,            'qgis.PyQt'),
        (qtcore,          'qgis.PyQt.QtCore'),
        (qtgui,           'qgis.PyQt.QtGui'),
        (qtwidgets,       'qgis.PyQt.QtWidgets'),
        (uic,             'qgis.PyQt.uic'),
        (webengine,       'qgis.PyQt.QtWebEngineWidgets'),
        (webchannel,      'qgis.PyQt.QtWebChannel'),
        (utils,           'qgis.utils'),
    ]:
        if name in sys.modules:
            to_restore[name] = sys.modules[name]
        sys.modules[name] = mod
    try:
        yield
    finally:
        names_to_clean = [
            'qgis.PyQt.uic', 'qgis.PyQt.QtWebEngineWidgets', 'qgis.PyQt.QtWebChannel',
            'qgis.PyQt.QtWidgets', 'qgis.PyQt.QtCore',
            'qgis.PyQt.QtGui', 'qgis.PyQt', 'qgis.gui', 'qgis.core', 'qgis.utils', 'qgis',
        ]
        for name in names_to_clean:
            if name in to_restore:
                sys.modules[name] = to_restore[name]
            elif name in sys.modules:
                del sys.modules[name]


def pytest_runtest_setup(item):
    if item.get_closest_marker('qgis_runtime'):
        item._qgis_stub_ctx = None
        return
    item._qgis_stub_ctx = _install_qgis_stubs()
    item._qgis_stub_ctx.__enter__()


def pytest_runtest_teardown(item, nextitem):
    ctx = getattr(item, '_qgis_stub_ctx', None)
    if ctx is not None:
        ctx.__exit__(None, None, None)


@pytest.fixture
def load_cases():
    """Load parametrized test cases from a JSON fixture file in tests/fixtures/json/."""
    def _load(filename: str) -> list:
        path = _FIXTURES_DIR / filename
        return json.loads(path.read_text(encoding='utf-8'))
    return _load
