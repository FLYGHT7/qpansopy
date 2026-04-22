# -*- coding: utf-8 -*-
"""
Qt compatibility shim for QPANSOPY.

Provides a single import point for Qt symbols that works in three environments:

1. Inside QGIS 3.x / 4.x  — uses the ``qgis.PyQt`` wrapper (preferred).
2. Standalone with PyQt6   — uses PyQt6 directly.
3. Standalone with PyQt5   — uses PyQt5 directly (legacy).

Usage in new code (outside a running QGIS session)::

    from Q_Pansopy.qt_compat import (
        QDockWidget, QDialog, QWidget,
        QLabel, QLineEdit, QComboBox,
        QPushButton, QGroupBox, QFileDialog, QMessageBox,
        Qt, QVariant, pyqtSignal,
        QIcon, QFont, QColor,
        QRegularExpression, QRegularExpressionValidator,
    )

Note:
    Files that already run inside QGIS should continue to use
    ``from qgis.PyQt import ...`` directly — that is always available
    and requires no fallback logic.
"""

try:
    # ── QGIS environment (QGIS 3.34 LTR and QGIS 4 / Qt6) ───────────
    from qgis.PyQt.QtWidgets import (  # noqa: F401
        QDockWidget, QDialog, QWidget,
        QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
        QPushButton, QGroupBox, QFileDialog, QMessageBox,
        QHBoxLayout, QVBoxLayout, QFormLayout,
        QCheckBox, QProgressBar, QTextEdit, QScrollArea,
    )
    from qgis.PyQt.QtCore import (  # noqa: F401
        Qt, QVariant, pyqtSignal, QRegularExpression,
    )
    from qgis.PyQt.QtGui import (  # noqa: F401
        QIcon, QFont, QColor,
        QRegularExpressionValidator,
    )

    _QT_BACKEND = "qgis.PyQt"

except ImportError:
    try:
        # ── Standalone PyQt6 ─────────────────────────────────────────
        from PyQt6.QtWidgets import (  # noqa: F401
            QDockWidget, QDialog, QWidget,
            QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
            QPushButton, QGroupBox, QFileDialog, QMessageBox,
            QHBoxLayout, QVBoxLayout, QFormLayout,
            QCheckBox, QProgressBar, QTextEdit, QScrollArea,
        )
        from PyQt6.QtCore import (  # noqa: F401
            Qt, pyqtSignal, QRegularExpression,
        )
        from PyQt6.QtGui import (  # noqa: F401
            QIcon, QFont, QColor,
            QRegularExpressionValidator,
        )

        # PyQt6 has no QVariant — provide a minimal stub so code that
        # uses QVariant.Int / QVariant.String etc. does not crash.
        class QVariant:  # noqa: N801
            """Minimal QVariant stub for PyQt6 compatibility."""
            Int = 2
            Double = 6
            String = 10
            Bool = 1
            LongLong = 4
            Date = 14
            DateTime = 16
            Invalid = 0

        _QT_BACKEND = "PyQt6"

    except ImportError:
        # ── Standalone PyQt5 (legacy) ─────────────────────────────────
        from PyQt5.QtWidgets import (  # noqa: F401
            QDockWidget, QDialog, QWidget,
            QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
            QPushButton, QGroupBox, QFileDialog, QMessageBox,
            QHBoxLayout, QVBoxLayout, QFormLayout,
            QCheckBox, QProgressBar, QTextEdit, QScrollArea,
        )
        from PyQt5.QtCore import (  # noqa: F401
            Qt, QVariant, pyqtSignal, QRegularExpression,
        )
        from PyQt5.QtGui import (  # noqa: F401
            QIcon, QFont, QColor,
            QRegularExpressionValidator,
        )

        _QT_BACKEND = "PyQt5"


def get_qt_backend() -> str:
    """Return the name of the active Qt backend (``'qgis.PyQt'``, ``'PyQt6'``, or ``'PyQt5'``)."""
    return _QT_BACKEND


# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible QDockWidget feature flags
#
# Qt5 / PyQt5: enums are unscoped  → QDockWidget.DockWidgetMovable
# Qt6 / PyQt6: enums are scoped    → QDockWidget.DockWidgetFeature.DockWidgetMovable
# ---------------------------------------------------------------------------
try:
    _dw = QDockWidget.DockWidgetFeature  # Qt6 scoped enum namespace
    DOCK_FEATURES_DEFAULT = (
        _dw.DockWidgetMovable | _dw.DockWidgetFloatable | _dw.DockWidgetClosable
    )
except AttributeError:
    DOCK_FEATURES_DEFAULT = (           # type: ignore[assignment]
        QDockWidget.DockWidgetMovable   # type: ignore[attr-defined]
        | QDockWidget.DockWidgetFloatable   # type: ignore[attr-defined]
        | QDockWidget.DockWidgetClosable    # type: ignore[attr-defined]
    )

# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible Qt.DockWidgetArea enum values
#
# Qt5: Qt.RightDockWidgetArea
# Qt6: Qt.DockWidgetArea.RightDockWidgetArea
# ---------------------------------------------------------------------------
try:
    _dwa = Qt.DockWidgetArea
    Qt_RightDockWidgetArea = _dwa.RightDockWidgetArea
    Qt_LeftDockWidgetArea = _dwa.LeftDockWidgetArea
    Qt_TopDockWidgetArea = _dwa.TopDockWidgetArea
    Qt_BottomDockWidgetArea = _dwa.BottomDockWidgetArea
except AttributeError:
    Qt_RightDockWidgetArea = Qt.RightDockWidgetArea   # type: ignore[attr-defined]
    Qt_LeftDockWidgetArea = Qt.LeftDockWidgetArea     # type: ignore[attr-defined]
    Qt_TopDockWidgetArea = Qt.TopDockWidgetArea       # type: ignore[attr-defined]
    Qt_BottomDockWidgetArea = Qt.BottomDockWidgetArea # type: ignore[attr-defined]

Qt_ALLOWED_DOCK_AREAS = Qt_LeftDockWidgetArea | Qt_RightDockWidgetArea

# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible Qt.AlignmentFlag enum values
#
# Qt5: Qt.AlignTop
# Qt6: Qt.AlignmentFlag.AlignTop
# ---------------------------------------------------------------------------
try:
    _af = Qt.AlignmentFlag
    Qt_AlignTop = _af.AlignTop
    Qt_AlignBottom = _af.AlignBottom
    Qt_AlignLeft = _af.AlignLeft
    Qt_AlignRight = _af.AlignRight
    Qt_AlignHCenter = _af.AlignHCenter
    Qt_AlignVCenter = _af.AlignVCenter
    Qt_AlignCenter = _af.AlignCenter
except AttributeError:
    Qt_AlignTop = Qt.AlignTop           # type: ignore[attr-defined]
    Qt_AlignBottom = Qt.AlignBottom     # type: ignore[attr-defined]
    Qt_AlignLeft = Qt.AlignLeft         # type: ignore[attr-defined]
    Qt_AlignRight = Qt.AlignRight       # type: ignore[attr-defined]
    Qt_AlignHCenter = Qt.AlignHCenter   # type: ignore[attr-defined]
    Qt_AlignVCenter = Qt.AlignVCenter   # type: ignore[attr-defined]
    Qt_AlignCenter = Qt.AlignCenter     # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible QFormLayout ItemRole enum values
#
# Qt5: QFormLayout.FieldRole
# Qt6: QFormLayout.ItemRole.FieldRole
# ---------------------------------------------------------------------------
try:
    _ir = QFormLayout.ItemRole
    FORM_LABEL_ROLE = _ir.LabelRole
    FORM_FIELD_ROLE = _ir.FieldRole
    FORM_SPANNING_ROLE = _ir.SpanningRole
except AttributeError:
    FORM_LABEL_ROLE = QFormLayout.LabelRole     # type: ignore[attr-defined]
    FORM_FIELD_ROLE = QFormLayout.FieldRole     # type: ignore[attr-defined]
    FORM_SPANNING_ROLE = QFormLayout.SpanningRole  # type: ignore[attr-defined]
