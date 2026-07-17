# -*- coding: utf-8 -*-
import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsRubberBand
from qgis.core import (
    QgsGeometry, QgsPoint, QgsLineString, QgsPolygon, QgsCircle,
    QgsProject, QgsDistanceArea, QgsCoordinateTransform, Qgis,
)
from ...qt_compat import (
    MLPM_PointLayer,
    preseed_active_layer, Qgis_GeomType_Point, Qgis_GeomType_Polygon,
)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv',
    'qpansopy_vor_dme_tolerance_dockwidget.ui'))


class QPANSOPYVORDMEToleranceDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

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
        self._on_layer_changed()

    def closeEvent(self, event):
        self._clear_preview()
        self.closingPlugin.emit()
        event.accept()

    def _on_layer_changed(self):
        for lyr in self._connected_layers:
            try:
                lyr.selectionChanged.disconnect(self._update_preview)
            except Exception:
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

            rotate = self.rotateDoubleSpinBox.value()
            azimuth = navid_geom.azimuth(fix_geom)
            length0 = navid_geom.distance(fix_geom)
            if length0 == 0:
                return

            da = QgsDistanceArea()
            da.setSourceCrs(map_crs, project.transformContext())
            da.setEllipsoid(project.ellipsoid())
            length0_m = da.measureLine(navid_geom, fix_geom)

            dme_tol_m = 0.25 * 1852 + 0.0125 * length0_m
            dme_tolerance = (dme_tol_m / length0_m) * length0 if length0_m > 0 else dme_tol_m

            pt1 = QgsPoint(navid_geom)
            proj2 = navid_geom.project(length0 * 5, azimuth + rotate)
            proj3 = navid_geom.project(length0 * 5, azimuth - rotate)
            sector = QgsGeometry(QgsPolygon(QgsLineString([pt1, QgsPoint(proj2), QgsPoint(proj3)])))

            dme_circle = QgsGeometry(
                QgsCircle(QgsPoint(navid_geom), length0).toCircularString()
            ).buffer(dme_tolerance, 360)

            tolerance_area = sector.intersection(dme_circle)
            if tolerance_area and not tolerance_area.isEmpty():
                self._preview_band.setToGeometry(tolerance_area, None)
        except Exception:
            pass

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

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

        params = {'rotate': self.rotateDoubleSpinBox.value()}

        try:
            self.log("Calculating VOR/DME Tolerance...")
            from ...modules.conv.vor_dme_tolerance import run_vor_dme_tolerance
            result = run_vor_dme_tolerance(self.iface, navid_layer, fix_layer, params)
            if result:
                self._clear_preview()
                self.log("VOR/DME Tolerance calculation completed successfully")
        except Exception as e:
            self.log(f"Error during calculation: {e}")
            import traceback
            self.log(traceback.format_exc())
