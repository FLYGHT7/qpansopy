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
    qtcore.QVariant = object
    qtgui.QColor = object

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
        (utils, 'qgis.utils'),
    ]:
        if name in sys.modules:
            to_restore[name] = sys.modules[name]
        sys.modules[name] = mod
    try:
        yield
    finally:
        # Restore prior modules if any, else remove our stubs
        for name in ['qgis.PyQt.QtCore', 'qgis.PyQt.QtGui', 'qgis.PyQt', 'qgis.core', 'qgis.utils', 'qgis']:
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