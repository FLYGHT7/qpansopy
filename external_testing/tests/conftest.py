import sys
import types
import contextlib


@contextlib.contextmanager
def _install_qgis_stubs():
    qgis = types.ModuleType('qgis')

    core = types.ModuleType('qgis.core')
    # Minimal dummies for imported names
    class _Dummy:  # noqa: N801
        pass

    # Commonly imported symbols in modules
    for name in [
        'QgsProject', 'QgsVectorLayer', 'QgsFeature', 'QgsGeometry',
        'QgsCoordinateReferenceSystem', 'QgsCoordinateTransform', 'QgsPointXY',
        'QgsWkbTypes', 'QgsField', 'QgsFields', 'QgsPoint', 'QgsLineString',
        'QgsPolygon', 'QgsVectorFileWriter', 'QgsCircularString'
    ]:
        setattr(core, name, _Dummy)

    # Qgis enum-like container
    core.Qgis = type('Qgis', (), {
        'Success': 0,
        'Info': 1,
        'Warning': 2,
        'Critical': 3,
        'NoError': 0,
    })

    # qgis.PyQt stubs
    PyQt = types.ModuleType('qgis.PyQt')
    qtcore = types.ModuleType('qgis.PyQt.QtCore')
    qtgui = types.ModuleType('qgis.PyQt.QtGui')
    qtwidgets = types.ModuleType('qgis.PyQt.QtWidgets')
    qtcore.QVariant = object
    qtcore.Qt = object
    qtgui.QColor = object
    for widget_name in [
        'QFileDialog', 'QDialog', 'QFormLayout', 'QLineEdit', 'QComboBox',
        'QDialogButtonBox', 'QMessageBox', 'QWidget', 'QApplication',
    ]:
        setattr(qtwidgets, widget_name, _Dummy)

    # PyQt5 stubs (some modules import PyQt5 directly)
    pyqt5 = types.ModuleType('PyQt5')
    pyqt5_qtcore = types.ModuleType('PyQt5.QtCore')
    pyqt5_qtgui = types.ModuleType('PyQt5.QtGui')
    pyqt5_qtwidgets = types.ModuleType('PyQt5.QtWidgets')
    pyqt5_qtcore.QVariant = object
    pyqt5_qtcore.Qt = object
    pyqt5_qtgui.QColor = object
    for widget_name in [
        'QFileDialog', 'QDialog', 'QFormLayout', 'QLineEdit', 'QComboBox',
        'QDialogButtonBox', 'QMessageBox', 'QWidget', 'QApplication',
    ]:
        setattr(pyqt5_qtwidgets, widget_name, _Dummy)

    # qgis.utils stub
    utils = types.ModuleType('qgis.utils')
    utils.iface = object()

    # Register in sys.modules
    to_restore = {}
    for mod, name in [
        (qgis, 'qgis'),
        (core, 'qgis.core'),
        (PyQt, 'qgis.PyQt'),
        (qtcore, 'qgis.PyQt.QtCore'),
        (qtgui, 'qgis.PyQt.QtGui'),
        (qtwidgets, 'qgis.PyQt.QtWidgets'),
        (utils, 'qgis.utils'),
        (pyqt5, 'PyQt5'),
        (pyqt5_qtcore, 'PyQt5.QtCore'),
        (pyqt5_qtgui, 'PyQt5.QtGui'),
        (pyqt5_qtwidgets, 'PyQt5.QtWidgets'),
    ]:
        if name in sys.modules:
            to_restore[name] = sys.modules[name]
        sys.modules[name] = mod
    try:
        yield
    finally:
        # Restore prior modules if any, else remove our stubs
        for name in ['PyQt5.QtWidgets', 'PyQt5.QtGui', 'PyQt5.QtCore', 'PyQt5',
                     'qgis.PyQt.QtWidgets', 'qgis.PyQt.QtCore', 'qgis.PyQt.QtGui',
                     'qgis.PyQt', 'qgis.core', 'qgis.utils', 'qgis']:
            if name in to_restore:
                sys.modules[name] = to_restore[name]
            elif name in sys.modules:
                del sys.modules[name]


def pytest_runtest_setup(item):
    # Ensure qgis stubs are available for tests that import plugin modules
    item._qgis_stub_ctx = _install_qgis_stubs()
    item._qgis_stub_ctx.__enter__()


def pytest_runtest_teardown(item, nextitem):
    # Tear down stubs after each test
    ctx = getattr(item, '_qgis_stub_ctx', None)
    if ctx is not None:
        ctx.__exit__(None, None, None)