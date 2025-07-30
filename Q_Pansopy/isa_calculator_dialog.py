# -*- coding: utf-8 -*-
"""
/***************************************************************************
ISA Calculator Dialog
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - ISA Calculator
                        -------------------
   begin                : 2025-07-30
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

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QComboBox, QPushButton, QLabel, 
                             QDialogButtonBox, QMessageBox, QGroupBox, QWidget)
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator


class ISACalculatorDialog(QDialog):
    """Dialog for ISA calculation with independent inputs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ISA Calculator")
        self.setFixedSize(400, 300)
        
        # Result values
        self.isa_variation = None
        self.calculation_metadata = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Input Group
        input_group = QGroupBox("Input Parameters")
        input_layout = QFormLayout(input_group)
        
        # Create validator for numeric inputs
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        # Aerodrome Elevation
        elev_container = QHBoxLayout()
        self.elevation_edit = QLineEdit()
        self.elevation_edit.setValidator(validator)
        self.elevation_edit.setText("0")
        self.elevation_edit.setMinimumHeight(28)
        
        self.elevation_unit_combo = QComboBox()
        self.elevation_unit_combo.addItems(['ft', 'm'])
        self.elevation_unit_combo.setMinimumHeight(28)
        self.elevation_unit_combo.setFixedWidth(50)
        
        elev_container.addWidget(self.elevation_edit)
        elev_container.addWidget(self.elevation_unit_combo)
        elev_widget = QWidget()
        elev_widget.setLayout(elev_container)
        
        input_layout.addRow("Aerodrome Elevation:", elev_widget)
        
        # Temperature Reference
        self.temperature_edit = QLineEdit()
        self.temperature_edit.setValidator(validator)
        self.temperature_edit.setText("15")
        self.temperature_edit.setMinimumHeight(28)
        input_layout.addRow("Temperature Reference (°C):", self.temperature_edit)
        
        layout.addWidget(input_group)
        
        # Calculation Group
        calc_group = QGroupBox("Calculation")
        calc_layout = QVBoxLayout(calc_group)
        
        # Calculate button
        self.calculate_btn = QPushButton("🧮 Calculate ISA Variation")
        self.calculate_btn.setMinimumHeight(35)
        self.calculate_btn.clicked.connect(self.calculate_isa)
        calc_layout.addWidget(self.calculate_btn)
        
        # Results display
        self.result_label = QLabel("Click 'Calculate ISA Variation' to see results")
        self.result_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        self.result_label.setWordWrap(True)
        calc_layout.addWidget(self.result_label)
        
        layout.addWidget(calc_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_calculation)
        button_box.rejected.connect(self.reject)
        
        # Initially disable OK button
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        
        layout.addWidget(button_box)
        
    def calculate_isa(self):
        """Calculate ISA variation"""
        try:
            # Get input values
            elevation_text = self.elevation_edit.text().strip()
            temperature_text = self.temperature_edit.text().strip()
            
            if not elevation_text or not temperature_text:
                QMessageBox.warning(self, "Input Error", 
                                  "Please enter both Aerodrome Elevation and Temperature Reference")
                return
            
            try:
                elevation = float(elevation_text)
                temperature = float(temperature_text)
            except ValueError:
                QMessageBox.warning(self, "Input Error", 
                                  "Please enter valid numeric values")
                return
            
            # Convert elevation to feet if needed
            elevation_unit = self.elevation_unit_combo.currentText()
            if elevation_unit == 'm':
                elevation_ft = elevation * 3.28084
            else:
                elevation_ft = elevation
            
            # Calculate ISA temperature at elevation
            # ISA temperature decreases at 1.98°C per 1000 ft (or 0.00198°C per ft)
            isa_temp = 15 - (0.00198 * elevation_ft)
            
            # Calculate ISA variation (actual temperature - ISA temperature)
            isa_variation = temperature - isa_temp
            
            # Store results
            self.isa_variation = isa_variation
            self.calculation_metadata = {
                'method': 'calculated',
                'isa_temperature': isa_temp,
                'elevation_feet': elevation_ft,
                'elevation_original': elevation,
                'elevation_unit': elevation_unit,
                'temperature_reference': temperature,
                'isa_variation_calculated': isa_variation
            }
            
            # Update result display
            result_text = f"✅ Calculation Complete\n\n"
            result_text += f"ISA Temperature: {isa_temp:.5f}°C (at {elevation_ft:.0f} ft)\n"
            result_text += f"ISA Variation: {isa_variation:.5f}°C\n"
            result_text += f"(Temperature Reference - ISA Temperature)"
            
            self.result_label.setText(result_text)
            self.result_label.setStyleSheet("color: #2e7d32; padding: 10px; background-color: #e8f5e8; border-radius: 5px;")
            
            # Enable OK button
            self.ok_button.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error calculating ISA Variation: {str(e)}")
            
    def accept_calculation(self):
        """Accept the calculation if valid"""
        if self.isa_variation is not None:
            self.accept()
        else:
            QMessageBox.warning(self, "No Calculation", 
                              "Please calculate ISA Variation before accepting")
    
    def get_isa_variation(self):
        """Get the calculated ISA variation"""
        return self.isa_variation
    
    def get_calculation_metadata(self):
        """Get the calculation metadata"""
        return self.calculation_metadata
