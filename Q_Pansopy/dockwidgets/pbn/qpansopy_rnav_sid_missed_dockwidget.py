from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsMapLayerProxyModel
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'pbn', 'qpansopy_rnav_sid_missed_dockwidget.ui'))


class QPANSOPYRNAVSIDMissedDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)

        # Setup layer selector
        self.routingLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)

        # Defaults
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
            self.log('Error: Please select at least one segment before calculation')
            return

        rnav_mode = 'RNAV1' if self.rnav1RadioButton.isChecked() else 'RNAV2'
        op_mode = 'SID' if self.sidRadioButton.isChecked() else 'MISSED'
        export_kml = self.exportKmlCheckBox.isChecked() if hasattr(self, 'exportKmlCheckBox') else False
        out_dir = self.outputFolderLineEdit.text()

        try:
            from ...modules.pbn.rnav_sid_missed import run_rnav_sid_missed
            res = run_rnav_sid_missed(self.iface, lyr, rnav_mode, op_mode, export_kml, out_dir)
            if res:
                self.log(f"{rnav_mode} {op_mode} calculation completed")
                if export_kml and 'kml_path' in res:
                    self.log(f"KML exported to: {res['kml_path']}")
        except Exception as e:
            import traceback
            self.log(f"Error during calculation: {e}")
            self.log(traceback.format_exc())
