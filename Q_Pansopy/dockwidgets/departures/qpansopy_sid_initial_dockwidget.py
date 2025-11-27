# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYSIDInitialDockWidget
                            A QGIS plugin module
Procedure Analysis - SID Initial Climb Dockwidget

This dockwidget provides the user interface for calculating SID Initial
Climb protection areas.
                        -------------------
   begin                : 2025
   copyright            : (C) 2025 by FLYGHT7
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
import json
import datetime

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, Qt, QRegExp, QMimeData
from PyQt5.QtGui import QRegExpValidator
from qgis.core import QgsMapLayerProxyModel, Qgis


# Load UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'departures', 'qpansopy_sid_initial_dockwidget.ui'))


class QPANSOPYSIDInitialDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """
    Dockwidget for SID Initial Climb protection areas calculation.
    
    This widget provides input controls for:
        - Runway/DER layer selection
        - Aerodrome and DER elevations
        - PDG, Temperature, IAS
        - Turn altitude, bank angle
        - Wind speed, pilot reaction time
        - Direction toggle (Start→End / End→Start)
    """
    
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """
        Constructor.
        
        Args:
            iface: QGIS interface object.
        """
        super(QPANSOPYSIDInitialDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        
        # Store exact values entered by user
        self.exact_values = {}
        
        # Configure dock widget properties
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFloatable |
            QtWidgets.QDockWidget.DockWidgetClosable
        )
        
        try:
            self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        except Exception:
            pass
        
        self.setMinimumHeight(300)
        
        # Setup layer combobox
        self.runwayLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        
        # Connect signals
        self.calculateButton.clicked.connect(self.calculate)
        self.directionButton.clicked.connect(self.toggle_direction)
        
        # Setup copy buttons
        self.setup_copy_buttons()
        
        # Setup numeric validators
        self.setup_validators()
        
        # Initialize direction state
        self.direction_reversed = False
        self.update_direction_button()
        
        # Log initial message
        self.log("SID Initial Climb module loaded.")
        self.log("Select a runway layer and configure parameters.")

    def setup_validators(self):
        """Configure validators for numeric input fields."""
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        # Apply validators to all numeric spin boxes
        # (Qt SpinBoxes have built-in validation, but LineEdits need this)

    def setup_copy_buttons(self):
        """Configure buttons to copy parameters to clipboard."""
        buttons_layout = QtWidgets.QHBoxLayout()
        
        self.copyParamsWordButton = QtWidgets.QPushButton("Copy for Word", self)
        self.copyParamsWordButton.clicked.connect(self.copy_parameters_for_word)
        self.copyParamsWordButton.setMinimumHeight(30)
        
        self.copyParamsJsonButton = QtWidgets.QPushButton("Copy as JSON", self)
        self.copyParamsJsonButton.clicked.connect(self.copy_parameters_as_json)
        self.copyParamsJsonButton.setMinimumHeight(30)
        
        buttons_layout.addWidget(self.copyParamsWordButton)
        buttons_layout.addWidget(self.copyParamsJsonButton)
        
        buttons_widget = QtWidgets.QWidget(self)
        buttons_widget.setLayout(buttons_layout)
        
        self.verticalLayout.addWidget(buttons_widget)

    def toggle_direction(self):
        """Toggle the direction of calculation."""
        self.direction_reversed = not self.direction_reversed
        self.update_direction_button()
        direction = "End → Start" if self.direction_reversed else "Start → End"
        self.log(f"Direction changed to: {direction}")

    def update_direction_button(self):
        """Update direction button text based on current state."""
        if self.direction_reversed:
            self.directionButton.setText("End → Start")
        else:
            self.directionButton.setText("Start → End")

    def copy_parameters_for_word(self):
        """Copy SID Initial parameters as HTML table for Word."""
        params = self.get_parameters()
        
        param_list = [
            ('Aerodrome Elevation', params['aerodrome_elevation_m'], 'm'),
            ('DER Elevation', params['der_elevation_m'], 'm'),
            ('PDG', params['pdg_percent'], '%'),
            ('Reference Temperature', params['reference_temp_c'], '°C'),
            ('IAS', params['ias_kt'], 'kt'),
            ('Turn Altitude', params['altitude_ft'], 'ft'),
            ('Bank Angle', params['bank_angle_deg'], '°'),
            ('Wind Speed', params['wind_kt'], 'kt'),
            ('Pilot Reaction Time', params['pilot_time_s'], 's'),
            ('Direction', 'End → Start' if self.direction_reversed else 'Start → End', '')
        ]
        
        # Create HTML table
        html = '<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">\n'
        html += '<tr><th colspan="3" style="background-color: #4472C4; color: white; text-align: center; font-weight: bold;">SID INITIAL CLIMB CALCULATION PARAMETERS</th></tr>\n'
        html += '<tr style="background-color: #D9E1F2; font-weight: bold;"><th>PARAMETER</th><th>VALUE</th><th>UNIT</th></tr>\n'
        
        for i, (name, value, unit) in enumerate(param_list):
            bg_color = '#FFFFFF' if i % 2 == 0 else '#F2F2F2'
            html += f'<tr style="background-color: {bg_color};"><td>{name}</td><td style="text-align: right;">{value}</td><td>{unit}</td></tr>\n'
        
        html += '</table>'
        
        # Set both HTML and plain text to clipboard
        mime_data = QMimeData()
        mime_data.setHtml(html)
        
        # Also set plain text as fallback
        plain_text = "SID INITIAL CLIMB CALCULATION PARAMETERS\n"
        plain_text += "=" * 50 + "\n\n"
        for name, value, unit in param_list:
            plain_text += f"{name}\t{value}\t{unit}\n"
        mime_data.setText(plain_text)
        
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setMimeData(mime_data)
        
        self.log("Parameters copied as table for Word.")
        self.iface.messageBar().pushMessage(
            "QPANSOPY", 
            "SID Initial parameters copied as table - paste in Word", 
            level=Qgis.Success
        )

    def copy_parameters_as_json(self):
        """Copy SID Initial parameters in JSON format."""
        params = self.get_parameters()
        
        params_dict = {
            "metadata": {
                "plugin": "QPANSOPY SID Initial Climb",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0"
            },
            "parameters": params
        }
        
        params_json = json.dumps(params_dict, indent=2)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(params_json)
        self.log("Parameters copied to clipboard as JSON.")
        self.iface.messageBar().pushMessage(
            "QPANSOPY", 
            "SID Initial parameters copied to clipboard as JSON", 
            level=Qgis.Success
        )

    def get_parameters(self):
        """
        Get current parameter values from UI.
        
        Returns:
            dict: Dictionary of all parameters.
        """
        return {
            'aerodrome_elevation_m': self.adElevSpinBox.value(),
            'der_elevation_m': self.derElevSpinBox.value(),
            'pdg_percent': self.pdgSpinBox.value(),
            'reference_temp_c': self.tempSpinBox.value(),
            'ias_kt': self.iasSpinBox.value(),
            'altitude_ft': self.altitudeSpinBox.value(),
            'bank_angle_deg': self.bankAngleSpinBox.value(),
            'wind_kt': self.windSpinBox.value(),
            'pilot_time_s': self.pilotTimeSpinBox.value(),
            'reverse_direction': 'YES' if self.direction_reversed else 'NO'
        }

    def log(self, message):
        """
        Add a message to the log.
        
        Args:
            message (str): Message to log.
        """
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def validate_inputs(self):
        """
        Validate user inputs.
        
        Returns:
            bool: True if inputs are valid, False otherwise.
        """
        # Check if layer is selected
        if not self.runwayLayerComboBox.currentLayer():
            self.log("Error: Please select a runway/DER layer")
            return False
        
        runway_layer = self.runwayLayerComboBox.currentLayer()
        
        # Log CRS information
        self.log(f"Runway layer CRS: {runway_layer.crs().authid()}")
        
        # Check for feature selection
        if runway_layer.selectedFeatureCount() == 0:
            self.log("Error: Please select a runway feature in the map")
            self.log("Tip: Use the selection tool to select the runway")
            return False
        
        return True

    def calculate(self):
        """Run the SID Initial Climb calculation."""
        self.log("Starting SID Initial Climb calculation...")
        
        # Validate inputs
        if not self.validate_inputs():
            return
        
        # Get layer and parameters
        runway_layer = self.runwayLayerComboBox.currentLayer()
        params = self.get_parameters()
        
        # Log parameters
        self.log(f"AD Elevation: {params['aerodrome_elevation_m']}m")
        self.log(f"DER Elevation: {params['der_elevation_m']}m")
        self.log(f"PDG: {params['pdg_percent']}%")
        self.log(f"Temperature: {params['reference_temp_c']}°C")
        self.log(f"IAS: {params['ias_kt']}kt")
        self.log(f"Turn Altitude: {params['altitude_ft']}ft")
        self.log(f"Bank Angle: {params['bank_angle_deg']}°")
        self.log(f"Wind: {params['wind_kt']}kt")
        self.log(f"Pilot Time: {params['pilot_time_s']}s")
        
        try:
            # Import and run the calculation module
            from ...modules.departures.sid_initial_climb import run_sid_initial_climb
            
            result = run_sid_initial_climb(
                self.iface,
                runway_layer,
                params,
                log_callback=self.log
            )
            
            # Log results
            if result:
                self.log("=" * 40)
                self.log("Calculation completed successfully!")
                self.log(f"TNA/H Distance: {result['tna_distance_nm']:.4f}NM")
                self.log(f"TAS: {result['tas_kt']:.2f}kt")
                self.log(f"Rate of Turn: {result['rate_of_turn']:.2f}°/s")
                self.log(f"Radius of Turn: {result['radius_of_turn_nm']:.2f}NM")
                self.log("Results copied to clipboard.")
            else:
                self.log("Calculation completed but no results returned.")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())

    def closeEvent(self, event):
        """Handle close event."""
        self.closingPlugin.emit()
        event.accept()
