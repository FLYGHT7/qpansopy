import json
import pathlib
import sys
import types
import contextlib
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
        # Renderers & symbols
        'QgsRuleBasedRenderer', 'QgsFillSymbol', 'QgsSymbol',
        'QgsCategorizedSymbolRenderer', 'QgsRendererCategory',
        'QgsSimpleFillSymbolLayer',
        # Map layer
        'QgsMapLayerProxyModel', 'QgsMapLayerComboBox',
        # Additional geometry/query classes
        'QgsRectangle', 'QgsFeatureRequest', 'QgsSpatialIndex',
        'QgsLayerTreeGroup', 'QgsLayerTreeLayer',
        # Symbol layers
        'QgsSimpleMarkerSymbolLayer', 'QgsMarkerSymbol',
    ]:
        setattr(core, name, _Dummy)

    core.Qgis = type('Qgis', (), {
        'Success': 0, 'Info': 1, 'Warning': 2, 'Critical': 3, 'NoError': 0,
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
        'Horizontal': 1, 'Vertical': 2, 'AlignLeft': 1,
    })
    qtcore.QMetaType = type('QMetaType', (), {
        'Type': type('Type', (), {
            'Double': 6, 'QString': 10, 'Int': 2, 'Bool': 1,
        }),
        'Double': 6, 'QString': 10, 'Int': 2,
    })
    qtcore.pyqtSignal = lambda *a, **kw: None
    qtgui.QColor = _Dummy

    # uic stub — needed by dockwidget modules that call uic.loadUiType()
    uic = types.ModuleType('qgis.PyQt.uic')
    uic.loadUiType = lambda *a, **kw: (_Dummy, None)
    PyQt.uic = uic
    sys.modules['qgis.PyQt.uic'] = uic

    for widget_name in [
        'QFileDialog', 'QDialog', 'QFormLayout', 'QLineEdit', 'QComboBox',
        'QDialogButtonBox', 'QMessageBox', 'QWidget', 'QApplication',
        'QDockWidget', 'QPushButton', 'QTextEdit', 'QGroupBox', 'QVBoxLayout',
    ]:
        setattr(qtwidgets, widget_name, _Dummy)

    # PyQt5 stubs (some modules import PyQt5 directly)
    pyqt5 = types.ModuleType('PyQt5')
    pyqt5_qtcore = types.ModuleType('PyQt5.QtCore')
    pyqt5_qtgui = types.ModuleType('PyQt5.QtGui')
    pyqt5_qtwidgets = types.ModuleType('PyQt5.QtWidgets')
    pyqt5_qtcore.QVariant = _QVariant
    pyqt5_qtcore.Qt = qtcore.Qt
    pyqt5_qtcore.QMetaType = qtcore.QMetaType
    pyqt5_qtcore.pyqtSignal = lambda *a, **kw: None
    pyqt5_qtgui.QColor = _Dummy
    for widget_name in [
        'QFileDialog', 'QDialog', 'QFormLayout', 'QLineEdit', 'QComboBox',
        'QDialogButtonBox', 'QMessageBox', 'QWidget', 'QApplication',
        'QDockWidget', 'QPushButton', 'QTextEdit', 'QGroupBox', 'QVBoxLayout',
    ]:
        setattr(pyqt5_qtwidgets, widget_name, _Dummy)

    # qgis.gui stub — some conv modules do `from qgis.gui import *`
    gui = types.ModuleType('qgis.gui')
    gui.__all__ = []

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
        (utils,           'qgis.utils'),
        (pyqt5,           'PyQt5'),
        (pyqt5_qtcore,    'PyQt5.QtCore'),
        (pyqt5_qtgui,     'PyQt5.QtGui'),
        (pyqt5_qtwidgets, 'PyQt5.QtWidgets'),
    ]:
        if name in sys.modules:
            to_restore[name] = sys.modules[name]
        sys.modules[name] = mod
    try:
        yield
    finally:
        names_to_clean = [
            'PyQt5.QtWidgets', 'PyQt5.QtGui', 'PyQt5.QtCore', 'PyQt5',
            'qgis.PyQt.uic', 'qgis.PyQt.QtWidgets', 'qgis.PyQt.QtCore',
            'qgis.PyQt.QtGui', 'qgis.PyQt', 'qgis.gui', 'qgis.core', 'qgis.utils', 'qgis',
        ]
        for name in names_to_clean:
            if name in to_restore:
                sys.modules[name] = to_restore[name]
            elif name in sys.modules:
                del sys.modules[name]


def pytest_runtest_setup(item):
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
