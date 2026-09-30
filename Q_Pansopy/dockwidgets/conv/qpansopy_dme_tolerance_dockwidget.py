# -*- coding: utf-8 -*-
import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsRubberBand
from qgis.core import (
    QgsProject, QgsDistanceArea, QgsCsException, Qgis,
)
from ...modules.conv.dme_tolerance import build_tolerance_geometry, _geom_to_map_crs
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

    # (nav_type, default_rotate, default_non_collocated)
    _TOLERANCE_TYPES = [
        ('VOR/DME', 5.2, False),
        ('NDB/DME', 6.9, False),
        ('LOC/DME', 2.4, True),
    ]

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        for nav_type, default_rotate, non_collocated in self._TOLERANCE_TYPES:
            self.toleranceTypeComboBox.addItem(nav_type, (default_rotate, non_collocated))
        self.toleranceTypeComboBox.currentIndexChanged.connect(self._on_tolerance_type_changed)

        self.pointLayerComboBox.setFilters(MLPM_PointLayer)
        self.fixLayerComboBox.setFilters(MLPM_PointLayer)
        self.trackingLayerComboBox.setFilters(MLPM_PointLayer)
        self.trackingLayerComboBox.setAllowEmptyLayer(True)
        self.trackingLayerComboBox.setLayer(None)
        preseed_active_layer(iface, self.pointLayerComboBox, Qgis_GeomType_Point)
        preseed_active_layer(iface, self.fixLayerComboBox, Qgis_GeomType_Point)

        self.calculateButton.clicked.connect(self.calculate)

        # Live preview rubber band
        self._preview_band = QgsRubberBand(iface.mapCanvas(), Qgis_GeomType_Polygon)
        self._preview_band.setColor(QColor(0, 100, 255, 80))
        self._preview_band.setStrokeColor(QColor(0, 100, 255, 200))
        self._preview_band.setWidth(1)
        self._connected_layers = []
        self.visibilityChanged.connect(self._on_visibility_changed)

        self.pointLayerComboBox.layerChanged.connect(self._on_layer_changed)
        self.fixLayerComboBox.layerChanged.connect(self._on_layer_changed)
        self.trackingLayerComboBox.layerChanged.connect(self._on_layer_changed)
        self.nonCollocatedDmeCheckBox.toggled.connect(self._on_dme_mode_changed)
        self.rotateDoubleSpinBox.valueChanged.connect(self._update_preview)
        iface.mapCanvas().destinationCrsChanged.connect(self._update_preview)

        self._on_tolerance_type_changed()
        self._on_layer_changed()

    def _on_tolerance_type_changed(self, *args):
        default_rotate, non_collocated = self.toleranceTypeComboBox.currentData()
        self.rotateDoubleSpinBox.setValue(default_rotate)
        self.nonCollocatedDmeCheckBox.setChecked(non_collocated)
        self._on_dme_mode_changed()

    def _on_dme_mode_changed(self, *args):
        enabled = self.nonCollocatedDmeCheckBox.isChecked()
        self.trackingLayerLabel.setVisible(enabled)
        self.trackingLayerComboBox.setVisible(enabled)
        self.trackingLayerComboBox.setEnabled(enabled)
        self._on_layer_changed()

    def closeEvent(self, event):
        self._clear_preview()
        self.closingPlugin.emit()
        event.accept()

    def _on_visibility_changed(self, visible):
        """Clear the canvas preview on hide; rebuild it from current inputs on show."""
        if visible:
            self._update_preview()
        else:
            self._clear_preview()

    def _on_layer_changed(self):
        for lyr in self._connected_layers:
            try:
                lyr.selectionChanged.disconnect(self._update_preview)
            except Exception:  # nosec B110 - signal may already be disconnected; safe to ignore
                pass
        self._connected_layers = []

        seen = set()
        combos = [self.pointLayerComboBox, self.fixLayerComboBox]
        if self.nonCollocatedDmeCheckBox.isChecked():
            combos.append(self.trackingLayerComboBox)
        for combo in combos:
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
        if not self.isVisible():
            return

        navid_layer = self.pointLayerComboBox.currentLayer()
        fix_layer = self.fixLayerComboBox.currentLayer()
        non_collocated = self.nonCollocatedDmeCheckBox.isChecked()
        tracking_layer = self.trackingLayerComboBox.currentLayer() if non_collocated else None
        layers = [navid_layer, fix_layer]
        if non_collocated:
            layers.append(tracking_layer)
        if any(not layer or layer.selectedFeatureCount() != 1 for layer in layers):
            return

        navid_sel = navid_layer.selectedFeatures()
        fix_sel = fix_layer.selectedFeatures()

        try:
            map_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            project = QgsProject.instance()

            navid_geom = _geom_to_map_crs(navid_sel[0], navid_layer, map_crs, project, 'DME')
            fix_geom = _geom_to_map_crs(fix_sel[0], fix_layer, map_crs, project, 'Fix')
            tracking_geom = None
            if non_collocated:
                tracking_geom = _geom_to_map_crs(
                    tracking_layer.selectedFeatures()[0], tracking_layer,
                    map_crs, project, 'Tracking Navaid')

            rotate = self.rotateDoubleSpinBox.value()
            da = QgsDistanceArea()
            da.setSourceCrs(map_crs, project.transformContext())
            da.setEllipsoid(project.ellipsoid())

            tolerance_area, _ = build_tolerance_geometry(
                navid_geom, fix_geom, rotate, da, tracking_geom)
            if tolerance_area and not tolerance_area.isEmpty():
                self._preview_band.setToGeometry(tolerance_area, None)
        except Exception:  # nosec B110 - best-effort live preview; a geometry/transform glitch must not crash the tool
            pass

    def _warn(self, message):
        self._clear_preview()
        self.log(f'Warning: {message}')
        self.iface.messageBar().pushMessage('QPANSOPY', message, level=Qgis.Warning)

    def calculate(self):
        navid_layer = self.pointLayerComboBox.currentLayer()
        fix_layer = self.fixLayerComboBox.currentLayer()

        non_collocated = self.nonCollocatedDmeCheckBox.isChecked()
        tracking_layer = self.trackingLayerComboBox.currentLayer() if non_collocated else None
        roles = [('DME', navid_layer), ('Fix', fix_layer)]
        if non_collocated:
            roles.append(('Tracking Navaid', tracking_layer))
        for role, layer in roles:
            if not layer:
                self._warn(f'Please select a {role} point layer')
                return
            selected_count = layer.selectedFeatureCount()
            if selected_count > 1 or (selected_count == 0 and layer.featureCount() != 1):
                self._warn(f'Select exactly one feature in the {role} layer before calculating')
                return

        nav_type = self.toleranceTypeComboBox.currentText()
        params = {
            'rotate': self.rotateDoubleSpinBox.value(), 'nav_type': nav_type,
            'non_collocated_dme': non_collocated,
        }

        try:
            self.log(f"Calculating {nav_type} Tolerance...")
            from ...modules.conv.dme_tolerance import run_dme_tolerance
            result = run_dme_tolerance(
                self.iface, navid_layer, fix_layer, params, tracking_layer=tracking_layer)
            if result:
                self._clear_preview()
                self.log(f"{nav_type} Tolerance calculation completed successfully")
        except (ValueError, QgsCsException) as e:
            self._warn(str(e))
        except Exception as e:
            self.log(f"Error during calculation: {e}")
            import traceback
            self.log(traceback.format_exc())
