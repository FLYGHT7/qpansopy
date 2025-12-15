from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
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

        # Setup layer selector
        self.routingLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)

        # Defaults
        self.altitudeUnitCombo.setCurrentText('ft')
        self.outputFolderLineEdit.setText(self._get_desktop())

        # Signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self._browse)

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
        except Exception as e:
            import traceback
            self.log(f"Error during calculation: {e}")
            self.log(traceback.format_exc())
