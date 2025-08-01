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
        
        # Improve form layout spacing and alignment
        self.formLayout.setVerticalSpacing(12)
        self.formLayout.setHorizontalSpacing(10)
        self.formLayout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.formLayout.setFormAlignment(Qt.AlignLeft)
        
        # Create validator for numeric inputs
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        # Common styles for consistent UI
        line_edit_style = """
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QLineEdit:hover {
                border-color: #999;
            }
        """
        
        combo_box_style = """
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                background-color: white;
                color: black;
                selection-background-color: #0078d4;
                selection-color: white;
            }
            QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox:hover {
                border-color: #999;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
                background-color: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #666;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ccc;
                background-color: white;
                selection-background-color: #0078d4;
                selection-color: white;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 4px 8px;
                border: none;
                color: black;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e3f2fd;
                color: black;
            }
        """
        
        # ISA Variation with Calculator button - aligned with other fields
        isa_container = QtWidgets.QWidget(self)
        isa_layout = QtWidgets.QHBoxLayout(isa_container)
        isa_layout.setContentsMargins(0, 0, 0, 0)
        isa_layout.setSpacing(8)
        
        # ISA Variation LineEdit - same size as other fields
        self.isaVarLineEdit = QtWidgets.QLineEdit(self)
        self.isaVarLineEdit.setValidator(validator)
        self.isaVarLineEdit.setText("0.00000")
        self.isaVarLineEdit.textChanged.connect(
            lambda text: self.handle_isa_manual_change(text))
        self.isaVarLineEdit.setMinimumHeight(28)
        self.isaVarLineEdit.setMaximumHeight(28)
        self.isaVarLineEdit.setStyleSheet(line_edit_style)
        
        # ISA Calculator Button - aligned to same height
        self.isaCalculatorButton = QtWidgets.QPushButton(self)
        self.isaCalculatorButton.setText("🧮")  # Calculator emoji as icon
        self.isaCalculatorButton.setToolTip("Calculate ISA Variation")
        self.isaCalculatorButton.setFixedWidth(34)  # Fixed width for consistency
        self.isaCalculatorButton.setMinimumHeight(28)
        self.isaCalculatorButton.setMaximumHeight(28)
        self.isaCalculatorButton.clicked.connect(self.show_isa_calculator_dialog)
        self.isaCalculatorButton.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        
        # Add widgets to layout - LineEdit takes most space, button is fixed
        isa_layout.addWidget(self.isaVarLineEdit)
        isa_layout.addWidget(self.isaCalculatorButton)
        
        # Set the container to have the same height as other form fields
        isa_container.setMinimumHeight(28)
        isa_container.setMaximumHeight(28)
        
        self.formLayout.addRow("ISA Variation (°C):", isa_container)
        
        # IAS
        self.IASLineEdit = QtWidgets.QLineEdit(self)
        self.IASLineEdit.setValidator(validator)
        self.IASLineEdit.setText("205")
        self.IASLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('IAS', text))
        self.IASLineEdit.setMinimumHeight(28)
        self.IASLineEdit.setMaximumHeight(28)
        self.IASLineEdit.setStyleSheet(line_edit_style)
        self.formLayout.addRow("IAS (kt):", self.IASLineEdit)
        
        # Altitude with unit selector
        self.altitudeLineEdit = QtWidgets.QLineEdit(self)
        self.altitudeLineEdit.setValidator(validator)
        self.altitudeLineEdit.setText("800")
        self.altitudeLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('altitude', text))
        self.altitudeLineEdit.setMinimumHeight(28)
        self.altitudeLineEdit.setMaximumHeight(28)
        self.altitudeLineEdit.setStyleSheet(line_edit_style)
        
        self.altitudeUnitCombo = QtWidgets.QComboBox(self)
        self.altitudeUnitCombo.addItems(['ft', 'm'])
        self.altitudeUnitCombo.currentTextChanged.connect(
            lambda text: self.update_unit('altitude', text))
        self.altitudeUnitCombo.setMinimumHeight(28)
        self.altitudeUnitCombo.setMaximumHeight(28)
        self.altitudeUnitCombo.setMinimumWidth(50)
        self.altitudeUnitCombo.setMaximumWidth(60)
        self.altitudeUnitCombo.setStyleSheet(combo_box_style)
        
        altitudeContainer = QtWidgets.QWidget(self)
        altitudeLayout = QtWidgets.QHBoxLayout(altitudeContainer)
        altitudeLayout.setContentsMargins(0, 0, 0, 0)
        altitudeLayout.setSpacing(8)
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
        self.bankAngleLineEdit.setMaximumHeight(28)
        self.bankAngleLineEdit.setStyleSheet(line_edit_style)
        self.formLayout.addRow("Bank Angle (°):", self.bankAngleLineEdit)
        
        # Wind Speed
        self.windSpeedLineEdit = QtWidgets.QLineEdit(self)
        self.windSpeedLineEdit.setValidator(validator)
        self.windSpeedLineEdit.setText("30")
        self.windSpeedLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('w', text))
        self.windSpeedLineEdit.setMinimumHeight(28)
        self.windSpeedLineEdit.setMaximumHeight(28)
        self.windSpeedLineEdit.setStyleSheet(line_edit_style)
        self.formLayout.addRow("Wind Speed (kt):", self.windSpeedLineEdit)
        
        # Turn Direction
        self.turnDirectionCombo = QtWidgets.QComboBox(self)
        self.turnDirectionCombo.addItems(['R', 'L'])
        self.turnDirectionCombo.setMinimumHeight(28)
        self.turnDirectionCombo.setMaximumHeight(28)
        self.turnDirectionCombo.setStyleSheet(combo_box_style)
        self.formLayout.addRow("Turn Direction:", self.turnDirectionCombo)
        
        # Show Points checkbox
        self.showPointsCheckBox = QtWidgets.QCheckBox("Show intermediate points", self)
        self.showPointsCheckBox.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border-color: #0078d4;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
        """)
        self.formLayout.addRow("", self.showPointsCheckBox)
        
        # Export KML checkbox
        self.exportKmlCheckBox = QtWidgets.QCheckBox("Export KML", self)
        self.exportKmlCheckBox.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border-color: #0078d4;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
        """)
        self.formLayout.addRow("", self.exportKmlCheckBox)
        
        # Output folder
        if not hasattr(self, 'outputFolderLineEdit'):
            self.outputFolderLineEdit = QtWidgets.QLineEdit(self)
            self.outputFolderLineEdit.setText(self.get_desktop_path())
            self.outputFolderLineEdit.setMinimumHeight(28)
            self.outputFolderLineEdit.setMaximumHeight(28)
            self.outputFolderLineEdit.setStyleSheet(line_edit_style)
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
        # Mark as manual input - no automatic calculations
        self.isa_calculation_metadata['method'] = 'manual'
    
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
        # Usar valores actuales (usando valores almacenados del diálogo)
        params = {
            'adElev': self.exact_values.get('adElev', ''),
            'adElev_unit': self.units.get('adElev', 'ft'),
            'tempRef': self.exact_values.get('tempRef', ''),
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
            params_text += f"Method:\t\t\tCalculated from Elevation and Temperature\n"
            params_text += f"ISA Temperature:\t\t{self.isa_calculation_metadata['isa_temperature']:.5f}\t\t°C\n"
            params_text += f"Elevation Used:\t\t{self.isa_calculation_metadata['elevation_feet']:.0f}\t\tft\n"
            params_text += f"Temperature Reference:\t\t{self.isa_calculation_metadata['temperature_reference']}\t\t°C\n"
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
                'adElev': self.exact_values.get('adElev', ''),
                'adElev_unit': self.units.get('adElev', 'ft'),
                'tempRef': self.exact_values.get('tempRef', ''),
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

    def show_isa_calculator_dialog(self):
        """Show ISA Calculator dialog to input elevation and temperature"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("ISA Calculator")
        dialog.setModal(True)
        dialog.setFixedSize(380, 180)  # Fixed size for better layout
        
        # Set dialog properties for better appearance
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Form layout for inputs with better spacing
        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignLeft)
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(15)
        
        # Create validator for numeric inputs
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        # Aerodrome Elevation with unit selector - improved layout
        elev_container = QtWidgets.QWidget()
        elev_layout = QtWidgets.QHBoxLayout(elev_container)
        elev_layout.setContentsMargins(0, 0, 0, 0)
        elev_layout.setSpacing(8)
        
        elev_line_edit = QtWidgets.QLineEdit()
        elev_line_edit.setValidator(validator)
        elev_line_edit.setText(str(self.exact_values.get('adElev', '1000')))
        elev_line_edit.setMinimumHeight(28)
        elev_line_edit.setMinimumWidth(180)
        elev_line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        
        elev_unit_combo = QtWidgets.QComboBox()
        elev_unit_combo.addItems(['ft', 'm'])
        elev_unit_combo.setCurrentText(self.units.get('adElev', 'ft'))
        elev_unit_combo.setMinimumHeight(28)
        elev_unit_combo.setMinimumWidth(55)
        elev_unit_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                background-color: white;
                color: black;
                selection-background-color: #0078d4;
                selection-color: white;
            }
            QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox:hover {
                border-color: #999;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
                background-color: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #666;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ccc;
                background-color: white;
                selection-background-color: #0078d4;
                selection-color: white;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 4px 8px;
                border: none;
                color: black;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e3f2fd;
                color: black;
            }
        """)
        
        elev_layout.addWidget(elev_line_edit)
        elev_layout.addWidget(elev_unit_combo)
        elev_layout.addStretch()
        
        form_layout.addRow("Aerodrome Elevation:", elev_container)
        
        # Temperature Reference - improved styling
        temp_line_edit = QtWidgets.QLineEdit()
        temp_line_edit.setValidator(validator)
        temp_line_edit.setText(str(self.exact_values.get('tempRef', '15')))
        temp_line_edit.setMinimumHeight(28)
        temp_line_edit.setMinimumWidth(180)
        temp_line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        
        form_layout.addRow("Temperature Ref (°C):", temp_line_edit)
        
        layout.addLayout(form_layout)
        
        # Separator line
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setStyleSheet("color: #ddd;")
        layout.addWidget(separator)
        
        # Buttons with improved styling
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)
        
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setMinimumHeight(32)
        cancel_button.setMinimumWidth(80)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        
        calculate_button = QtWidgets.QPushButton("Calculate ISA")
        calculate_button.setMinimumHeight(32)
        calculate_button.setMinimumWidth(100)
        calculate_button.setDefault(True)
        calculate_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border: 1px solid #0078d4;
                border-radius: 4px;
                color: white;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
                border-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:default {
                border: 2px solid #0078d4;
            }
        """)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(calculate_button)
        
        layout.addLayout(button_layout)
        
        # Connect buttons
        cancel_button.clicked.connect(dialog.reject)
        
        def calculate_and_close():
            try:
                # Get values
                elevation_text = elev_line_edit.text().strip()
                temperature_text = temp_line_edit.text().strip()
                
                if not elevation_text or not temperature_text:
                    QtWidgets.QMessageBox.warning(dialog, "Input Error", 
                        "Please enter both Aerodrome Elevation and Temperature Reference")
                    return
                
                try:
                    elevation = float(elevation_text)
                    temperature = float(temperature_text)
                except ValueError:
                    QtWidgets.QMessageBox.warning(dialog, "Input Error", 
                        "Please enter valid numeric values")
                    return
                
                # Store values for future use
                self.store_exact_value('adElev', elevation_text)
                self.store_exact_value('tempRef', temperature_text)
                
                # Update unit
                elevation_unit = elev_unit_combo.currentText()
                self.units['adElev'] = elevation_unit
                
                # Convert elevation to feet if needed
                if elevation_unit == 'm':
                    elevation_ft = elevation * 3.28084
                else:
                    elevation_ft = elevation
                
                # Calculate ISA temperature at elevation
                # ISA temperature decreases at 1.98°C per 1000 ft (or 0.00198°C per ft)
                isa_temp = 15 - (0.00198 * elevation_ft)
                
                # Calculate ISA variation (actual temperature - ISA temperature)
                isa_variation = temperature - isa_temp
                
                # Update the ISA Variation field in main UI
                self.isaVarLineEdit.setText(f"{isa_variation:.5f}")
                self.store_exact_value('isaVar', f"{isa_variation:.5f}")
                
                # Store calculation metadata
                self.isa_calculation_metadata = {
                    'method': 'calculated',
                    'isa_temperature': isa_temp,
                    'elevation_feet': elevation_ft,
                    'elevation_original': elevation,
                    'elevation_unit': elevation_unit,
                    'temperature_reference': temperature,
                    'isa_variation_calculated': isa_variation
                }
                
                # Log the calculation
                elev_info = f"{elevation} {elevation_unit}"
                self.log(f"ISA Calculator: Elevation {elev_info} → ISA Temp {isa_temp:.5f}°C → ISA Variation {isa_variation:.5f}°C")
                self.iface.messageBar().pushMessage("QPANSOPY", f"ISA Variation calculated: {isa_variation:.5f}°C", level=Qgis.Info)
                
                dialog.accept()
                
            except Exception as e:
                self.log(f"Error calculating ISA Variation: {str(e)}")
                QtWidgets.QMessageBox.critical(dialog, "Error", f"Error calculating ISA Variation: {str(e)}")
        
        calculate_button.clicked.connect(calculate_and_close)
        
        # Focus on elevation field
        elev_line_edit.setFocus()
        
        # Show dialog
        dialog.exec_()
    def calculate(self):
        """Run the calculation"""
        self.log("Starting calculation...")
        
        # Validate inputs
        if not self.validate_inputs():
            return
        
        # Get parameters (no longer need aerodrome elevation and temperature reference)
        point_layer = self.pointLayerComboBox.currentLayer()
        reference_layer = self.referenceLayerComboBox.currentLayer()
        
        # Use ISA Variation directly from field
        isa_var = self.exact_values.get('isaVar', self.isaVarLineEdit.text())
        try:
            isa_var = float(isa_var)
        except Exception:
            isa_var = 0
        
        IAS = self.exact_values.get('IAS', self.IASLineEdit.text())
        altitude = self.exact_values.get('altitude', self.altitudeLineEdit.text())
        bankAngle = self.exact_values.get('bankAngle', self.bankAngleLineEdit.text())
        w = self.exact_values.get('w', self.windSpeedLineEdit.text())
        turn_direction = self.turnDirectionCombo.currentText()
        show_points = self.showPointsCheckBox.isChecked()
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()
        
        # Unidades
        altitude_unit = self.units.get('altitude', 'ft')
        
        # Prepare parameters (simplified - no aerodrome elevation or temperature reference)
        params = {
            'isaVar': isa_var,
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
        
        # Log ISA calculation method
        if self.isa_calculation_metadata['method'] == 'calculated':
            self.log(f"Using calculated ISA Variation: {isa_var}°C")
            self.log(f"ISA calculation source: {self.isa_calculation_metadata['elevation_original']} {self.isa_calculation_metadata['elevation_unit']} elevation, {self.isa_calculation_metadata['temperature_reference']}°C reference")
        else:
            self.log(f"Using manual ISA Variation: {isa_var}°C")
        
        # Registrar las unidades utilizadas
        self.log(f"Using units - Altitude: {self.units.get('altitude', 'ft')}")
        
        try:
            # Import here to avoid circular imports
            from ...modules.wind_spiral import calculate_wind_spiral
            result = calculate_wind_spiral(self.iface, point_layer, reference_layer, params)
            
            # Log results
            if result:
                if export_kml:
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
            # Get parameters - use stored values for elevation and temperature from dialog
            params = {
                'adElev': self.exact_values.get('adElev', ''),
                'adElev_unit': self.units.get('adElev', 'ft'),
                'tempRef': self.exact_values.get('tempRef', ''),
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