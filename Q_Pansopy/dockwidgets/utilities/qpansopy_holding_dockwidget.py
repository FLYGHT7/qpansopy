import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis, QgsGeometry, QgsProject
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsRubberBand
from ...qt_compat import MLPM_LineLayer, preseed_active_layer, Qgis_GeomType_Line

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_holding_dockwidget.ui'))


class QPANSOPYHoldingDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    _LAYER_PREVIEW_SIGNALS = (
        'selectionChanged', 'geometryChanged', 'featureAdded',
        'featureDeleted', 'dataChanged', 'crsChanged',
    )

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self.last_summary = None
        self.last_summary_text = None
        self._preview_band = None
        self._connected_layers = []
        self._preview_active = False
        self._preview_closed = False
        self._removing_layer_ids = set()

        # Setup layer selector
        self.routingLayerComboBox.setFilters(MLPM_LineLayer)
        preseed_active_layer(iface, self.routingLayerComboBox, Qgis_GeomType_Line)

        # Defaults
        self.altitudeUnitCombo.setCurrentText('ft')
        self.outputFolderLineEdit.setText(self.get_desktop_path())

        # Signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self._browse)
        self.copyWordButton.setText("Show Table")
        self.copyWordButton.clicked.connect(self.show_parameters_table)
        self.routingLayerComboBox.layerChanged.connect(self._on_preview_layers_changed)
        for control in (self.iasLineEdit, self.altitudeLineEdit,
                        self.isaVarLineEdit, self.bankAngleLineEdit,
                        self.legTimeLineEdit):
            control.textChanged.connect(self._update_preview)
        self.altitudeUnitCombo.currentTextChanged.connect(self._update_preview)
        self.rightTurnRadio.toggled.connect(self._update_preview)
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
            self._preview_band = QgsRubberBand(canvas, Qgis_GeomType_Line)
            self._preview_band.setColor(QColor('green'))
            self._preview_band.setWidth(2)
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
            layer = self.routingLayerComboBox.currentLayer()
            if layer is not None and layer.id() not in self._removing_layer_ids:
                for signal_name in self._LAYER_PREVIEW_SIGNALS:
                    getattr(layer, signal_name).connect(self._update_preview)
                self._connected_layers.append(layer)
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
            self._preview_band.reset(Qgis_GeomType_Line)

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
        if self._preview_band is not None:
            self.iface.mapCanvas().scene().removeItem(self._preview_band)
            self._preview_band = None
        self._removing_layer_ids.clear()

    def _update_preview(self, *args):
        self._clear_preview()
        if not self.isVisible() or self._preview_closed or not self._preview_active:
            return
        try:
            layer = self.routingLayerComboBox.currentLayer()
            if (layer is None or layer.id() in self._removing_layer_ids or
                    layer.selectedFeatureCount() != 1):
                return
            map_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            if (not map_crs.isValid() or map_crs.isGeographic() or
                    map_crs.mapUnits() != Qgis.DistanceUnit.Meters or
                    layer.crs() != map_crs):
                return
            geometry = layer.selectedFeatures()[0].geometry()
            if geometry.isNull() or geometry.isEmpty() or geometry.isMultipart():
                return
            from ...modules.utilities.holding import build_holding_nominal
            result = build_holding_nominal(geometry.asPolyline(), self._read_parameters())
            paths = [segment.asPolyline() for segment in result.geometries]
            self._preview_band.setToGeometry(QgsGeometry.fromMultiPolylineXY(paths), None)
        except Exception:  # nosec B110 - invalid live inputs clear the optional preview without interrupting editing
            self._clear_preview()

    def _read_parameters(self):
        """Use the same explicit input values for preview and Calculate."""
        return {
            'IAS': float(self.iasLineEdit.text()),
            'altitude': float(self.altitudeLineEdit.text()),
            'altitude_unit': self.altitudeUnitCombo.currentText(),
            'isa_var': float(self.isaVarLineEdit.text()),
            'bank_angle': float(self.bankAngleLineEdit.text()),
            'leg_time_min': float(self.legTimeLineEdit.text()),
            'turn': 'L' if self.leftTurnRadio.isChecked() else 'R',
            'show_circles': self.showCirclesCheckBox.isChecked(),
            'output_dir': self.outputFolderLineEdit.text(),
        }

    def get_desktop_path(self) -> str:
        from ...utils import get_desktop_path as _gdp
        return _gdp()

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Output Folder', self.outputFolderLineEdit.text())
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, msg):
        if hasattr(self, 'logTextEdit') and self.logTextEdit:
            self.logTextEdit.append(msg)
            self.logTextEdit.ensureCursorVisible()

    def calculate(self):
        lyr = self.routingLayerComboBox.currentLayer()
        if not lyr:
            self.log('Error: Please select a routing layer')
            return

        if lyr.selectedFeatureCount() != 1:
            msg = 'Select exactly one segment in the routing layer before calculating'
            self.log(f'Error: {msg}')
            self.iface.messageBar().pushMessage('QPANSOPY', msg, level=Qgis.Warning)
            return

        try:
            params = self._read_parameters()

            from ...modules.utilities.holding import run_holding_pattern
            res = run_holding_pattern(self.iface, lyr, params)
            if res:
                self._clear_preview()
                self.log('Holding pattern created successfully')
                summary_text = res.get('summary_text')
                if summary_text:
                    self.log(summary_text)
                else:
                    summary = res.get('summary', {})
                    if summary:
                        self.log(
                            f"IAS {summary.get('IAS_kt', 0):.1f} kt | Alt {summary.get('Altitude_ft', 0):.0f} ft | "
                            f"ISA Δ {summary.get('ISA_var_C', 0):.1f}°C | Bank {summary.get('Bank_deg', 0):.1f}° | "
                            f"Leg {summary.get('Leg_min', 0):.2f} min ({summary.get('Leg_nm', 0):.2f} NM) | "
                            f"Turn {summary.get('Turn', '?')} | TAS {summary.get('TAS_kt', 0):.2f} kt | "
                            f"Rate {summary.get('Rate_deg_s', 0):.3f} °/s | "
                            f"Radius {summary.get('Radius_nm', 0):.3f} NM"
                        )
                self.last_summary = res.get('summary')
                self.last_summary_text = res.get('summary_text')
        except Exception as e:
            import traceback
            self.log(f"Error during calculation: {e}")
            self.log(traceback.format_exc())

    def show_parameters_table(self):
        """Show the last calculation's parameters as a rendered HTML table.
        The popup itself offers a 'Copy to Word' button (issue #193)."""
        summary = self.last_summary
        if not summary:
            self.log('Error: No calculation available to show')
            return

        from ...modules.utilities.holding import build_holding_table_views
        from ...parameters_inspector_dialog import show_web_popup
        show_web_popup(
            "Holding Pattern — Feature Parameters", [],
            table_views=build_holding_table_views(summary))
        self.log('Holding pattern parameters shown in Parameters Inspector.')
