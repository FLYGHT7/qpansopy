# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYWindSpiralDockWidget
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - Wind Spiral Module
                        -------------------
   begin                : 2023-04-29
   git sha              : $Format:%H$
   copyright            : (C) 2023 by Your Name
   email                : your.email@example.com
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
from PyQt5.QtCore import pyqtSignal, QFileInfo, Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtWidgets import QMessageBox
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes, QgsCoordinateReferenceSystem, QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox  # Importar QgsMapLayerComboBox
from qgis.utils import iface
from qgis.core import Qgis
import json
import datetime

# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_wind_spiral_dockwidget.ui'))


class QPANSOPYWindSpiralDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """Constructor."""
        super(QPANSOPYWindSpiralDockWidget, self).__init__(iface.mainWindow())
        
        # Initialize exact_values dictionary BEFORE setupUi to prevent AttributeError
        self.exact_values = {}
        
        # Initialize ISA calculation metadata
        self.isa_calculation_metadata = {
            'method': 'manual',  # Default to manual input
            'isa_temperature': None,
            'elevation_feet': None,
            'elevation_original': None,
            'elevation_unit': None,
            'temperature_reference': None,
            'isa_variation_calculated': None
        }
        
        # Initialize units dictionary
        self.units = {
            'adElev': 'ft',
            'altitude': 'ft'
        }
        
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.iface = iface
        
        # Setup layer combos (these should already exist from UI file)
        if hasattr(self, 'pointLayerComboBox'):
            self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        if hasattr(self, 'referenceLayerComboBox'):
            self.referenceLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        
        # Set default output folder
        if hasattr(self, 'outputFolderLineEdit'):
            self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Connect signals for existing UI elements
        if hasattr(self, 'calculateButton'):
            self.calculateButton.clicked.connect(self.calculate)
        if hasattr(self, 'browseButton'):
            self.browseButton.clicked.connect(self.browse_output_folder)
        if hasattr(self, 'copyParamsButton'):
            self.copyParamsButton.clicked.connect(self.copy_parameters_for_word)
        
        # Setup parameter input fields dynamically
        self.setup_dynamic_parameters()
        
        # Log initial message
        self.log("Wind Spiral generator loaded. Set parameters and click Calculate.")

    def setup_dynamic_parameters(self):
        """Setup parameter input fields that aren't defined in the UI file"""
        # Find the form layout (should exist in UI file)
        if not hasattr(self, 'formLayout'):
            # If formLayout doesn't exist, we need to create it
            self.log("Warning: formLayout not found in UI, creating dynamically")
            return
        
        # Create validator for numeric inputs
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        # Aerodrome Elevation with unit selector
        self.adElevLineEdit = QtWidgets.QLineEdit(self)
        self.adElevLineEdit.setValidator(validator)
        self.adElevLineEdit.setText("0")
        self.adElevLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('adElev', text))
        self.adElevLineEdit.setMinimumHeight(28)
        
        self.adElevUnitCombo = QtWidgets.QComboBox(self)
        self.adElevUnitCombo.addItems(['ft', 'm'])
        self.adElevUnitCombo.currentTextChanged.connect(
            lambda text: self.update_unit('adElev', text))
        self.adElevUnitCombo.setMinimumHeight(28)
        self.adElevUnitCombo.setFixedWidth(45)
        
        adElevContainer = QtWidgets.QWidget(self)
        adElevLayout = QtWidgets.QHBoxLayout(adElevContainer)
        adElevLayout.setContentsMargins(0, 0, 0, 0)
        adElevLayout.setSpacing(5)
        adElevLayout.addWidget(self.adElevLineEdit)
        adElevLayout.addWidget(self.adElevUnitCombo)
        
        self.formLayout.addRow("Aerodrome Elevation:", adElevContainer)
        
        # Temperature Reference
        self.tempRefLineEdit = QtWidgets.QLineEdit(self)
        self.tempRefLineEdit.setValidator(validator)
        self.tempRefLineEdit.setText("15")
        self.tempRefLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('tempRef', text))
        self.tempRefLineEdit.setMinimumHeight(28)
        self.formLayout.addRow("Temperature Reference (°C):", self.tempRefLineEdit)
        
        # ISA Variation with Calculator Button
        isa_layout = QtWidgets.QHBoxLayout()
        self.isaVarLineEdit = QtWidgets.QLineEdit(self)
        self.isaVarLineEdit.setValidator(validator)
        self.isaVarLineEdit.setText("0.00000")
        self.isaVarLineEdit.textChanged.connect(
            lambda text: self.handle_isa_manual_change(text))
        self.isaVarLineEdit.setMinimumHeight(28)
        
        # ISA Calculator Button with calculator icon
        self.isaCalculatorButton = QtWidgets.QPushButton(self)
        self.isaCalculatorButton.setText("🧮")  # Calculator emoji as icon
        self.isaCalculatorButton.setToolTip("Calculate ISA Variation automatically\nfrom Aerodrome Elevation and Temperature Reference")
        self.isaCalculatorButton.setMaximumWidth(40)
        self.isaCalculatorButton.setMinimumHeight(28)
        self.isaCalculatorButton.clicked.connect(self.calculate_isa_variation)
        
        isa_layout.addWidget(self.isaVarLineEdit)
        isa_layout.addWidget(self.isaCalculatorButton)
        isa_widget = QtWidgets.QWidget()
        isa_widget.setLayout(isa_layout)
        self.formLayout.addRow("ISA Variation (°C):", isa_widget)
        
        # IAS
        self.IASLineEdit = QtWidgets.QLineEdit(self)
        self.IASLineEdit.setValidator(validator)
        self.IASLineEdit.setText("205")
        self.IASLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('IAS', text))
        self.IASLineEdit.setMinimumHeight(28)
        self.formLayout.addRow("IAS (kt):", self.IASLineEdit)
        
        # Altitude with unit selector
        self.altitudeLineEdit = QtWidgets.QLineEdit(self)
        self.altitudeLineEdit.setValidator(validator)
        self.altitudeLineEdit.setText("800")
        self.altitudeLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('altitude', text))
        self.altitudeLineEdit.setMinimumHeight(28)
        
        self.altitudeUnitCombo = QtWidgets.QComboBox(self)
        self.altitudeUnitCombo.addItems(['ft', 'm'])
        self.altitudeUnitCombo.currentTextChanged.connect(
            lambda text: self.update_unit('altitude', text))
        self.altitudeUnitCombo.setMinimumHeight(28)
        self.altitudeUnitCombo.setFixedWidth(45)
        
        altitudeContainer = QtWidgets.QWidget(self)
        altitudeLayout = QtWidgets.QHBoxLayout(altitudeContainer)
        altitudeLayout.setContentsMargins(0, 0, 0, 0)
        altitudeLayout.setSpacing(5)
        altitudeLayout.addWidget(self.altitudeLineEdit)
        altitudeLayout.addWidget(self.altitudeUnitCombo)
        
        self.formLayout.addRow("Altitude:", altitudeContainer)
        
        # Bank Angle
        self.bankAngleLineEdit = QtWidgets.QLineEdit(self)
        self.bankAngleLineEdit.setValidator(validator)
        self.bankAngleLineEdit.setText("15")
        self.bankAngleLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('bankAngle', text))
        self.bankAngleLineEdit.setMinimumHeight(28)
        self.formLayout.addRow("Bank Angle (°):", self.bankAngleLineEdit)
        
        # Wind Speed
        self.windSpeedLineEdit = QtWidgets.QLineEdit(self)
        self.windSpeedLineEdit.setValidator(validator)
        self.windSpeedLineEdit.setText("30")
        self.windSpeedLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('w', text))
        self.windSpeedLineEdit.setMinimumHeight(28)
        self.formLayout.addRow("Wind Speed (kt):", self.windSpeedLineEdit)
        
        # Turn Direction
        self.turnDirectionCombo = QtWidgets.QComboBox(self)
        self.turnDirectionCombo.addItems(['R', 'L'])
        self.turnDirectionCombo.setMinimumHeight(28)
        self.formLayout.addRow("Turn Direction:", self.turnDirectionCombo)
        
        # Show Points checkbox
        self.showPointsCheckBox = QtWidgets.QCheckBox("Show intermediate points", self)
        self.formLayout.addRow("", self.showPointsCheckBox)
        
        # Export KML checkbox
        self.exportKmlCheckBox = QtWidgets.QCheckBox("Export KML", self)
        self.formLayout.addRow("", self.exportKmlCheckBox)
        
        # Output folder
        if not hasattr(self, 'outputFolderLineEdit'):
            self.outputFolderLineEdit = QtWidgets.QLineEdit(self)
            self.outputFolderLineEdit.setText(self.get_desktop_path())
            self.formLayout.addRow("Output Folder:", self.outputFolderLineEdit)
        
        # Export KML Checkbox (if not in UI)
        if not hasattr(self, 'exportKmlCheckBox'):
            self.exportKmlCheckBox = QtWidgets.QCheckBox(self)
            self.exportKmlCheckBox.setChecked(True)
            
    def store_exact_value(self, key, value):
        """Store exact value for precise calculations"""
        try:
            self.exact_values[key] = float(value)
        except ValueError:
            if key in self.exact_values:
                del self.exact_values[key]
    
    def handle_isa_manual_change(self, text):
        """Handle manual changes to ISA Variation field"""
        self.store_exact_value('isaVar', text)
        # Reset to manual input when user types manually
        self.isa_calculation_metadata['method'] = 'manual'
        self.isa_calculation_metadata['isa_temperature'] = None
        self.isa_calculation_metadata['elevation_feet'] = None
        self.isa_calculation_metadata['elevation_original'] = None
        self.isa_calculation_metadata['elevation_unit'] = None
        self.isa_calculation_metadata['temperature_reference'] = None
        self.isa_calculation_metadata['isa_variation_calculated'] = None
    
    def update_unit(self, param, unit):
        """Update unit for parameter"""
        self.units[param] = unit

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
            print(f"Wind Spiral: {message}")

    def copy_parameters_for_word(self):
        """Copiar los parámetros en formato tabla para Word"""
        params_text = "QPANSOPY WIND SPIRAL CALCULATION PARAMETERS\n"
        params_text += "=" * 50 + "\n\n"
        params_text += "PARAMETER\t\t\tVALUE\t\tUNIT\n"
        params_text += "-" * 50 + "\n"
        param_names = {
            'adElev': 'Aerodrome Elevation',
            'tempRef': 'Temperature Reference',
            'isaVar': 'ISA Variation',
            'IAS': 'IAS',
            'altitude': 'Altitude',
            'bankAngle': 'Bank Angle',
            'w': 'Wind Speed',
            'turn_direction': 'Turn Direction',
            'show_points': 'Show Construction Points'
        }
        # Usar valores actuales
        params = {
            'adElev': self.exact_values.get('adElev', self.adElevLineEdit.text()),
            'adElev_unit': self.units.get('adElev', 'ft'),
            'tempRef': self.exact_values.get('tempRef', self.tempRefLineEdit.text()),
            'isaVar': self.exact_values.get('isaVar', self.isaVarLineEdit.text()),
            'IAS': self.exact_values.get('IAS', self.IASLineEdit.text()),
            'altitude': self.exact_values.get('altitude', self.altitudeLineEdit.text()),
            'altitude_unit': self.units.get('altitude', 'ft'),
            'bankAngle': self.exact_values.get('bankAngle', self.bankAngleLineEdit.text()),
            'w': self.exact_values.get('w', self.windSpeedLineEdit.text()),
            'turn_direction': self.turnDirectionCombo.currentText(),
            'show_points': self.showPointsCheckBox.isChecked()
        }
        for key in ['adElev', 'tempRef', 'isaVar', 'IAS', 'altitude', 'bankAngle', 'w', 'turn_direction', 'show_points']:
            display_name = param_names.get(key, key.replace('_', ' ').title())
            value = params[key]
            unit = ""
            if key == 'adElev':
                unit = params['adElev_unit']
            elif key == 'altitude':
                unit = params['altitude_unit']
            elif key == 'tempRef' or key == 'isaVar':
                unit = "°C"
            elif key == 'IAS':
                unit = "kt"
            elif key == 'bankAngle':
                unit = "°"
            elif key == 'w':
                unit = "kt"
            params_text += f"{display_name:<25}\t{value}\t\t{unit}\n"
        
        # Add ISA calculation details if available
        if self.isa_calculation_metadata['method'] == 'calculated':
            params_text += "\n" + "=" * 50 + "\n"
            params_text += "ISA CALCULATION DETAILS\n"
            params_text += "-" * 50 + "\n"
            params_text += f"Method:\t\t\tCalculated\n"
            params_text += f"ISA Temperature:\t\t{self.isa_calculation_metadata['isa_temperature']:.5f}\t\t°C\n"
            params_text += f"Elevation Used:\t\t{self.isa_calculation_metadata['elevation_feet']:.0f}\t\tft\n"
        else:
            params_text += "\n" + "=" * 50 + "\n"
            params_text += "ISA CALCULATION DETAILS\n"
            params_text += "-" * 50 + "\n"
            params_text += f"Method:\t\t\tManual Input\n"
        
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(params_text)
        self.log("Wind Spiral parameters copied to clipboard in Word format. You can now paste them into Word.")
        self.iface.messageBar().pushMessage("QPANSOPY", "Wind Spiral parameters copied to clipboard in Word format", level=Qgis.Success)

    def copy_parameters_as_json(self):
        """Copiar los parámetros actuales al portapapeles en formato JSON"""
        params_dict = {
            "metadata": {
                "plugin": "QPANSOPY Wind Spiral",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0"
            },
            "parameters": {
                'adElev': self.exact_values.get('adElev', self.adElevLineEdit.text()),
                'adElev_unit': self.units.get('adElev', 'ft'),
                'tempRef': self.exact_values.get('tempRef', self.tempRefLineEdit.text()),
                'isaVar': self.exact_values.get('isaVar', self.isaVarLineEdit.text()),
                'IAS': self.exact_values.get('IAS', self.IASLineEdit.text()),
                'altitude': self.exact_values.get('altitude', self.altitudeLineEdit.text()),
                'altitude_unit': self.units.get('altitude', 'ft'),
                'bankAngle': self.exact_values.get('bankAngle', self.bankAngleLineEdit.text()),
                'w': self.exact_values.get('w', self.windSpeedLineEdit.text()),
                'turnDirection': self.turnDirectionCombo.currentText(),
                'showPoints': self.showPointsCheckBox.isChecked()
            },
            "isa_calculation": {
                'method': self.isa_calculation_metadata['method'],
                'isa_temperature': self.isa_calculation_metadata['isa_temperature'],
                'elevation_feet': self.isa_calculation_metadata['elevation_feet'],
                'elevation_original': self.isa_calculation_metadata['elevation_original'],
                'elevation_unit': self.isa_calculation_metadata['elevation_unit'],
                'temperature_reference': self.isa_calculation_metadata['temperature_reference'],
                'isa_variation_calculated': self.isa_calculation_metadata['isa_variation_calculated'],
                'isa_variation_used': self.exact_values.get('isaVar', self.isaVarLineEdit.text())
            }
        }
        params_json = json.dumps(params_dict, indent=2)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(params_json)
        self.log("Wind Spiral parameters copied to clipboard as JSON. You can now paste them into a JSON editor or processing tool.")
        self.iface.messageBar().pushMessage("QPANSOPY", "Wind Spiral parameters copied to clipboard as JSON", level=Qgis.Success)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def validate_inputs(self):
        """Validate user inputs"""
        # Check if layers are selected
        if not self.pointLayerComboBox.currentLayer():
            self.log("Error: Please select a point layer")
            return False
        
        if not self.referenceLayerComboBox.currentLayer():
            self.log("Error: Please select a reference layer")
            return False
        
        # Check if point layer is in WGS84
        point_layer = self.pointLayerComboBox.currentLayer()
        if not point_layer.crs().authid() == 'EPSG:4326':
            self.log("Warning: Point layer should be in WGS84 (EPSG:4326)")
            # Continue anyway, but warn the user
        
        # Check if reference layer is in a projected CRS
        reference_layer = self.referenceLayerComboBox.currentLayer()
        if reference_layer.crs().isGeographic():
            self.log("Warning: Reference layer should be in a projected coordinate system")
            # Continue anyway, but warn the user
        
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

    def calculate_isa_variation(self):
        """Calculate ISA Variation automatically from Aerodrome Elevation and Temperature Reference"""
        try:
            # Get aerodrome elevation and temperature reference
            ad_elev_text = self.exact_values.get('adElev', self.adElevLineEdit.text())
            temp_ref_text = self.exact_values.get('tempRef', self.tempRefLineEdit.text())
            
            # Validate inputs
            if not ad_elev_text or not temp_ref_text:
                self.log("Error: Please enter both Aerodrome Elevation and Temperature Reference before calculating ISA Variation")
                self.iface.messageBar().pushMessage("Error", "Please enter both Aerodrome Elevation and Temperature Reference", level=Qgis.Warning)
                return
                
            try:
                ad_elev = float(ad_elev_text)
                temp_ref = float(temp_ref_text)
            except ValueError:
                self.log("Error: Invalid numeric values for Aerodrome Elevation or Temperature Reference")
                self.iface.messageBar().pushMessage("Error", "Invalid numeric values", level=Qgis.Warning)
                return
            
            # Convert elevation to feet if needed
            ad_elev_unit = self.units.get('adElev', 'ft')
            if ad_elev_unit == 'm':
                ad_elev_ft = ad_elev * 3.28084
            else:
                ad_elev_ft = ad_elev
            
            # Calculate ISA temperature at elevation using standard formula
            # ISA temperature decreases at 1.98°C per 1000 ft (or 0.00198°C per ft)
            isa_temp = 15 - (0.00198 * ad_elev_ft)
            
            # Calculate ISA deviation (actual temperature - ISA temperature)
            isa_variation = temp_ref - isa_temp
            
            # Store calculation metadata for JSON export
            self.isa_calculation_metadata = {
                'method': 'calculated',
                'isa_temperature': isa_temp,
                'elevation_feet': ad_elev_ft,
                'elevation_original': ad_elev,
                'elevation_unit': ad_elev_unit,
                'temperature_reference': temp_ref,
                'isa_variation_calculated': isa_variation
            }
            
            # Show popup dialog with calculation details (like before)
            msg = QMessageBox()
            msg.setWindowTitle("ISA Calculator - Wind Spiral")
            msg.setIcon(QMessageBox.Information)
            
            # Two lines that were shown before
            calculation_text = f"ISA temperature: {isa_temp:.5f}°C (at {ad_elev_ft:.0f} ft)\n"
            calculation_text += f"ISA variation: {isa_variation:.5f}°C (Temp Ref - ISA Temp)"
            
            msg.setText(calculation_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            
            # Update the ISA Variation field
            self.isaVarLineEdit.setText(f"{isa_variation:.5f}")
            self.store_exact_value('isaVar', f"{isa_variation:.5f}")
            
            # Log the calculation
            self.log(f"ISA Calculation: Elevation {ad_elev} {ad_elev_unit} → ISA Temp {isa_temp:.5f}°C → ISA Variation {isa_variation:.5f}°C")
            self.iface.messageBar().pushMessage("QPANSOPY", f"ISA Variation calculated: {isa_variation:.5f}°C", level=Qgis.Info)
            
        except Exception as e:
            self.log(f"Error calculating ISA Variation: {str(e)}")
            self.iface.messageBar().pushMessage("Error", f"Error calculating ISA Variation: {str(e)}", level=Qgis.Critical)

    def calculate(self):
        """Run the calculation"""
        self.log("Starting calculation...")
        
        # Validate inputs
        if not self.validate_inputs():
            return
        
        # Usar el valor de ISA Variation directamente
        isa_var = self.exact_values.get('isaVar', self.isaVarLineEdit.text())
        try:
            isa_var = float(isa_var)
        except Exception:
            isa_var = 0
        # Get parameters
        point_layer = self.pointLayerComboBox.currentLayer()
        reference_layer = self.referenceLayerComboBox.currentLayer()
        IAS = self.exact_values.get('IAS', self.IASLineEdit.text())
        altitude = self.exact_values.get('altitude', self.altitudeLineEdit.text())
        bankAngle = self.exact_values.get('bankAngle', self.bankAngleLineEdit.text())
        w = self.exact_values.get('w', self.windSpeedLineEdit.text())
        turn_direction = self.turnDirectionCombo.currentText()
        show_points = self.showPointsCheckBox.isChecked()
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()
        
        # Get aerodrome elevation and temperature reference for ISA calculation
        adElev = self.exact_values.get('adElev', self.adElevLineEdit.text())
        tempRef = self.exact_values.get('tempRef', self.tempRefLineEdit.text())
        
        # Unidades
        altitude_unit = self.units.get('altitude', 'ft')
        adElev_unit = self.units.get('adElev', 'ft')
        
        # Prepare parameters
        params = {
            'adElev': adElev,
            'adElev_unit': adElev_unit,
            'tempRef': tempRef,
            'IAS': IAS,
            'altitude': altitude,
            'altitude_unit': altitude_unit,
            'bankAngle': bankAngle,
            'w': w,
            'turn_direction': turn_direction,
            'show_points': show_points,
            'export_kml': export_kml,
            'output_dir': output_dir
        }
        
        # Registrar las unidades utilizadas
        self.log(f"Using units - Aerodrome Elevation: {self.units.get('adElev', 'ft')}, Altitude: {self.units.get('altitude', 'ft')}")
        
        try:
            # Import here to avoid circular imports
            from ...modules.wind_spiral import calculate_wind_spiral
            result = calculate_wind_spiral(self.iface, point_layer, reference_layer, params)
            
            # Log results
            if result:
                if export_kml:
                    # Corregido: usar 'spiral_path' en lugar de 'kml_path'
                    self.log(f"Wind Spiral KML exported to: {result.get('spiral_path', 'N/A')}")
                self.log("Calculation completed successfully!")
                self.log("You can now use the 'Copy Parameters as JSON' button to copy the parameters for documentation.")
            else:
                self.log("Calculation completed but no results were returned.")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())

    def copy_parameters(self):
        """Copy parameters to clipboard"""
        try:
            # Get parameters
            params = {
                'adElev': self.exact_values.get('adElev', self.adElevLineEdit.text()),
                'adElev_unit': self.adElevUnitCombo.currentText(),
                'tempRef': self.exact_values.get('tempRef', self.tempRefLineEdit.text()),
                'isa_var': self.exact_values.get('isaVar', self.isaVarLineEdit.text()),
                'IAS': self.exact_values.get('IAS', self.IASLineEdit.text()),
                'altitude': self.exact_values.get('altitude', self.altitudeLineEdit.text()),
                'altitude_unit': self.altitudeUnitCombo.currentText(),
                'bankAngle': self.exact_values.get('bankAngle', self.bankAngleLineEdit.text()),
                'w': self.exact_values.get('w', self.windSpeedLineEdit.text()),
                'turn_direction': self.turnDirectionCombo.currentText()
            }
            
            # Import module and format parameters
            from ...modules.wind_spiral import copy_parameters_table
            formatted_params = copy_parameters_table(params)
            
            # Copy to clipboard
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(formatted_params)
            
            self.log("Parameters copied to clipboard")
            
        except Exception as e:
            self.log(f"Error copying parameters: {str(e)}")