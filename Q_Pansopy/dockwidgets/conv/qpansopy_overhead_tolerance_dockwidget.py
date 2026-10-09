"""Dock for VOR/NDB overhead facility fix tolerance."""

import math
import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor, QDoubleValidator
from qgis.core import Qgis, QgsGeometry, QgsPointXY, QgsProject
from qgis.gui import QgsRubberBand

from ...qt_compat import (
    MLPM_LineLayer, MLPM_PointLayer, Qgis_GeomType_Line, Qgis_GeomType_Point,
    Qgis_GeomType_Polygon, preseed_active_layer,
)


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv',
    'qpansopy_overhead_tolerance_dockwidget.ui'))


class QPANSOPYOverheadToleranceDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Collect elevations and selected geometries for overhead construction."""

    closingPlugin = pyqtSignal()

    _LAYER_PREVIEW_SIGNALS = (
        'selectionChanged', 'geometryChanged', 'featureAdded',
        'featureDeleted', 'dataChanged', 'crsChanged',
    )
    _DIRECTION_LENGTH_PX = 24
    _DIRECTION_HALF_WIDTH_PX = 12

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        self._direction_preview_band = None
        self._connected_layers = []
        self._preview_active = False
        self._preview_closed = False
        self._removing_layer_ids = set()
        self.navaidLayerComboBox.setFilters(MLPM_PointLayer)
        self.trackLayerComboBox.setFilters(MLPM_LineLayer)
        preseed_active_layer(iface, self.navaidLayerComboBox, Qgis_GeomType_Point)
        preseed_active_layer(iface, self.trackLayerComboBox, Qgis_GeomType_Line)
        for field in (self.aircraftAltitudeLineEdit, self.stationElevationLineEdit):
            field.setValidator(QDoubleValidator(field))
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self._browse)
        self.exportKmlCheckBox.toggled.connect(self._update_export_controls)
        self._update_export_controls(False)
        for combo in (self.navaidLayerComboBox, self.trackLayerComboBox):
            combo.layerChanged.connect(self._on_preview_layers_changed)
        self.reverseDirectionCheckBox.toggled.connect(self._update_direction_preview)
        self.visibilityChanged.connect(self._on_visibility_changed)

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
            self._direction_preview_band = QgsRubberBand(canvas, Qgis_GeomType_Polygon)
            self._direction_preview_band.setColor(QColor(0, 170, 0, 120))
            self._direction_preview_band.setStrokeColor(QColor(0, 120, 0, 220))
            self._direction_preview_band.setWidth(1)
            canvas.scaleChanged.connect(self._update_direction_preview)
            canvas.destinationCrsChanged.connect(self._update_direction_preview)
            QgsProject.instance().layersWillBeRemoved.connect(self._on_layers_will_be_removed)
            QgsProject.instance().layersRemoved.connect(self._on_layers_removed)
            self._preview_active = True
        self._on_preview_layers_changed()

    def _disconnect_layer_signals(self):
        for layer in self._connected_layers:
            for signal_name in self._LAYER_PREVIEW_SIGNALS:
                try:
                    getattr(layer, signal_name).disconnect(self._update_direction_preview)
                except (TypeError, RuntimeError):
                    # Removed layers can already have disconnected their signals.
                    continue
        self._connected_layers = []

    def _on_preview_layers_changed(self, *args):
        self._disconnect_layer_signals()
        if self._preview_active and not self._preview_closed and self.isVisible():
            seen = set()
            for combo in (self.navaidLayerComboBox, self.trackLayerComboBox):
                layer = combo.currentLayer()
                if layer is None or id(layer) in seen or layer.id() in self._removing_layer_ids:
                    continue
                for signal_name in self._LAYER_PREVIEW_SIGNALS:
                    getattr(layer, signal_name).connect(self._update_direction_preview)
                self._connected_layers.append(layer)
                seen.add(id(layer))
        self._update_direction_preview()

    def _on_layers_will_be_removed(self, layer_ids):
        self._removing_layer_ids.update(layer_ids)
        if any(layer.id() in layer_ids for layer in self._connected_layers):
            self._clear_direction_preview()
            self._disconnect_layer_signals()

    def _on_layers_removed(self, layer_ids):
        self._removing_layer_ids.difference_update(layer_ids)
        self._on_preview_layers_changed()

    def _clear_direction_preview(self):
        if self._direction_preview_band is not None:
            self._direction_preview_band.reset(Qgis_GeomType_Polygon)

    def _stop_preview(self):
        self._disconnect_layer_signals()
        if self._preview_active:
            for signal, callback in (
                (self.iface.mapCanvas().scaleChanged, self._update_direction_preview),
                (self.iface.mapCanvas().destinationCrsChanged, self._update_direction_preview),
                (QgsProject.instance().layersWillBeRemoved, self._on_layers_will_be_removed),
                (QgsProject.instance().layersRemoved, self._on_layers_removed),
            ):
                try:
                    signal.disconnect(callback)
                except (TypeError, RuntimeError):
                    continue
        self._preview_active = False
        self._clear_direction_preview()
        if self._direction_preview_band is not None:
            self.iface.mapCanvas().scene().removeItem(self._direction_preview_band)
            self._direction_preview_band = None
        self._removing_layer_ids.clear()

    def _update_direction_preview(self, *args):
        self._clear_direction_preview()
        if not self.isVisible() or self._preview_closed or not self._preview_active:
            return
        try:
            from ...modules.conv.overhead_tolerance import resolve_overhead_direction_from_layers
            layers = (self.navaidLayerComboBox.currentLayer(), self.trackLayerComboBox.currentLayer())
            if any(layer is not None and layer.id() in self._removing_layer_ids for layer in layers):
                return
            canvas = self.iface.mapCanvas()
            station, direction, _tied = resolve_overhead_direction_from_layers(
                *layers, canvas.mapSettings().destinationCrs(), self.reverseDirectionCheckBox.isChecked())
            mupp = canvas.mapUnitsPerPixel()
            if not math.isfinite(mupp) or mupp <= 0:
                return
            norm = math.hypot(*direction)
            ux, uy = direction[0] / norm, direction[1] / norm
            length = self._DIRECTION_LENGTH_PX * mupp
            half_width = self._DIRECTION_HALF_WIDTH_PX * mupp
            tip = QgsPointXY(station[0] + ux * length, station[1] + uy * length)
            left = QgsPointXY(station[0] - uy * half_width, station[1] + ux * half_width)
            right = QgsPointXY(station[0] + uy * half_width, station[1] - ux * half_width)
            triangle = QgsGeometry.fromPolygonXY([[tip, left, right, tip]])
            self._direction_preview_band.setToGeometry(triangle, None)
        except Exception:  # nosec B110 - invalid input clears the optional preview without interrupting the dock
            self._clear_direction_preview()

    def _update_export_controls(self, enabled):
        self.outputFolderLineEdit.setEnabled(enabled)
        self.browseButton.setEnabled(enabled)

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select KML output folder', self.outputFolderLineEdit.text())
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        self.logTextEdit.append(str(message))
        self.logTextEdit.ensureCursorVisible()

    @staticmethod
    def _feet(field, unit):
        value = field.text().strip()
        if not value:
            raise ValueError('Enter both aircraft altitude and station elevation')
        number = float(value)
        return number / 0.3048 if unit.currentText() == 'm' else number

    def calculate(self):
        try:
            navaid_layer = self.navaidLayerComboBox.currentLayer()
            track_layer = self.trackLayerComboBox.currentLayer()
            if navaid_layer is None or track_layer is None:
                raise ValueError('Select a navaid point layer and a track line layer')
            params = {
                'navaid_type': self.navaidTypeComboBox.currentText(),
                'aircraft_altitude_ft': self._feet(
                    self.aircraftAltitudeLineEdit, self.aircraftUnitComboBox),
                'station_elevation_ft': self._feet(
                    self.stationElevationLineEdit, self.stationUnitComboBox),
                'reverse_direction': self.reverseDirectionCheckBox.isChecked(),
                'include_cone': self.includeConeCheckBox.isChecked(),
                'include_points': self.includePointsCheckBox.isChecked(),
                'export_kml': self.exportKmlCheckBox.isChecked(),
                'output_dir': self.outputFolderLineEdit.text().strip(),
            }
            from ...modules.conv.overhead_tolerance import run_overhead_tolerance
            run_overhead_tolerance(self.iface, navaid_layer, track_layer, params)
            self.log('{0} overhead tolerance created.'.format(params['navaid_type']))
        except (ValueError, RuntimeError) as exc:
            self.log('Error: {0}'.format(exc))
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(exc), level=Qgis.Warning)
        except Exception as exc:
            self.log('Error: {0}'.format(exc))
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(exc), level=Qgis.Critical)
