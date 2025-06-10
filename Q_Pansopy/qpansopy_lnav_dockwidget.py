from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, Qt
from qgis.core import QgsMapLayerProxyModel
import os
import datetime

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qpansopy_lnav_dockwidget.ui'))

class QPANSOPYLNAVDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super(QPANSOPYLNAVDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        # Setup layer combobox
        self.routingLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        
        # Set default output folder
        self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Connect signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self.browse_output_folder)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def get_desktop_path(self):
        if os.name == 'nt':
            return os.path.join(os.environ['USERPROFILE'], 'Desktop')
        return os.path.expanduser('~/Desktop')

    def browse_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.outputFolderLineEdit.text()
        )
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def calculate(self):
        routing_layer = self.routingLayerComboBox.currentLayer()
        if not routing_layer:
            self.log("Error: Please select a routing layer")
            return

        # Get export options
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()

        # Determine which approach to calculate
        if self.initialRadioButton.isChecked():
            from .modules.PBN_LNAV_Initial_Approach import run_initial_approach
            run_initial_approach(self.iface, routing_layer)
        elif self.intermediateRadioButton.isChecked():
            from .modules.PBN_LNAV_Intermediate_Approach import run_intermediate_approach
            run_intermediate_approach(self.iface, routing_layer)
        else:  # Final approach
            from .modules.PBN_LNAV_Final_Approach import run_final_approach
            run_final_approach(self.iface, routing_layer)
