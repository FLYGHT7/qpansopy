# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYPointFilterDockWidget
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - Point Filter Module
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
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_point_filter_dockwidget.ui'))


class QPANSOPYPointFilterDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """Constructor."""
        super(QPANSOPYPointFilterDockWidget, self).__init__(iface.mainWindow())
        
        # Initialize exact_values dictionary
        self.exact_values = {}
        
        # Initialize symbology settings
        self.higher_color = QColor("red")
        self.lower_color = QColor("green")
        
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.iface = iface
        
        # Set default output folder
        if hasattr(self, 'outputFolderLineEdit'):
            self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Setup numeric validator for THR elevation
        self.setup_validators()
        
        # Connect signals for existing UI elements
        self.setup_connections()
        
        # Initialize color button appearances
        self.update_color_button(self.higherColorButton, self.higher_color)
        self.update_color_button(self.lowerColorButton, self.lower_color)
        
        # Hide and disable KML export checkbox by default
        if hasattr(self, 'exportKmlCheckBox'):
            self.exportKmlCheckBox.setVisible(False)
            self.exportKmlCheckBox.setChecked(False)
        
        # Log initial message
        self.log("Point Filter loaded. Select a point layer with 'elev' field as active layer and set THR elevation.")

    def setup_validators(self):
        """Setup validators for numeric inputs"""
        # Create validator for decimal numbers (including negative)
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        if hasattr(self, 'thrElevLineEdit'):
            self.thrElevLineEdit.setValidator(validator)
            self.thrElevLineEdit.textChanged.connect(
                lambda text: self.store_exact_value('thrElev', text))

    def setup_connections(self):
        """Setup signal/slot connections"""
        if hasattr(self, 'calculateButton'):
            self.calculateButton.clicked.connect(self.filter_points)
        if hasattr(self, 'browseButton'):
            self.browseButton.clicked.connect(self.browse_output_folder)
        if hasattr(self, 'copyParamsButton'):
            self.copyParamsButton.clicked.connect(self.copy_parameters_as_json)
        
        # Note: exportKmlCheckBox doesn't need connection - it's checked during filter execution
        
        # Connect symbology controls (these should always exist in the UI)
        self.higherColorButton.clicked.connect(self.choose_higher_color)
        self.lowerColorButton.clicked.connect(self.choose_lower_color)

    def store_exact_value(self, key, value):
        """Store exact value for precise calculations"""
        try:
            self.exact_values[key] = float(value)
        except ValueError:
            if key in self.exact_values:
                del self.exact_values[key]

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

    def choose_higher_color(self):
        """Choose color for points above threshold"""
        color = QColorDialog.getColor(self.higher_color, self, "Choose color for higher points")
        if color.isValid():
            self.higher_color = color
            self.update_color_button(self.higherColorButton, color)
            self.log(f"Higher points color changed to: {color.name()}")

    def choose_lower_color(self):
        """Choose color for points below threshold"""
        color = QColorDialog.getColor(self.lower_color, self, "Choose color for lower points")
        if color.isValid():
            self.lower_color = color
            self.update_color_button(self.lowerColorButton, color)
            self.log(f"Lower points color changed to: {color.name()}")

    def update_color_button(self, button, color):
        """Update button appearance with selected color"""
        # Determine text color based on background brightness
        text_color = "white" if color.lightness() < 128 else "black"
        button.setStyleSheet(f"background-color: {color.name()}; color: {text_color};")
        button.setText(color.name().upper())

    def log(self, message):
        """Log a message"""
        if hasattr(self, 'logTextEdit'):
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.logTextEdit.append(f"[{timestamp}] {message}")
        else:
            print(f"Point Filter: {message}")

    def validate_inputs(self):
        """Validate user inputs"""
        # Get active layer instead of selected layer
        active_layer = self.iface.activeLayer()
        
        # Check if there's an active layer
        if not active_layer:
            self.log("Error: No active layer. Please select a layer in the Layers panel.")
            self.iface.messageBar().pushMessage("Error", "No active layer selected. Please select a layer in the Layers panel.", level=Qgis.Warning)
            return False
        
        # Check if active layer is a point layer
        if active_layer.type() != QgsVectorLayer.VectorLayer or active_layer.geometryType() != QgsWkbTypes.PointGeometry:
            self.log("Error: Active layer must be a point layer")
            self.iface.messageBar().pushMessage("Error", "Active layer must be a point layer", level=Qgis.Warning)
            return False
        
        # Check if THR elevation is provided
        if not self.thrElevLineEdit.text():
            self.log("Error: Please enter THR Elevation value")
            return False
        
        # Validate THR elevation is numeric
        try:
            float(self.thrElevLineEdit.text())
        except ValueError:
            self.log("Error: THR Elevation must be a valid number")
            return False
        
        # Check if layer has 'elev' field
        if active_layer.fields().indexFromName("elev") == -1:
            self.log("Error: Active layer must have an 'elev' field")
            self.iface.messageBar().pushMessage("Error", "The 'elev' field is not present in the active layer", level=Qgis.Warning)
            return False
        
        # Check if output folder exists
        output_folder = self.outputFolderLineEdit.text()
        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder)
                self.log(f"Created output folder: {output_folder}")
            except Exception as e:
                self.log(f"Error creating output folder: {str(e)}")
                return False
        
        return True

    def filter_points(self):
        """Filter points based on THR elevation"""
        self.log("Starting point filtering...")
        
        # Validate inputs
        if not self.validate_inputs():
            return
        
        # Get active layer instead of selected layer
        layer = self.iface.activeLayer()
        thr_elev = self.exact_values.get('thrElev', float(self.thrElevLineEdit.text()))
        output_dir = self.outputFolderLineEdit.text()
        
        # Get symbology parameters
        point_size = self.pointSizeSpinBox.value()
        
        # Check if KML export is requested
        export_kml = self.exportKmlCheckBox.isChecked() if hasattr(self, 'exportKmlCheckBox') else False
        
        # Log the operation
        self.log(f"Using active layer: {layer.name()}")
        self.log(f"THR Elevation threshold: {thr_elev}m")
        self.log(f"Symbology - Higher color: {self.higher_color.name()}, Lower color: {self.lower_color.name()}, Size: {point_size}")
        
        try:
            # Import and run the point filter module
            from ...modules.utilities.point_filter import filter_points_by_elevation
            result = filter_points_by_elevation(self.iface, layer, thr_elev, output_dir, 
                                               self.higher_color, self.lower_color, point_size)
            
            # Log results
            if result:
                self.log(f"Point filtering completed successfully!")
                self.log(f"Points above threshold ({self.higher_color.name()}): {result.get('higher_count', 0)} features")
                self.log(f"Points below threshold ({self.lower_color.name()}): {result.get('lower_count', 0)} features")
                self.log(f"Higher layer: {result.get('higher_layer').name()}")
                self.log(f"Lower layer: {result.get('lower_layer').name()}")
                self.log("Layers added to project with custom symbology")
                self.log("Fields added: x_dist, y_dist, z_height (elevation - threshold)")
                
                # Handle KML export if requested
                if export_kml:
                    try:
                        self.export_results_to_kml(result.get('higher_layer'), result.get('lower_layer'), output_dir)
                    except Exception as kml_error:
                        self.log(f"Warning: KML export failed: {str(kml_error)}")
                
                self.log("You can now use the 'Copy Parameters as JSON' button to copy the parameters for documentation.")
                
                # Show success message
                self.iface.messageBar().pushMessage("QPANSOPY", 
                    f"Point filtering completed: {result.get('higher_count', 0)} above, {result.get('lower_count', 0)} below threshold", 
                    level=Qgis.Success)
            else:
                self.log("Point filtering completed but no results were returned.")
                
        except Exception as e:
            self.log(f"Error during point filtering: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage("Error", f"Point filtering failed: {str(e)}", level=Qgis.Critical)

    def copy_parameters_as_json(self):
        """Copy current parameters to clipboard as JSON"""
        # Get active layer
        active_layer = self.iface.activeLayer()
        point_size = self.pointSizeSpinBox.value()
        
        params_dict = {
            "metadata": {
                "plugin": "QPANSOPY Point Filter",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0"
            },
            "parameters": {
                'active_layer_name': active_layer.name() if active_layer else None,
                'layer_type': 'Point Layer' if active_layer else None,
                'thr_elevation': self.exact_values.get('thrElev', self.thrElevLineEdit.text()),
                'output_folder': self.outputFolderLineEdit.text()
            },
            "symbology": {
                'higher_color': self.higher_color.name(),
                'lower_color': self.lower_color.name(),
                'point_size': point_size
            },
            "processing_info": {
                'description': 'Filters points based on THR (Threshold) elevation',
                'higher_points': f'Points with elevation >= threshold (colored {self.higher_color.name()})',
                'lower_points': f'Points with elevation < threshold (colored {self.lower_color.name()})',
                'calculated_fields': ['x_dist', 'y_dist', 'z_height'],
                'z_height_formula': 'elevation - thr_elevation'
            }
        }
        params_json = json.dumps(params_dict, indent=2)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(params_json)
        self.log("Point Filter parameters copied to clipboard as JSON.")
        self.iface.messageBar().pushMessage("QPANSOPY", "Point Filter parameters copied to clipboard as JSON", level=Qgis.Success)

    def export_results_to_kml(self, higher_layer, lower_layer, output_dir):
        """Export filtered results to KML format"""
        if not output_dir or not os.path.exists(output_dir):
            output_dir = self.get_desktop_path()
        
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            exported_files = []
            
            # Export higher layer if exists
            if higher_layer:
                higher_kml_path = os.path.join(output_dir, f"point_filter_higher_{timestamp}.kml")
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    higher_layer,
                    higher_kml_path,
                    "utf-8",
                    higher_layer.crs(),
                    "KML"
                )
                if error[0] == QgsVectorFileWriter.NoError:
                    exported_files.append(higher_kml_path)
                    self.log(f"Higher points exported to KML: {higher_kml_path}")
                else:
                    self.log(f"Error exporting higher layer: {error[1]}")
            
            # Export lower layer if exists
            if lower_layer:
                lower_kml_path = os.path.join(output_dir, f"point_filter_lower_{timestamp}.kml")
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    lower_layer,
                    lower_kml_path,
                    "utf-8",
                    lower_layer.crs(),
                    "KML"
                )
                if error[0] == QgsVectorFileWriter.NoError:
                    exported_files.append(lower_kml_path)
                    self.log(f"Lower points exported to KML: {lower_kml_path}")
                else:
                    self.log(f"Error exporting lower layer: {error[1]}")
            
            if exported_files:
                self.log(f"KML export completed successfully! {len(exported_files)} file(s) exported.")
                self.iface.messageBar().pushMessage("QPANSOPY", 
                    f"Point Filter results exported to KML: {len(exported_files)} file(s)", 
                    level=Qgis.Success)
            else:
                self.log("Warning: No KML files were exported.")
                
        except Exception as e:
            self.log(f"Error during KML export: {str(e)}")
            raise e

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
