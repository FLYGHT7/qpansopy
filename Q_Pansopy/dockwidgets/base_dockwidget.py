import pathlib
from PyQt5 import QtWidgets


class BasePansopyDockWidget(QtWidgets.QDockWidget):
    """Base class for all QPANSOPY dockwidgets.

    Centralises: log output, output-path resolution, error display,
    and the three copy-parameters helpers used by most panels.
    Subclasses that override any method must call super() when relevant.
    """

    # ------------------------------------------------------------------ #
    # Log                                                                 #
    # ------------------------------------------------------------------ #

    def log(self, message: str) -> None:
        if hasattr(self, "logTextEdit") and self.logTextEdit is not None:
            self.logTextEdit.append(message)
            self.logTextEdit.ensureCursorVisible()

    # ------------------------------------------------------------------ #
    # Output path                                                         #
    # ------------------------------------------------------------------ #

    def get_output_path(self) -> pathlib.Path:
        from ..utils import get_desktop_path
        return pathlib.Path(get_desktop_path())

    # kept for backward-compat: some widgets call get_desktop_path() -> str
    def get_desktop_path(self) -> str:
        from ..utils import get_desktop_path as _gdp
        return _gdp()

    # ------------------------------------------------------------------ #
    # Error display                                                       #
    # ------------------------------------------------------------------ #

    def show_error(self, message: str) -> None:
        iface = getattr(self, "iface", None)
        if iface is not None:
            try:
                from qgis.core import Qgis
                iface.messageBar().pushMessage("QPANSOPY Error", message, level=Qgis.Critical)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Copy-parameters helpers (no-op stubs; override in subclasses)      #
    # ------------------------------------------------------------------ #

    def copy_parameters_to_clipboard(self) -> None:
        pass

    def copy_parameters_for_word(self) -> None:
        pass

    def copy_parameters_as_json(self) -> None:
        pass
