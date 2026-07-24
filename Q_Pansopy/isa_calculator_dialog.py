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

from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                                 QLineEdit, QComboBox, QPushButton, QLabel,
                                 QMessageBox, QGroupBox, QWidget)
from qgis.PyQt.QtCore import QRegularExpression
from qgis.PyQt.QtGui import QRegularExpressionValidator
from .qt_compat import Qt_AlignRight, Qt_AlignVCenter
from .dockwidgets.base_dockwidget import load_base_qss


class ISACalculatorDialog(QDialog):
    """Dialog for ISA calculation with independent inputs"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ISA Calculator")
        self.setFixedSize(400, 300)
        self.setStyleSheet(load_base_qss())

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
        input_layout.setVerticalSpacing(12)
        input_layout.setHorizontalSpacing(10)
        input_layout.setLabelAlignment(Qt_AlignRight | Qt_AlignVCenter)

        # Create validator for numeric inputs
        regex = QRegularExpression(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegularExpressionValidator(regex)

        # Aerodrome Elevation
        elev_container = QHBoxLayout()
        elev_container.setContentsMargins(0, 0, 0, 0)
        elev_container.setSpacing(8)
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

        # Calculate button — calculating also accepts and closes the dialog,
        # applying the result to the caller immediately (no separate OK step)
        self.calculate_btn = QPushButton("🧮 Calculate ISA Variation")
        self.calculate_btn.setMinimumHeight(35)
        self.calculate_btn.clicked.connect(self.calculate_isa)
        calc_layout.addWidget(self.calculate_btn)

        # Hint label
        self.hint_label = QLabel("Enter the values above, then click 'Calculate ISA Variation'.")
        self.hint_label.setStyleSheet("color: #999; font-style: italic; padding: 10px;")
        self.hint_label.setWordWrap(True)
        calc_layout.addWidget(self.hint_label)

        layout.addWidget(calc_group)

        # Cancel button (Calculate is the accept action, so no separate OK button)
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        cancel_row.addWidget(self.cancel_btn)
        layout.addLayout(cancel_row)

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

            # Calculation succeeded — accept and close immediately, no extra
            # confirmation step. The caller reads the result via
            # get_isa_variation()/get_calculation_metadata() after exec().
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error calculating ISA Variation: {str(e)}")

    def get_isa_variation(self):
        """Get the calculated ISA variation"""
        return self.isa_variation

    def get_calculation_metadata(self):
        """Get the calculation metadata"""
        return self.calculation_metadata
