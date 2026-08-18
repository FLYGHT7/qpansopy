# -*- coding: utf-8 -*-
import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsRubberBand
from qgis.core import (
    QgsProject, QgsDistanceArea, QgsCoordinateTransform, Qgis,
)
from ...modules.conv.dme_tolerance import build_tolerance_geometry
from ...qt_compat import (
    MLPM_PointLayer,
    preseed_active_layer, Qgis_GeomType_Point, Qgis_GeomType_Polygon,
)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv',
    'qpansopy_dme_tolerance_dockwidget.ui'))


class QPANSOPYDMEToleranceDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """
    Dockwidget for the VOR/DME, NDB/DME, and LOC/DME fix tolerance tools.
    Tolerance type is picked via toleranceTypeComboBox (issue #181 follow-up)
    instead of separate dockwidget subclasses/instances, so switching type
    keeps the selected layers and live preview instead of losing them.
    """

    closingPlugin = pyqtSignal()

    # (nav_type, default_rotate, point_layer_label)
    _TOLERANCE_TYPES = [
        ('VOR/DME', 5.2, 'DME Point Layer'),
        ('NDB/DME', 6.9, 'NDB Point Layer'),
        ('LOC/DME', 2.4, 'LOC Point Layer'),
    ]

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        for nav_type, default_rotate, point_layer_label in self._TOLERANCE_TYPES:
            self.toleranceTypeComboBox.addItem(nav_type, (default_rotate, point_layer_label))
        self.toleranceTypeComboBox.currentIndexChanged.connect(self._on_tolerance_type_changed)

        self.pointLayerComboBox.setFilters(MLPM_PointLayer)
        self.fixLayerComboBox.setFilters(MLPM_PointLayer)
        preseed_active_layer(iface, self.pointLayerComboBox, Qgis_GeomType_Point)
        preseed_active_layer(iface, self.fixLayerComboBox, Qgis_GeomType_Point)

        self.calculateButton.clicked.connect(self.calculate)

        # Live preview rubber band
        self._preview_band = QgsRubberBand(iface.mapCanvas(), Qgis_GeomType_Polygon)
        self._preview_band.setColor(QColor(0, 100, 255, 80))
        self._preview_band.setStrokeColor(QColor(0, 100, 255, 200))
        self._preview_band.setWidth(1)
        self._connected_layers = []

        self.pointLayerComboBox.layerChanged.connect(self._on_layer_changed)
        self.fixLayerComboBox.layerChanged.connect(self._on_layer_changed)
        self.rotateDoubleSpinBox.valueChanged.connect(self._update_preview)

        self._on_tolerance_type_changed()
        self._on_layer_changed()

    def _on_tolerance_type_changed(self, *args):
        default_rotate, point_layer_label = self.toleranceTypeComboBox.currentData()
        self.pointLayerLabel.setText(point_layer_label)
        self.rotateDoubleSpinBox.setValue(default_rotate)

    def closeEvent(self, event):
        self._clear_preview()
        self.closingPlugin.emit()
        event.accept()

    def _on_layer_changed(self):
        for lyr in self._connected_layers:
            try:
                lyr.selectionChanged.disconnect(self._update_preview)
            except Exception:  # nosec B110 - signal may already be disconnected; safe to ignore
                pass
        self._connected_layers = []

        seen = set()
        for combo in [self.pointLayerComboBox, self.fixLayerComboBox]:
            lyr = combo.currentLayer()
            if lyr and id(lyr) not in seen:
                lyr.selectionChanged.connect(self._update_preview)
                self._connected_layers.append(lyr)
                seen.add(id(lyr))

        self._update_preview()

    def _clear_preview(self):
        if self._preview_band:
            self._preview_band.reset(Qgis_GeomType_Polygon)

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def _update_preview(self, *args):
        self._clear_preview()

        navid_layer = self.pointLayerComboBox.currentLayer()
        fix_layer = self.fixLayerComboBox.currentLayer()
        if not navid_layer or not fix_layer:
            return

        if navid_layer.selectedFeatureCount() > 1 or fix_layer.selectedFeatureCount() > 1:
            return

        navid_sel = navid_layer.selectedFeatures()
        fix_sel = fix_layer.selectedFeatures()
        if not navid_sel or not fix_sel:
            return

        try:
            map_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            project = QgsProject.instance()

            def to_map(feat, lyr):
                g = feat.geometry()
                g.transform(QgsCoordinateTransform(lyr.crs(), map_crs, project))
                return g.asPoint()

            navid_geom = to_map(navid_sel[0], navid_layer)
            fix_geom = to_map(fix_sel[0], fix_layer)

            if navid_geom.distance(fix_geom) == 0:
                return

            rotate = self.rotateDoubleSpinBox.value()
            da = QgsDistanceArea()
            da.setSourceCrs(map_crs, project.transformContext())
            da.setEllipsoid(project.ellipsoid())

            tolerance_area, _ = build_tolerance_geometry(navid_geom, fix_geom, rotate, da)
            if tolerance_area and not tolerance_area.isEmpty():
                self._preview_band.setToGeometry(tolerance_area, None)
        except Exception:  # nosec B110 - best-effort live preview; a geometry/transform glitch must not crash the tool
            pass

    def calculate(self):
        navid_layer = self.pointLayerComboBox.currentLayer()
        fix_layer = self.fixLayerComboBox.currentLayer()

        if not navid_layer:
            self.log("Error: Please select a NAVID point layer")
            return
        if not fix_layer:
            self.log("Error: Please select a Fix point layer")
            return

        if navid_layer.selectedFeatureCount() > 1:
            msg = 'Select exactly one feature in the NAVID layer before calculating'
            self.log(f'Error: {msg}')
            self.iface.messageBar().pushMessage('QPANSOPY', msg, level=Qgis.Warning)
            return
        if fix_layer.selectedFeatureCount() > 1:
            msg = 'Select exactly one feature in the Fix layer before calculating'
            self.log(f'Error: {msg}')
            self.iface.messageBar().pushMessage('QPANSOPY', msg, level=Qgis.Warning)
            return

        nav_type = self.toleranceTypeComboBox.currentText()
        params = {'rotate': self.rotateDoubleSpinBox.value(), 'nav_type': nav_type}

        try:
            self.log(f"Calculating {nav_type} Tolerance...")
            from ...modules.conv.dme_tolerance import run_dme_tolerance
            result = run_dme_tolerance(self.iface, navid_layer, fix_layer, params)
            if result:
                self._clear_preview()
                self.log(f"{nav_type} Tolerance calculation completed successfully")
        except Exception as e:
            self.log(f"Error during calculation: {e}")
            import traceback
            self.log(traceback.format_exc())
