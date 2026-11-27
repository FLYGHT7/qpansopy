"""Runtime rejection happens before plugin imports; preseeding stays best effort."""
import builtins
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('qgis_version,qt_version,pyqt_version,accepted', [
    (40000, '6.0.0', '6.0.0', True),
    (40203, '6.12.0', '6.12.0', True),
    (33400, '6.12.0', '6.12.0', False),
    (40203, '5.15.0', '5.15.0', False),
    (40203, '6.12.0', '5.15.0', False),
    (50000, '6.12.0', '6.12.0', False),
])
def test_class_factory_checks_runtime_before_importing_plugin(
        monkeypatch, qgis_version, qt_version, pyqt_version, accepted):
    from qgis.core import Qgis
    from qgis.PyQt import QtCore

    monkeypatch.setattr(Qgis, 'QGIS_VERSION_INT', qgis_version)
    monkeypatch.setattr(QtCore, 'QT_VERSION_STR', qt_version)
    monkeypatch.setattr(QtCore, 'PYQT_VERSION_STR', pyqt_version)
    path = Path(__file__).resolve().parents[2] / 'Q_Pansopy/__init__.py'
    spec = importlib.util.spec_from_file_location('isolated_entrypoint', path)
    entrypoint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entrypoint)
    original_import = builtins.__import__
    imports = []
    iface = object()

    def traced_import(name, *args, **kwargs):
        if name == 'qpansopy':
            imports.append(name)
            return SimpleNamespace(Qpansopy=lambda supplied: ('plugin', supplied))
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', traced_import)
    if accepted:
        assert entrypoint.classFactory(iface) == ('plugin', iface)
        assert imports == ['qpansopy']
    else:
        with pytest.raises(RuntimeError, match='QGIS 4.*Qt6.*PyQt6'):
            entrypoint.classFactory(iface)
        assert imports == []


@pytest.mark.parametrize('kind', ['match', 'mismatch', 'none', 'nonvector', 'error'])
def test_active_layer_preselection_preserves_best_effort_behavior(monkeypatch, kind):
    import qgis.core as core
    from Q_Pansopy.utils import preseed_active_layer

    class VectorLayer:
        def geometryType(self):
            return 1 if kind == 'match' else 0

    monkeypatch.setattr(core, 'QgsVectorLayer', VectorLayer)
    layer = None if kind == 'none' else object() if kind == 'nonvector' else VectorLayer()

    def active_layer():
        if kind == 'error':
            raise RuntimeError('Interface unavailable')
        return layer

    selected = []
    preseed_active_layer(SimpleNamespace(activeLayer=active_layer),
                         SimpleNamespace(setLayer=selected.append), 1)
    assert selected == ([layer] if kind == 'match' else [])
