import pytest


pytestmark = [pytest.mark.integration, pytest.mark.qgis_runtime]


@pytest.fixture(scope='module')
def qgis_app():
    from qgis.core import QgsApplication

    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


class _Rect:
    def __init__(self, height):
        self._height = height

    def center(self):
        return object()

    def height(self):
        return self._height

    def intersected(self, other):
        return _Rect(min(self._height, other.height()))


class _Screen:
    def __init__(self, available_height):
        self._available_height = available_height

    def availableGeometry(self):
        return _Rect(self._available_height)


class _MainWindow:
    def __init__(self, frame_height, contents_height):
        self._frame = _Rect(frame_height)
        self._contents = _Rect(contents_height)

    def frameGeometry(self):
        return self._frame

    def contentsRect(self):
        return self._contents

    def windowHandle(self):
        return None


def _plugin_for_window(window):
    from Q_Pansopy.qpansopy import Qpansopy

    plugin = object.__new__(Qpansopy)
    plugin.iface = type('Iface', (), {'mainWindow': lambda self: window})()
    return plugin


def test_dock_height_uses_the_qgis_window_on_its_active_screen(
        qgis_app, monkeypatch):
    import Q_Pansopy.qpansopy as plugin_module

    secondary_screen = _Screen(720)
    primary_screen = _Screen(1440)
    gui_application = type('GuiApplication', (), {
        'screenAt': staticmethod(lambda point: secondary_screen),
        'primaryScreen': staticmethod(lambda: primary_screen),
    })
    monkeypatch.setattr(plugin_module, 'QGuiApplication', gui_application)

    plugin = _plugin_for_window(_MainWindow(1000, 920))

    assert plugin._available_dock_height() == 720


@pytest.mark.parametrize(
    ('frame_height', 'contents_height', 'screen_height', 'expected'),
    [
        (768, 700, 1080, 700),
        (1440, 1300, 900, 900),
        (300, 280, 720, 350),
    ],
)
def test_dock_height_respects_window_screen_and_safe_minimum(
        qgis_app, monkeypatch, frame_height, contents_height, screen_height,
        expected):
    import Q_Pansopy.qpansopy as plugin_module

    screen = _Screen(screen_height)
    gui_application = type('GuiApplication', (), {
        'screenAt': staticmethod(lambda point: screen),
        'primaryScreen': staticmethod(lambda: screen),
    })
    monkeypatch.setattr(plugin_module, 'QGuiApplication', gui_application)

    plugin = _plugin_for_window(
        _MainWindow(frame_height, contents_height)
    )

    assert plugin._available_dock_height() == expected
