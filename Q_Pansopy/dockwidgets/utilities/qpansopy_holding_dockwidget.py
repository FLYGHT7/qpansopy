from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, QMimeData
from qgis.core import QgsMapLayerProxyModel
import os

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
        self.routingLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)

        # Defaults
        self.altitudeUnitCombo.setCurrentText('ft')
        self.outputFolderLineEdit.setText(self._get_desktop())

        # Signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self._browse)
        self.copyWordButton.clicked.connect(self.copy_to_word)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def _get_desktop(self):
        if os.name == 'nt':
            return os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
        return os.path.expanduser('~/Desktop')

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

        if lyr.selectedFeatureCount() == 0:
            self.log('Error: Please select one segment before calculation')
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
                            f"Rate {summary.get('Rate_deg_s', 0):.3f} °/s | Radius {summary.get('Radius_nm', 0):.3f} NM"
                        )
                self.last_summary = res.get('summary')
                self.last_summary_text = res.get('summary_text')
        except Exception as e:
            import traceback
            self.log(f"Error during calculation: {e}")
            self.log(traceback.format_exc())

    def copy_to_word(self):
        summary = self.last_summary
        if not summary:
            self.log('Error: No calculation available to copy')
            return

        rows = [
            ("IAS", f"{summary.get('IAS_kt', 0):.1f}", "kt"),
            ("Altitude", f"{summary.get('Altitude_ft', 0):.0f}", "ft"),
            ("ISA Delta", f"{summary.get('ISA_var_C', 0):.1f}", "°C"),
            ("Bank Angle", f"{summary.get('Bank_deg', 0):.1f}", "deg"),
            ("Leg Time", f"{summary.get('Leg_min', 0):.2f}", "min"),
            ("Leg Length", f"{summary.get('Leg_nm', 0):.2f}", "NM"),
            ("Turn", f"{summary.get('Turn', '')}", ""),
            ("TAS", f"{summary.get('TAS_kt', 0):.2f}", "kt"),
            ("Rate of Turn", f"{summary.get('Rate_deg_s', 0):.3f}", "°/s"),
            ("Radius", f"{summary.get('Radius_nm', 0):.3f}", "NM"),
        ]

        # Build tab-delimited text (fallback) and HTML table (for Word)
        lines = ["Parameter\tValue\tUnits"]
        for p, v, u in rows:
            lines.append(f"{p}\t{v}\t{u}")
        table_text = "\n".join(lines)

        html_rows = ["<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>",
                     "<tr><th>Parameter</th><th>Value</th><th>Units</th></tr>"]
        for p, v, u in rows:
            html_rows.append(f"<tr><td>{p}</td><td style='text-align:right'>{v}</td><td>{u}</td></tr>")
        html_rows.append("</table>")
        html_table = "".join(html_rows)

        mime = QMimeData()
        mime.setHtml(html_table)
        mime.setText(table_text)
        QtWidgets.QApplication.clipboard().setMimeData(mime)
        self.log('Summary copied to clipboard as Word-friendly table')
