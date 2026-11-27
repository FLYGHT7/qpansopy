# -*- coding: utf-8 -*-
"""Temporary Qt6-only exports for consumers awaiting migration.

Requires QGIS 4 and its qgis.PyQt binding. Import Qt/QGIS directly in
migrated tools; this module is removed after its last consumer migrates.
"""

from qgis.PyQt.QtWidgets import (  # noqa: F401
    QDockWidget,
    QDialog,
    QWidget,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QCheckBox,
    QProgressBar,
    QTextEdit,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QLayout,
    QDialogButtonBox,
)
from qgis.PyQt.QtCore import (  # noqa: F401
    Qt,
    QEvent,
    QVariant,
    pyqtSignal,
    QRegularExpression,
)
from qgis.PyQt.QtGui import (  # noqa: F401
    QIcon,
    QFont,
    QColor,
    QRegularExpressionValidator,
)
from qgis.core import (  # noqa: F401
    QgsMapLayerProxyModel as _QgsMLPM,
)
from qgis.core import (  # noqa: F401
    Qgis as _Qgis,
)
from .utils import preseed_active_layer  # noqa: F401 - transitional re-export

_QT_BACKEND = 'qgis.PyQt'
_dw = QDockWidget.DockWidgetFeature
DOCK_FEATURES_DEFAULT = _dw.DockWidgetMovable | _dw.DockWidgetFloatable | _dw.DockWidgetClosable
QDockWidget_VerticalTitleBar = _dw.DockWidgetVerticalTitleBar
_dwa = Qt.DockWidgetArea
Qt_RightDockWidgetArea = _dwa.RightDockWidgetArea
Qt_LeftDockWidgetArea = _dwa.LeftDockWidgetArea
Qt_TopDockWidgetArea = _dwa.TopDockWidgetArea
Qt_BottomDockWidgetArea = _dwa.BottomDockWidgetArea
Qt_ALLOWED_DOCK_AREAS = Qt_LeftDockWidgetArea | Qt_RightDockWidgetArea
_af = Qt.AlignmentFlag
Qt_AlignTop = _af.AlignTop
Qt_AlignBottom = _af.AlignBottom
Qt_AlignLeft = _af.AlignLeft
Qt_AlignRight = _af.AlignRight
Qt_AlignHCenter = _af.AlignHCenter
Qt_AlignVCenter = _af.AlignVCenter
Qt_AlignCenter = _af.AlignCenter
_ir = QFormLayout.ItemRole
FORM_LABEL_ROLE = _ir.LabelRole
FORM_FIELD_ROLE = _ir.FieldRole
FORM_SPANNING_ROLE = _ir.SpanningRole
_sbp = Qt.ScrollBarPolicy
Qt_ScrollBarAsNeeded = _sbp.ScrollBarAsNeeded
Qt_ScrollBarAlwaysOff = _sbp.ScrollBarAlwaysOff
Qt_ScrollBarAlwaysOn = _sbp.ScrollBarAlwaysOn
_cs = Qt.CursorShape
Qt_SizeVerCursor = _cs.SizeVerCursor
Qt_SizeHorCursor = _cs.SizeHorCursor
Qt_ArrowCursor = _cs.ArrowCursor
Qt_PointingHandCursor = _cs.PointingHandCursor
Qt_WaitCursor = _cs.WaitCursor
_mb = Qt.MouseButton
Qt_LeftButton = _mb.LeftButton
Qt_RightButton = _mb.RightButton
Qt_MiddleButton = _mb.MiddleButton
_event_type = QEvent.Type
QEvent_MouseButtonPress = _event_type.MouseButtonPress
QEvent_MouseMove = _event_type.MouseMove
QEvent_MouseButtonRelease = _event_type.MouseButtonRelease
QEvent_Resize = _event_type.Resize
QEvent_Close = _event_type.Close
QEvent_Show = _event_type.Show
QEvent_Hide = _event_type.Hide
_mf = _QgsMLPM.Filter
MLPM_PointLayer = _mf.PointLayer
MLPM_LineLayer = _mf.LineLayer
MLPM_PolygonLayer = _mf.PolygonLayer
MLPM_VectorLayer = _mf.VectorLayer
MLPM_RasterLayer = _mf.RasterLayer
MLPM_NoGeometry = _mf.NoGeometry
MLPM_All = _mf.All
_geom_type = _Qgis.GeometryType
Qgis_GeomType_Point = _geom_type.Point
Qgis_GeomType_Line = _geom_type.Line
Qgis_GeomType_Polygon = _geom_type.Polygon
Qgis_GeomType_Unknown = _geom_type.Unknown
Qgis_GeomType_Null = _geom_type.Null
_layer_type = _Qgis.LayerType
Qgis_LayerType_Vector = _layer_type.Vector
Qgis_LayerType_Raster = _layer_type.Raster
_fs = QFrame.Shape
QFrame_NoFrame = _fs.NoFrame
QFrame_StyledPanel = _fs.StyledPanel
QFrame_HLine = _fs.HLine
QFrame_VLine = _fs.VLine
_spp = QSizePolicy.Policy
QSizePolicy_Fixed = _spp.Fixed
QSizePolicy_Minimum = _spp.Minimum
QSizePolicy_Maximum = _spp.Maximum
QSizePolicy_Preferred = _spp.Preferred
QSizePolicy_Expanding = _spp.Expanding
QSizePolicy_MinimumExpanding = _spp.MinimumExpanding
QSizePolicy_Ignored = _spp.Ignored
_fgp = QFormLayout.FieldGrowthPolicy
QFormLayout_AllNonFixedFieldsGrow = _fgp.AllNonFixedFieldsGrow
QFormLayout_FieldsStayAtSizeHint = _fgp.FieldsStayAtSizeHint
QFormLayout_ExpandingFieldsGrow = _fgp.ExpandingFieldsGrow
_dbb = QDialogButtonBox.StandardButton
QDialogButtonBox_Ok = _dbb.Ok
QDialogButtonBox_Cancel = _dbb.Cancel
_lwm = QTextEdit.LineWrapMode
QTextEdit_WidgetWidth = _lwm.WidgetWidth
QTextEdit_NoWrap = _lwm.NoWrap
QTextEdit_FixedPixelWidth = _lwm.FixedPixelWidth
QTextEdit_FixedColumnWidth = _lwm.FixedColumnWidth
_lsc = QLayout.SizeConstraint
QLayout_SetDefaultConstraint = _lsc.SetDefaultConstraint
QLayout_SetMinimumSize = _lsc.SetMinimumSize
QLayout_SetFixedSize = _lsc.SetFixedSize
QLayout_SetMaximumSize = _lsc.SetMaximumSize
QLayout_SetMinAndMaxSize = _lsc.SetMinAndMaxSize
QLayout_SetNoConstraint = _lsc.SetNoConstraint
_orient = Qt.Orientation
Qt_Vertical = _orient.Vertical
Qt_Horizontal = _orient.Horizontal


def get_qt_backend() -> str:
    """Return the QGIS-provided Qt binding name."""
    return _QT_BACKEND
