import pathlib
from qgis.PyQt import QtWidgets


def _load_base_qss() -> str:
    """Return the content of dockwidget_base.qss, empty string on error."""
    qss_path = pathlib.Path(__file__).parent.parent / "styles" / "dockwidget_base.qss"
    try:
        return qss_path.read_text(encoding="utf-8")
    except OSError:
        return ""


class BasePansopyDockWidget(QtWidgets.QDockWidget):
    """Base class for all QPANSOPY dockwidgets.

    Centralises: QSS loading, log output, output-path resolution,
    error display, progress feedback, and copy-parameters stubs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet(_load_base_qss())

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

    # backward-compat: widgets call get_desktop_path() -> str
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
    # Calculation feedback                                                #
    # ------------------------------------------------------------------ #

    def _run_with_feedback(self, calc_fn) -> None:
        """Disable the calculate button and show an indeterminate progress
        bar while *calc_fn* runs, then restore the UI state.

        Usage in a subclass::

            def calculate(self):
                self._run_with_feedback(self._do_calculate)

            def _do_calculate(self):
                ...
        """
        btn = getattr(self, "calculateButton", None)
        pbar = getattr(self, "progressBar", None)

        if btn is not None:
            btn.setEnabled(False)
        if pbar is not None:
            pbar.setRange(0, 0)  # indeterminate spinner

        try:
            calc_fn()
        finally:
            if btn is not None:
                btn.setEnabled(True)
            if pbar is not None:
                pbar.setRange(0, 1)
                pbar.setValue(1)

    # ------------------------------------------------------------------ #
    # Copy-parameters helpers (no-op stubs; override in subclasses)      #
    # ------------------------------------------------------------------ #

    def copy_parameters_to_clipboard(self) -> None:
        pass

    def copy_parameters_for_word(self) -> None:
        pass

    def copy_parameters_as_json(self) -> None:
        pass

