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
        Qt, QEvent, QVariant, pyqtSignal, QRegularExpression,
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
            Qt, QEvent, pyqtSignal, QRegularExpression,
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
            Qt, QEvent, QVariant, pyqtSignal, QRegularExpression,
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

# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible Qt.ScrollBarPolicy enum values
#
# Qt5: Qt.ScrollBarAsNeeded
# Qt6: Qt.ScrollBarPolicy.ScrollBarAsNeeded
# ---------------------------------------------------------------------------
try:
    _sbp = Qt.ScrollBarPolicy
    Qt_ScrollBarAsNeeded = _sbp.ScrollBarAsNeeded
    Qt_ScrollBarAlwaysOff = _sbp.ScrollBarAlwaysOff
    Qt_ScrollBarAlwaysOn = _sbp.ScrollBarAlwaysOn
except AttributeError:
    Qt_ScrollBarAsNeeded = Qt.ScrollBarAsNeeded   # type: ignore[attr-defined]
    Qt_ScrollBarAlwaysOff = Qt.ScrollBarAlwaysOff # type: ignore[attr-defined]
    Qt_ScrollBarAlwaysOn = Qt.ScrollBarAlwaysOn   # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible Qt.CursorShape enum values
#
# Qt5: Qt.SizeVerCursor
# Qt6: Qt.CursorShape.SizeVerCursor
# ---------------------------------------------------------------------------
try:
    _cs = Qt.CursorShape
    Qt_SizeVerCursor = _cs.SizeVerCursor
    Qt_SizeHorCursor = _cs.SizeHorCursor
    Qt_ArrowCursor = _cs.ArrowCursor
    Qt_PointingHandCursor = _cs.PointingHandCursor
except AttributeError:
    Qt_SizeVerCursor = Qt.SizeVerCursor           # type: ignore[attr-defined]
    Qt_SizeHorCursor = Qt.SizeHorCursor           # type: ignore[attr-defined]
    Qt_ArrowCursor = Qt.ArrowCursor               # type: ignore[attr-defined]
    Qt_PointingHandCursor = Qt.PointingHandCursor # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible Qt.MouseButton enum values
#
# Qt5: Qt.LeftButton
# Qt6: Qt.MouseButton.LeftButton
# ---------------------------------------------------------------------------
try:
    _mb = Qt.MouseButton
    Qt_LeftButton = _mb.LeftButton
    Qt_RightButton = _mb.RightButton
    Qt_MiddleButton = _mb.MiddleButton
except AttributeError:
    Qt_LeftButton = Qt.LeftButton     # type: ignore[attr-defined]
    Qt_RightButton = Qt.RightButton   # type: ignore[attr-defined]
    Qt_MiddleButton = Qt.MiddleButton # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Qt5/Qt6 compatible QEvent.Type enum values
#
# Qt5: QEvent.MouseButtonPress
# Qt6: QEvent.Type.MouseButtonPress
# ---------------------------------------------------------------------------
try:
    _event_type = QEvent.Type
    QEvent_MouseButtonPress = _event_type.MouseButtonPress
    QEvent_MouseMove = _event_type.MouseMove
    QEvent_MouseButtonRelease = _event_type.MouseButtonRelease
    QEvent_Resize = _event_type.Resize
    QEvent_Close = _event_type.Close
    QEvent_Show = _event_type.Show
    QEvent_Hide = _event_type.Hide
except AttributeError:
    QEvent_MouseButtonPress = QEvent.MouseButtonPress       # type: ignore[attr-defined]
    QEvent_MouseMove = QEvent.MouseMove                     # type: ignore[attr-defined]
    QEvent_MouseButtonRelease = QEvent.MouseButtonRelease   # type: ignore[attr-defined]
    QEvent_Resize = QEvent.Resize                           # type: ignore[attr-defined]
    QEvent_Close = QEvent.Close                             # type: ignore[attr-defined]
    QEvent_Show = QEvent.Show                               # type: ignore[attr-defined]
    QEvent_Hide = QEvent.Hide                               # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QGIS 3/4 compatible QgsMapLayerProxyModel filter values
#
# QGIS 3 / PyQt5: QgsMapLayerProxyModel.PointLayer  (unscoped)
# QGIS 4 / PyQt6: QgsMapLayerProxyModel.Filter.PointLayer  (scoped)
# ---------------------------------------------------------------------------
try:
    from qgis.core import QgsMapLayerProxyModel as _QgsMLPM  # noqa: F401
    try:
        _mf = _QgsMLPM.Filter
        MLPM_PointLayer = _mf.PointLayer
        MLPM_LineLayer = _mf.LineLayer
        MLPM_PolygonLayer = _mf.PolygonLayer
        MLPM_VectorLayer = _mf.VectorLayer
        MLPM_RasterLayer = _mf.RasterLayer
        MLPM_NoGeometry = _mf.NoGeometry
        MLPM_All = _mf.All
    except AttributeError:
        MLPM_PointLayer = _QgsMLPM.PointLayer    # type: ignore[attr-defined]
        MLPM_LineLayer = _QgsMLPM.LineLayer       # type: ignore[attr-defined]
        MLPM_PolygonLayer = _QgsMLPM.PolygonLayer # type: ignore[attr-defined]
        MLPM_VectorLayer = _QgsMLPM.VectorLayer   # type: ignore[attr-defined]
        MLPM_RasterLayer = _QgsMLPM.RasterLayer   # type: ignore[attr-defined]
        MLPM_NoGeometry = _QgsMLPM.NoGeometry     # type: ignore[attr-defined]
        MLPM_All = _QgsMLPM.All                   # type: ignore[attr-defined]
except ImportError:
    # Not in QGIS environment — sentinel values
    MLPM_PointLayer = None    # type: ignore[assignment]
    MLPM_LineLayer = None     # type: ignore[assignment]
    MLPM_PolygonLayer = None  # type: ignore[assignment]
    MLPM_VectorLayer = None   # type: ignore[assignment]
    MLPM_RasterLayer = None   # type: ignore[assignment]
    MLPM_NoGeometry = None    # type: ignore[assignment]
    MLPM_All = None           # type: ignore[assignment]

# ---------------------------------------------------------------------------
# QGIS 3/4 compatible geometry type and layer type enum values
#
# QGIS 3: QgsWkbTypes.PointGeometry / QgsWkbTypes.LineGeometry
#         QgsMapLayer.VectorLayer
# QGIS 4: Qgis.GeometryType.Point / Qgis.GeometryType.Line
#         Qgis.LayerType.Vector
# ---------------------------------------------------------------------------
try:
    from qgis.core import (  # noqa: F401
        Qgis as _Qgis,
        QgsWkbTypes as _QgsWkbTypes,
        QgsMapLayer as _QgsMapLayer,
    )
    try:
        _geom_type = _Qgis.GeometryType
        Qgis_GeomType_Point = _geom_type.Point
        Qgis_GeomType_Line = _geom_type.Line
        Qgis_GeomType_Polygon = _geom_type.Polygon
        Qgis_GeomType_Unknown = _geom_type.Unknown
        Qgis_GeomType_Null = _geom_type.Null
    except AttributeError:
        Qgis_GeomType_Point = _QgsWkbTypes.PointGeometry    # type: ignore[attr-defined]
        Qgis_GeomType_Line = _QgsWkbTypes.LineGeometry       # type: ignore[attr-defined]
        Qgis_GeomType_Polygon = _QgsWkbTypes.PolygonGeometry # type: ignore[attr-defined]
        Qgis_GeomType_Unknown = _QgsWkbTypes.UnknownGeometry # type: ignore[attr-defined]
        Qgis_GeomType_Null = _QgsWkbTypes.NullGeometry       # type: ignore[attr-defined]
    try:
        _layer_type = _Qgis.LayerType
        Qgis_LayerType_Vector = _layer_type.Vector
        Qgis_LayerType_Raster = _layer_type.Raster
    except AttributeError:
        Qgis_LayerType_Vector = _QgsMapLayer.VectorLayer  # type: ignore[attr-defined]
        Qgis_LayerType_Raster = _QgsMapLayer.RasterLayer  # type: ignore[attr-defined]
except ImportError:
    Qgis_GeomType_Point = None    # type: ignore[assignment]
    Qgis_GeomType_Line = None     # type: ignore[assignment]
    Qgis_GeomType_Polygon = None  # type: ignore[assignment]
    Qgis_GeomType_Unknown = None  # type: ignore[assignment]
    Qgis_GeomType_Null = None     # type: ignore[assignment]
    Qgis_LayerType_Vector = None  # type: ignore[assignment]
    Qgis_LayerType_Raster = None  # type: ignore[assignment]
