from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, Qt
from qgis.core import QgsMapLayerProxyModel
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'pbn', 'qpansopy_rnav1_arrival_dockwidget.ui'))


class QPANSOPYRnav1ArrivalDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super(QPANSOPYRnav1ArrivalDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        # Setup layer combobox - only line layers
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
        """Run the RNAV 1 Arrival calculation"""
        routing_layer = self.routingLayerComboBox.currentLayer()
        
        if not routing_layer:
            self.log("Error: Please select a routing layer")
            return
            
        # Check for selection
        if routing_layer.selectedFeatureCount() == 0:
            self.log("Error: Please select the arrival segment in the map")
            self.log("Tip: Use the selection tool to select the arrival segment")
            return
        
        # Get parameters
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()

        try:
            self.log("Creating RNAV 1 Arrival area...")
            
            from ...modules.pbn.pbn_rnav1_arrival import run_rnav1_arrival
            
            params = {
                'export_kml': export_kml,
                'output_dir': output_dir
            }
            
            result = run_rnav1_arrival(self.iface, routing_layer, params)
            
            if result:
                self.log("RNAV 1 Arrival calculation completed successfully")
                if export_kml and 'kml_path' in result:
                    self.log(f"KML exported to: {result['kml_path']}")
            else:
                self.log("Calculation failed - check messages above")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
