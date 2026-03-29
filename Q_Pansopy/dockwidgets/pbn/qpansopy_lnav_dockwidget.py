from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, Qt
from qgis.core import QgsMapLayerProxyModel
import os
import datetime
import runpy

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'pbn', 'qpansopy_lnav_dockwidget.ui'))

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

        # No RNAV mode selector needed (RNAV1/2 same output)

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
        """Run the calculation"""
        routing_layer = self.routingLayerComboBox.currentLayer()
        if not routing_layer:
            self.log("Error: Please select a routing layer")
            return
            
        # NO hacer selecciones automáticas aquí
        # Verificar que el usuario tenga al menos un elemento seleccionado
        if routing_layer.selectedFeatureCount() == 0:
            self.log("Error: Please select at least one segment in the map before calculation")
            self.log("Tip: Use the selection tool to manually select the segment you want to calculate")
            return
        
        # Get export options
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()

        try:
            # Determine which approach to calculate
            if self.arrivalRadioButton.isChecked():
                self.log("Calculating Arrival...")
                from ...modules.pbn.pbn_rnav1_arrival import run_rnav1_arrival
                params = {'export_kml': export_kml, 'output_dir': output_dir}
                result = run_rnav1_arrival(self.iface, routing_layer, params)
                approach_type = "Arrival"
            elif self.initialRadioButton.isChecked():
                self.log("Calculating Initial Approach...")
                # Use function from Initial Approach module
                from ...modules.pbn.PBN_LNAV_Initial_Approach import run_initial_approach
                result = run_initial_approach(self.iface, routing_layer, export_kml, output_dir)
                approach_type = "Initial"
            elif self.intermediateRadioButton.isChecked():
                self.log("Calculating Intermediate Approach...")
                # Use function from Intermediate Approach module
                from ...modules.pbn.PBN_LNAV_Intermediate_Approach import run_intermediate_approach
                result = run_intermediate_approach(self.iface, routing_layer, export_kml, output_dir)
                approach_type = "Intermediate"
            elif self.missedRadioButton.isChecked():
                self.log("Calculating Missed Approach...")
                from ...modules.pbn.PBN_LNAV_Missed_Approach import run_missed_approach
                result = run_missed_approach(self.iface, routing_layer, export_kml, output_dir)
                approach_type = "Missed Approach"
            elif getattr(self, 'sidRadioButton', None) and self.sidRadioButton.isChecked():
                # RNAV1/2 same output; label accordingly
                rnav_mode = 'RNAV1/2'
                self.log(f"Calculating {rnav_mode} SID...")
                from ...modules.pbn.rnav_sid_missed import run_rnav_sid_missed
                result = run_rnav_sid_missed(self.iface, routing_layer, 'RNAV1', 'SID', export_kml, output_dir)
                approach_type = f"SID ({rnav_mode})"
            else:  # Final approach
                self.log("Calculating Final Approach...")
                # Use function from Final Approach module
                from ...modules.pbn.PBN_LNAV_Final_Approach import run_final_approach
                result = run_final_approach(self.iface, routing_layer, export_kml, output_dir)
                approach_type = "Final"

            # Log results
            if result:
                self.log(f"{approach_type} Approach calculation completed successfully")
                if export_kml and 'kml_path' in result:
                    self.log(f"KML exported to: {result['kml_path']}")
                elif export_kml:
                    self.log(f"KML export was requested but not supported for {approach_type} approach")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
