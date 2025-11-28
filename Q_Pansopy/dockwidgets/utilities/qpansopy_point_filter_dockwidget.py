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
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes, QgsCoordinateReferenceSystem
from qgis.utils import iface
from qgis.core import Qgis
import datetime

# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_point_filter_dockwidget.ui'))


class QPANSOPYPointFilterDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """Constructor."""
        super(QPANSOPYPointFilterDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        
        # Initialize exact_values dictionary
        self.exact_values = {}
        
        # Initialize unit and symbology settings
        self.units = {
            'thrElev': 'm'
        }
        self.higher_color = QColor("red")
        self.lower_color = QColor("green")
        
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.iface = iface
        
        # Hide output/KML/JSON controls not needed for this tool (per #67)
        if hasattr(self, 'outputGroup'):
            self.outputGroup.setVisible(False)
        if hasattr(self, 'exportKmlCheckBox'):
            self.exportKmlCheckBox.setVisible(False)
            self.exportKmlCheckBox.setChecked(False)
        if hasattr(self, 'copyParamsButton'):
            self.copyParamsButton.setVisible(False)
        
        # Setup numeric validator for THR elevation
        self.setup_validators()
        
        # Connect signals for existing UI elements
        self.setup_connections()
        
        # Initialize color button appearances
        self.update_color_button(self.higherColorButton, self.higher_color)
        self.update_color_button(self.lowerColorButton, self.lower_color)
        
        # Add unit combo next to threshold field
        self.setup_thr_elev_with_units()

        # Log initial message
        self.log("Point Filter loaded. Select a point layer with 'elev' field as active layer and set Filter Elevation.")

    def setup_validators(self):
        """Setup validators for numeric inputs"""
        # Create validator for decimal numbers (including negative)
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        if hasattr(self, 'thrElevLineEdit'):
            self.thrElevLineEdit.setValidator(validator)
            self.thrElevLineEdit.textChanged.connect(
                lambda text: self.store_exact_value('thrElev', text))

    def setup_thr_elev_with_units(self):
        """Wrap the Filter Elevation QLineEdit with a unit combo (m/ft) in the same row"""
        if not (hasattr(self, 'thrElevLineEdit') and hasattr(self, 'parametersLayout')):
            return
        # Create unit combo
        self.thrElevUnitCombo = QtWidgets.QComboBox(self)
        self.thrElevUnitCombo.addItems(['m', 'ft'])
        self.thrElevUnitCombo.setCurrentText(self.units.get('thrElev', 'm'))
        self.thrElevUnitCombo.currentTextChanged.connect(lambda u: self.units.__setitem__('thrElev', u))

        # Create a container to hold line edit + unit combo
        container = QtWidgets.QWidget(self)
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(self.thrElevLineEdit)
        h.addWidget(self.thrElevUnitCombo)

        # Replace the original field in the form layout (row 0, column 1)
        try:
            self.parametersLayout.removeWidget(self.thrElevLineEdit)
            self.parametersLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, container)
        except Exception:
            pass

    def setup_connections(self):
        """Setup signal/slot connections"""
        if hasattr(self, 'calculateButton'):
            self.calculateButton.clicked.connect(self.filter_points)
        # Output folder / JSON are hidden; do not wire their actions
        
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

    # Output folder selection removed per #67

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
        # Do not show hex value; keep a neutral label
        if button is self.higherColorButton:
            button.setText("Higher")
        elif button is self.lowerColorButton:
            button.setText("Lower")
        else:
            button.setText("")

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
        
        # Check if Filter elevation is provided
        if not self.thrElevLineEdit.text():
            self.log("Error: Please enter Filter Elevation value")
            return False
        
        # Validate THR elevation is numeric
        try:
            float(self.thrElevLineEdit.text())
        except ValueError:
            self.log("Error: Filter Elevation must be a valid number")
            return False
        
        # Check if layer has 'elev' field
        if active_layer.fields().indexFromName("elev") == -1:
            self.log("Error: Active layer must have an 'elev' field")
            self.iface.messageBar().pushMessage("Error", "The 'elev' field is not present in the active layer", level=Qgis.Warning)
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
        thr_elev_input = self.exact_values.get('thrElev', float(self.thrElevLineEdit.text()))
        unit = self.units.get('thrElev', 'm')
        thr_elev_m = float(thr_elev_input) * 0.3048 if unit == 'ft' else float(thr_elev_input)
        
        # Get symbology parameters
        point_size = self.pointSizeSpinBox.value()
        
        # Log the operation
        self.log(f"Using active layer: {layer.name()}")
        self.log(f"Filter Elevation threshold: {thr_elev_input}{unit} (converted: {thr_elev_m:.3f} m)")
        self.log(f"Symbology - Higher color: {self.higher_color.name()}, Lower color: {self.lower_color.name()}, Size: {point_size}")
        
        try:
            # Import and run the point filter module
            from ...modules.utilities.point_filter import filter_points_by_elevation
            result = filter_points_by_elevation(self.iface, layer, thr_elev_m, None, 
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
                
                # KML/JSON export removed per #67
                
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

    # JSON copy functionality removed per #67

    # KML export functionality removed per #67

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
