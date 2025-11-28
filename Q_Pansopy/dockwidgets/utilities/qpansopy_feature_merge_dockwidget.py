# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYFeatureMergeDockWidget
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - Feature Merge Module
                        -------------------
   begin                : 2025-07-29
   git sha              : $Format:%H$
   copyright            : (C) 2025 by QPANSOPY Team
   email                : support@qpansopy.com
***************************************************************************/

/***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************/
"""

import os
from PyQt5 import QtGui, QtWidgets, uic, QtCore
from PyQt5.QtCore import pyqtSignal, QRegExp
from PyQt5.QtGui import QRegExpValidator, QColor
from PyQt5.QtWidgets import QColorDialog
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes, QgsCoordinateReferenceSystem, QgsMapLayerProxyModel, QgsVectorFileWriter
from qgis.gui import QgsMapLayerComboBox
from qgis.utils import iface
from qgis.core import Qgis
import json
import datetime

# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_feature_merge_dockwidget.ui'))


class QPANSOPYFeatureMergeDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """Constructor."""
        super(QPANSOPYFeatureMergeDockWidget, self).__init__(iface.mainWindow())
        
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.iface = iface
        
        # Make the dock widget floating by default
        
        # Set default output folder
        if hasattr(self, 'outputFolderLineEdit'):
            self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Hide and disable KML export checkbox by default
        if hasattr(self, 'exportKmlCheckBox'):
            self.exportKmlCheckBox.setVisible(False)
            self.exportKmlCheckBox.setChecked(False)
        
        # Connect signals for existing UI elements
        self.setup_connections()
        
        # Log initial message
        self.log("Feature Merge loaded. Select 2+ vector layers in Layers panel and click Merge Layers.")

    def setup_connections(self):
        """Setup signal/slot connections"""
        if hasattr(self, 'calculateButton'):
            self.calculateButton.clicked.connect(self.merge_layers)
        if hasattr(self, 'browseButton'):
            self.browseButton.clicked.connect(self.browse_output_folder)
        if hasattr(self, 'copyParamsButton'):
            self.copyParamsButton.clicked.connect(self.copy_parameters_as_json)
        
        # Note: exportKmlCheckBox doesn't need connection - it's checked during merge execution

    def get_desktop_path(self):
        """Get desktop path for default output folder"""
        try:
            import os
            return os.path.join(os.path.expanduser("~"), "Desktop")
        except:
            return ""

    def browse_output_folder(self):
        """Browse for output folder"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.outputFolderLineEdit.text())
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        """Log a message"""
        if hasattr(self, 'logTextEdit'):
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.logTextEdit.append(f"[{timestamp}] {message}")
        else:
            print(f"Feature Merge: {message}")

    def validate_inputs(self):
        """Validate user inputs"""
        # Get selected layers
        selected_layers = self.iface.layerTreeView().selectedLayers()
        
        # Filter to only vector layers
        selected_layers = [layer for layer in selected_layers if isinstance(layer, QgsVectorLayer)]
        
        # Check if at least 2 layers are selected
        if len(selected_layers) < 2:
            self.log("Error: Select at least two vector layers in the Layers panel.")
            self.iface.messageBar().pushMessage("Error", "Select at least two vector layers in the Layers panel.", level=Qgis.Warning)
            return False, []
        
        # Check geometry and CRS compatibility
        geom_type = selected_layers[0].wkbType()
        crs = selected_layers[0].crs()
        
        for i, layer in enumerate(selected_layers[1:], 1):
            if layer.wkbType() != geom_type:
                self.log(f"Error: Geometry type mismatch between layer '{selected_layers[0].name()}' and '{layer.name()}'")
                self.iface.messageBar().pushMessage("Error", f"Geometry types differ between selected layers", level=Qgis.Warning)
                return False, []
            if layer.crs() != crs:
                self.log(f"Error: CRS mismatch between layer '{selected_layers[0].name()}' and '{layer.name()}'")
                self.iface.messageBar().pushMessage("Error", f"CRS differ between selected layers", level=Qgis.Warning)
                return False, []
        
        # Check if layer name is provided
        if not self.layerNameLineEdit.text().strip():
            self.log("Error: Please enter a name for the merged layer")
            return False, []
        
        # Check if output folder exists
        output_folder = self.outputFolderLineEdit.text()
        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder)
                self.log(f"Created output folder: {output_folder}")
            except Exception as e:
                self.log(f"Error creating output folder: {str(e)}")
                return False, []
        
        return True, selected_layers

    def merge_layers(self):
        """Merge selected vector layers"""
        self.log("Starting layer merging...")
        
        # Validate inputs
        is_valid, selected_layers = self.validate_inputs()
        if not is_valid:
            return
        
        # Get parameters
        merged_layer_name = self.layerNameLineEdit.text().strip()
        output_dir = self.outputFolderLineEdit.text()
        
        # Check if KML export is requested
        export_kml = self.exportKmlCheckBox.isChecked() if hasattr(self, 'exportKmlCheckBox') else False
        
        # Log the operation
        self.log(f"Merging {len(selected_layers)} layers:")
        for layer in selected_layers:
            self.log(f"  - {layer.name()} ({layer.featureCount()} features)")
        
        try:
            # Import and run the feature merge module
            from ...modules.utilities.feature_merge import merge_selected_layers
            result = merge_selected_layers(self.iface, selected_layers, merged_layer_name, output_dir)
            
            # Log results
            if result:
                self.log(f"Layer merging completed successfully!")
                self.log(f"Merged layer: {result.get('merged_layer').name()}")
                self.log(f"Total features: {result.get('total_features', 0)}")
                self.log(f"Geometry type: {result.get('geometry_type', 'Unknown')}")
                self.log(f"CRS: {result.get('crs', 'Unknown')}")
                
                # Log individual layer contributions
                for layer_name, count in result.get('layer_counts', {}).items():
                    self.log(f"  {layer_name}: {count} features")
                
                # Handle KML export if requested
                if export_kml:
                    try:
                        self.export_results_to_kml(result.get('merged_layer'), output_dir)
                    except Exception as kml_error:
                        self.log(f"Warning: KML export failed: {str(kml_error)}")
                
                self.log("You can now use the 'Copy Parameters as JSON' button to copy the parameters for documentation.")
                
                # Show success message
                self.iface.messageBar().pushMessage("QPANSOPY", 
                    f"Layer merging completed: {result.get('total_features', 0)} features merged", 
                    level=Qgis.Success)
            else:
                self.log("Layer merging completed but no results were returned.")
                
        except Exception as e:
            self.log(f"Error during layer merging: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage("Error", f"Layer merging failed: {str(e)}", level=Qgis.Critical)

    def export_results_to_kml(self, merged_layer, output_dir):
        """Export merged results to KML format"""
        if not output_dir or not os.path.exists(output_dir):
            output_dir = self.get_desktop_path()
        
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Export merged layer
            if merged_layer:
                kml_path = os.path.join(output_dir, f"feature_merge_{timestamp}.kml")
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    merged_layer,
                    kml_path,
                    "utf-8",
                    merged_layer.crs(),
                    "KML"
                )
                if error[0] == QgsVectorFileWriter.NoError:
                    self.log(f"Merged layer exported to KML: {kml_path}")
                    self.iface.messageBar().pushMessage("QPANSOPY", 
                        f"Feature Merge results exported to KML", 
                        level=Qgis.Success)
                else:
                    self.log(f"Error exporting merged layer: {error[1]}")
            else:
                self.log("Warning: No merged layer to export.")
                
        except Exception as e:
            self.log(f"Error during KML export: {str(e)}")
            raise e

    def copy_parameters_as_json(self):
        """Copy current parameters to clipboard as JSON"""
        # Get selected layers
        selected_layers = self.iface.layerTreeView().selectedLayers()
        selected_layers = [layer for layer in selected_layers if isinstance(layer, QgsVectorLayer)]
        
        params_dict = {
            "metadata": {
                "plugin": "QPANSOPY Feature Merge",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0"
            },
            "parameters": {
                'selected_layers': [layer.name() for layer in selected_layers],
                'merged_layer_name': self.layerNameLineEdit.text(),
                'output_folder': self.outputFolderLineEdit.text(),
                'kml_export': self.exportKmlCheckBox.isChecked() if hasattr(self, 'exportKmlCheckBox') else False
            },
            "processing_info": {
                'description': 'Merges multiple vector layers into a single layer',
                'requirements': 'Selected layers must have same geometry type and CRS',
                'output': 'Single merged layer with union of all fields',
                'features': 'All features from input layers combined'
            }
        }
        
        if selected_layers:
            params_dict["layer_info"] = {
                'geometry_type': selected_layers[0].wkbType(),
                'crs': selected_layers[0].crs().authid(),
                'total_layers': len(selected_layers),
                'total_features': sum(layer.featureCount() for layer in selected_layers)
            }
        
        params_json = json.dumps(params_dict, indent=2)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(params_json)
        self.log("Feature Merge parameters copied to clipboard as JSON.")
        self.iface.messageBar().pushMessage("QPANSOPY", "Feature Merge parameters copied to clipboard as JSON", level=Qgis.Success)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
