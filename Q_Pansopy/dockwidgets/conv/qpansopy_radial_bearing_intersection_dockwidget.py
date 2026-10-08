"""Dockwidget for radial/bearing intersection fix tolerance."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import Qgis, QgsGeometry, QgsPointXY, QgsProject
from qgis.gui import QgsRubberBand

from ...qt_compat import (
    MLPM_PointLayer, Qgis_GeomType_Line, Qgis_GeomType_Point,
    Qgis_GeomType_Polygon, preseed_active_layer,
)


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv',
    'qpansopy_radial_bearing_intersection_dockwidget.ui'))


class QPANSOPYRadialBearingIntersectionDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Choose two facilities and their nominal intersection point."""

    closingPlugin = pyqtSignal()

    _LAYER_PREVIEW_SIGNALS = (
        'selectionChanged', 'geometryChanged', 'featureAdded',
        'featureDeleted', 'dataChanged', 'crsChanged',
    )

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        self._preview_band = None
        self._construction_preview_band = None
        self._connected_layers = []
        self._preview_active = False
        self._preview_closed = False
        self._removing_layer_ids = set()
        for combo in (self.trackingLayerComboBox, self.crossingLayerComboBox,
                      self.fixLayerComboBox):
            combo.setFilters(MLPM_PointLayer)
            preseed_active_layer(iface, combo, Qgis_GeomType_Point)
            combo.layerChanged.connect(self._on_preview_layers_changed)
        self.trackingTypeComboBox.currentTextChanged.connect(self._update_preview)
        self.crossingTypeComboBox.currentTextChanged.connect(self._update_preview)
        self.includeConstructionLinesCheckBox.toggled.connect(self._update_preview)
        self.visibilityChanged.connect(self._on_visibility_changed)
        self.calculateButton.clicked.connect(self.calculate)

    def closeEvent(self, event):
        self._preview_closed = True
        self._stop_preview()
        self.closingPlugin.emit()
        event.accept()

    def _on_visibility_changed(self, visible):
        if visible:
            self._start_preview()
        else:
            self._stop_preview()

    def _start_preview(self):
        if self._preview_closed:
            return
        if not self._preview_active:
            canvas = self.iface.mapCanvas()
            self._preview_band = QgsRubberBand(canvas, Qgis_GeomType_Polygon)
            self._preview_band.setColor(QColor(0, 100, 255, 80))
            self._preview_band.setStrokeColor(QColor(0, 100, 255, 200))
            self._preview_band.setWidth(1)
            self._construction_preview_band = QgsRubberBand(canvas, Qgis_GeomType_Line)
            self._construction_preview_band.setColor(QColor(230, 184, 0, 200))
            self._construction_preview_band.setWidth(1)
            canvas.destinationCrsChanged.connect(self._update_preview)
            QgsProject.instance().layersWillBeRemoved.connect(self._on_layers_will_be_removed)
            QgsProject.instance().layersRemoved.connect(self._on_layers_removed)
            self._preview_active = True
        self._on_preview_layers_changed()

    def _disconnect_layer_signals(self):
        for layer in self._connected_layers:
            for signal_name in self._LAYER_PREVIEW_SIGNALS:
                try:
                    getattr(layer, signal_name).disconnect(self._update_preview)
                except (TypeError, RuntimeError):
                    # A removed layer may already have disconnected its signals.
                    continue
        self._connected_layers = []

    def _on_preview_layers_changed(self, *args):
        self._disconnect_layer_signals()
        if self._preview_active and not self._preview_closed and self.isVisible():
            seen = set()
            for combo in (self.trackingLayerComboBox, self.crossingLayerComboBox,
                          self.fixLayerComboBox):
                layer = combo.currentLayer()
                if layer is None or id(layer) in seen or layer.id() in self._removing_layer_ids:
                    continue
                for signal_name in self._LAYER_PREVIEW_SIGNALS:
                    getattr(layer, signal_name).connect(self._update_preview)
                self._connected_layers.append(layer)
                seen.add(id(layer))
        self._update_preview()

    def _on_layers_will_be_removed(self, layer_ids):
        self._removing_layer_ids.update(layer_ids)
        if any(layer.id() in layer_ids for layer in self._connected_layers):
            self._clear_preview()
            self._disconnect_layer_signals()

    def _on_layers_removed(self, layer_ids):
        self._removing_layer_ids.difference_update(layer_ids)
        self._on_preview_layers_changed()

    def _clear_preview(self):
        if self._preview_band is not None:
            self._preview_band.reset(Qgis_GeomType_Polygon)
        if self._construction_preview_band is not None:
            self._construction_preview_band.reset(Qgis_GeomType_Line)

    def _stop_preview(self):
        self._disconnect_layer_signals()
        if self._preview_active:
            for signal, callback in (
                (self.iface.mapCanvas().destinationCrsChanged, self._update_preview),
                (QgsProject.instance().layersWillBeRemoved, self._on_layers_will_be_removed),
                (QgsProject.instance().layersRemoved, self._on_layers_removed),
            ):
                try:
                    signal.disconnect(callback)
                except (TypeError, RuntimeError):
                    continue
        self._preview_active = False
        self._clear_preview()
        for attr in ('_preview_band', '_construction_preview_band'):
            band = getattr(self, attr)
            if band is not None:
                self.iface.mapCanvas().scene().removeItem(band)
                setattr(self, attr, None)
        self._removing_layer_ids.clear()

    def _update_preview(self, *args):
        self._clear_preview()
        if not self.isVisible() or self._preview_closed or not self._preview_active:
            return
        try:
            from ...modules.conv.radial_bearing_intersection import (
                build_intersection_tolerance_from_layers,
            )
            layers = (
                self.trackingLayerComboBox.currentLayer(),
                self.crossingLayerComboBox.currentLayer(),
                self.fixLayerComboBox.currentLayer(),
            )
            if any(layer is not None and layer.id() in self._removing_layer_ids for layer in layers):
                return
            result = build_intersection_tolerance_from_layers(
                *layers, self.iface.mapCanvas().mapSettings().destinationCrs(),
                self.trackingTypeComboBox.currentText(), self.crossingTypeComboBox.currentText())
            polygon = QgsGeometry.fromPolygonXY([
                [QgsPointXY(*point) for point in result.ring]])
            lines = QgsGeometry.fromMultiPolylineXY([
                [QgsPointXY(*segment.start), QgsPointXY(*segment.end)]
                for segment in result.construction_lines])
            if not polygon.isGeosValid() or not lines.isGeosValid():
                return
            self._preview_band.setToGeometry(polygon, None)
            if self.includeConstructionLinesCheckBox.isChecked():
                self._construction_preview_band.setToGeometry(lines, None)
        except Exception:  # nosec B110 - unusable input clears the optional preview without interrupting the dock
            self._clear_preview()

    def log(self, message):
        self.logTextEdit.append(str(message))
        self.logTextEdit.ensureCursorVisible()

    def _log_result(self, result):
        self.log('Early: {0:.3f} NM; late: {1:.3f} NM'.format(
            result.early_nm, result.late_nm))

    def calculate(self):
        params = {
            'tracking_type': self.trackingTypeComboBox.currentText(),
            'crossing_type': self.crossingTypeComboBox.currentText(),
            'include_construction_lines': self.includeConstructionLinesCheckBox.isChecked(),
            'on_result': self._log_result,
        }
        try:
            from ...modules.conv.radial_bearing_intersection import (
                run_radial_bearing_intersection,
            )
            result = run_radial_bearing_intersection(
                self.iface, self.trackingLayerComboBox.currentLayer(),
                self.crossingLayerComboBox.currentLayer(),
                self.fixLayerComboBox.currentLayer(), params)
            if result:
                self._clear_preview()
                self.log('Radial/bearing fix tolerance created.')
        except (ValueError, RuntimeError) as error:
            self._clear_preview()
            self.log('Error: {0}'.format(error))
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(error), level=Qgis.Warning)
        except Exception as error:
            self._clear_preview()
            self.log('Error: {0}'.format(error))
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(error), level=Qgis.Critical)
