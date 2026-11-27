"""The lightweight harness exposes scoped Qt6 APIs and restores module state."""
import sys
import types

from tests.conftest import _install_qgis_stubs


def test_scoped_qt6_enums_are_available_without_a_pyqt5_backend():
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import Qt, QMetaType, QT_VERSION_STR

    assert Qgis.QGIS_VERSION_INT >= 40000
    assert QT_VERSION_STR.startswith('6.')
    assert Qgis.MessageLevel.Info != Qgis.MessageLevel.Success
    assert Qgis.GeometryType.Line != Qgis.GeometryType.Point
    assert Qt.Orientation.Horizontal != Qt.Orientation.Vertical
    flags = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    assert flags & Qt.AlignmentFlag.AlignRight
    assert QMetaType.Type.QString != QMetaType.Type.Double
    assert 'PyQt5' not in sys.modules


def test_nested_stubs_restore_optional_modules(monkeypatch):
    names = ('qgis.PyQt.uic', 'qgis.PyQt.QtWebEngineWidgets',
             'qgis.PyQt.QtWebChannel')
    originals = {name: types.ModuleType(name) for name in names}
    for name, module in originals.items():
        monkeypatch.setitem(sys.modules, name, module)
    with _install_qgis_stubs():
        assert all(sys.modules[name] is not module
                   for name, module in originals.items())
    assert all(sys.modules[name] is module for name, module in originals.items())
