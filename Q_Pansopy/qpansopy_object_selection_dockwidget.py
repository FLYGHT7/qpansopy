from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsMapLayerProxyModel, Qgis
from qgis.gui import QgsMapLayerComboBox
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qpansopy_object_selection_dockwidget.ui'))

class QPANSOPYObjectSelectionDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super(QPANSOPYObjectSelectionDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        # Setup layer combos
        self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.surfaceLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        
        # Set default output folder
        self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Connect signals
        self.calculateButton.clicked.connect(self.extract_objects)
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

    def extract_objects(self):
        """Extract intersecting objects"""
        try:
            point_layer = self.pointLayerComboBox.currentLayer()
            surface_layer = self.surfaceLayerComboBox.currentLayer()
            
            if not point_layer or not surface_layer:
                self.log("Error: Please select both input layers")
                return

            # Get options
            export_kml = self.exportKmlCheckBox.isChecked()
            output_dir = self.outputFolderLineEdit.text() if export_kml else None
            use_selection_only = self.useSelectionOnlyCheckBox.isChecked()
            
            from .modules.selection_of_objects import extract_objects
            result = extract_objects(
                self.iface,
                point_layer,
                surface_layer,
                export_kml=export_kml,
                output_dir=output_dir,
                use_selection_only=use_selection_only
            )
            
            if result:
                msg = f"Extracted {result['count']} objects"
                if export_kml:
                    msg += f"\nKML exported to: {output_dir}"
                self.log(msg)
                
        except Exception as e:
            self.log(f"Error during extraction: {str(e)}")
            self.iface.messageBar().pushMessage(
                "Error", str(e), level=Qgis.Critical)
