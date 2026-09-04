import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis
from ...qt_compat import MLPM_LineLayer, preseed_active_layer, Qgis_GeomType_Line

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_holding_dockwidget.ui'))


class QPANSOPYHoldingDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self.last_summary = None
        self.last_summary_text = None

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

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

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
            params = {
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

            from ...modules.utilities.holding import run_holding_pattern
            res = run_holding_pattern(self.iface, lyr, params)
            if res:
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

        flat_params = {
            'IAS_kt': f"{summary.get('IAS_kt', 0):.1f}",
            'Altitude_ft': f"{summary.get('Altitude_ft', 0):.0f}",
            'ISA_var_C': f"{summary.get('ISA_var_C', 0):.1f}",
            'Bank_deg': f"{summary.get('Bank_deg', 0):.1f}",
            'Leg_min': f"{summary.get('Leg_min', 0):.2f}",
            'Leg_nm': f"{summary.get('Leg_nm', 0):.2f}",
            'Turn': summary.get('Turn', ''),
            'TAS_kt': f"{summary.get('TAS_kt', 0):.2f}",
            'Rate_deg_s': f"{summary.get('Rate_deg_s', 0):.3f}",
            'Radius_nm': f"{summary.get('Radius_nm', 0):.3f}",
        }

        from ...parameters_inspector_dialog import show_web_popup
        show_web_popup("Holding Pattern — Feature Parameters", [("Holding Pattern", flat_params)])
        self.log('Holding pattern parameters shown in Parameters Inspector.')
