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
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes, QgsCoordinateReferenceSystem, QgsMapLayerProxyModel
from qgis.utils import iface
from qgis.core import Qgis
import json

# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qpansopy_wind_spiral_dockwidget.ui'))


class QPANSOPYWindSpiralDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """Constructor."""
        super(QPANSOPYWindSpiralDockWidget, self).__init__(iface.mainWindow())
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.iface = iface
        
        # Diccionario para almacenar los valores exactos ingresados
        self.exact_values = {}
        # Diccionario para almacenar las unidades seleccionadas
        self.units = {
            'adElev': 'ft',
            'altitude': 'ft'
        }
        
        # Configure the dock widget to be resizable
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable |
                         QtWidgets.QDockWidget.DockWidgetClosable)
        
        # Set minimum and maximum sizes (similar to OAS ILS)
        self.setMinimumWidth(400)
        self.setMinimumHeight(450)
        self.setMaximumHeight(700)
        
        # Connect signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self.browse_output_folder)
        self.copyParamsButton.clicked.connect(self.copy_parameters_to_clipboard)
        
        # Set default output folder
        self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Filter layers in comboboxes
        self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.referenceLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        
        # Reemplazar los spinboxes con QLineEdit y añadir selectores de unidades
        self.setup_lineedits()
        
        # Limitar el tamaño del área de logs para que no sea demasiado grande
        # Usar un valor razonable similar al de OAS ILS (100-150px)
        self.logTextEdit.setMaximumHeight(120)
        
        # Log message
        self.log("QPANSOPY Wind Spiral plugin loaded. Select layers and parameters, then click Calculate.")

    def copy_parameters_to_clipboard(self):
        """Copiar los parámetros al portapapeles en formato JSON"""
        # Crear un diccionario con los parámetros actuales
        params_dict = {
            'adElev': self.exact_values.get('adElev', self.adElevLineEdit.text()),
            'adElev_unit': self.units.get('adElev', 'ft'),
            'tempRef': self.exact_values.get('tempRef', self.tempRefLineEdit.text()),
            'IAS': self.exact_values.get('IAS', self.IASLineEdit.text()),
            'altitude': self.exact_values.get('altitude', self.altitudeLineEdit.text()),
            'altitude_unit': self.units.get('altitude', 'ft'),
            'bankAngle': self.exact_values.get('bankAngle', self.bankAngleLineEdit.text()),
            'w': self.exact_values.get('w', self.windSpeedLineEdit.text()),
            'turnDirection': self.turnDirectionCombo.currentText(),
            'showPoints': self.showPointsCheckBox.isChecked()
        }
        
        # Añadir metadatos adicionales
        params_dict['metadata'] = {
            'plugin': 'QPANSOPY Wind Spiral',
            'version': '1.0',
            'date': QtCore.QDateTime.currentDateTime().toString(QtCore.Qt.ISODate),
            'description': 'Wind Spiral parameters'
        }
        
        # Convertir a JSON para el portapapeles
        params_json = json.dumps(params_dict, indent=2)
        
        # Preguntar al usuario si quiere ver el JSON antes de copiarlo
        msgBox = QtWidgets.QMessageBox()
        msgBox.setWindowTitle("Copy Parameters as JSON")
        msgBox.setText("Parameters have been formatted as JSON.")
        msgBox.setInformativeText("Do you want to view the JSON before copying to clipboard?")
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msgBox.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if msgBox.exec_() == QtWidgets.QMessageBox.Yes:
            # Mostrar el JSON en un diálogo
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("JSON Parameters")
            dialog.setMinimumSize(500, 400)
            
            layout = QtWidgets.QVBoxLayout(dialog)
            
            textEdit = QtWidgets.QTextEdit(dialog)
            textEdit.setReadOnly(True)
            textEdit.setPlainText(params_json)
            layout.addWidget(textEdit)
            
            buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            buttonBox.accepted.connect(dialog.accept)
            buttonBox.rejected.connect(dialog.reject)
            layout.addWidget(buttonBox)
            
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # Copiar al portapapeles
                clipboard = QtWidgets.QApplication.clipboard()
                clipboard.setText(params_json)
                self.log("Parameters copied to clipboard in JSON format.")
                self.iface.messageBar().pushMessage("QPANSOPY", "Parameters copied to clipboard in JSON format", level=Qgis.Success)
        else:
            # Copiar directamente al portapapeles
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(params_json)
            self.log("Parameters copied to clipboard in JSON format.")
            self.iface.messageBar().pushMessage("QPANSOPY", "Parameters copied to clipboard in JSON format", level=Qgis.Success)

    def setup_lineedits(self):
        """Configurar QLineEdit para los campos numéricos y añadir selectores de unidades"""
        # Crear un validador para números decimales
        regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
        validator = QRegExpValidator(regex)
        
        # Aerodrome Elevation con selector de unidades
        self.adElevLineEdit = QtWidgets.QLineEdit(self)
        self.adElevLineEdit.setValidator(validator)
        self.adElevLineEdit.setText("0")
        self.adElevLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('adElev', text))
        
        self.adElevUnitCombo = QtWidgets.QComboBox(self)
        self.adElevUnitCombo.addItems(['ft', 'm'])
        self.adElevUnitCombo.currentTextChanged.connect(
            lambda text: self.update_unit('adElev', text))
        self.adElevUnitCombo.setFixedWidth(50)
        
        # Crear un widget contenedor para el campo y el selector de unidades
        adElevContainer = QtWidgets.QWidget(self)
        adElevLayout = QtWidgets.QHBoxLayout(adElevContainer)
        adElevLayout.setContentsMargins(0, 0, 0, 0)
        adElevLayout.setSpacing(5)
        adElevLayout.addWidget(self.adElevLineEdit)
        adElevLayout.addWidget(self.adElevUnitCombo)
        
        # Añadir el widget al formulario
        self.formLayout.addRow("Aerodrome Elevation:", adElevContainer)
        
        # Temperature Reference
        self.tempRefLineEdit = QtWidgets.QLineEdit(self)
        self.tempRefLineEdit.setValidator(validator)
        self.tempRefLineEdit.setText("15")
        self.tempRefLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('tempRef', text))
        
        # Añadir el widget al formulario
        self.formLayout.addRow("Temperature Reference (°C):", self.tempRefLineEdit)
        
        # IAS
        self.IASLineEdit = QtWidgets.QLineEdit(self)
        self.IASLineEdit.setValidator(validator)
        self.IASLineEdit.setText("205")
        self.IASLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('IAS', text))
        
        # Añadir el widget al formulario
        self.formLayout.addRow("IAS (kt):", self.IASLineEdit)
        
        # Altitude con selector de unidades
        self.altitudeLineEdit = QtWidgets.QLineEdit(self)
        self.altitudeLineEdit.setValidator(validator)
        self.altitudeLineEdit.setText("800")
        self.altitudeLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('altitude', text))
        
        self.altitudeUnitCombo = QtWidgets.QComboBox(self)
        self.altitudeUnitCombo.addItems(['ft', 'm'])
        self.altitudeUnitCombo.currentTextChanged.connect(
            lambda text: self.update_unit('altitude', text))
        self.altitudeUnitCombo.setFixedWidth(50)
        
        # Crear un widget contenedor para el campo y el selector de unidades
        altitudeContainer = QtWidgets.QWidget(self)
        altitudeLayout = QtWidgets.QHBoxLayout(altitudeContainer)
        altitudeLayout.setContentsMargins(0, 0, 0, 0)
        altitudeLayout.setSpacing(5)
        altitudeLayout.addWidget(self.altitudeLineEdit)
        altitudeLayout.addWidget(self.altitudeUnitCombo)
        
        # Añadir el widget al formulario
        self.formLayout.addRow("Altitude:", altitudeContainer)
        
        # Bank Angle
        self.bankAngleLineEdit = QtWidgets.QLineEdit(self)
        self.bankAngleLineEdit.setValidator(validator)
        self.bankAngleLineEdit.setText("15")
        self.bankAngleLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('bankAngle', text))
        
        # Añadir el widget al formulario
        self.formLayout.addRow("Bank Angle (°):", self.bankAngleLineEdit)
        
        # Wind Speed
        self.windSpeedLineEdit = QtWidgets.QLineEdit(self)
        self.windSpeedLineEdit.setValidator(validator)
        self.windSpeedLineEdit.setText("30")
        self.windSpeedLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('w', text))
        
        # Añadir el widget al formulario
        self.formLayout.addRow("Wind Speed (kt):", self.windSpeedLineEdit)
        
        # Turn Direction
        self.turnDirectionCombo = QtWidgets.QComboBox(self)
        self.turnDirectionCombo.addItems(['R', 'L'])
        
        # Añadir el widget al formulario
        self.formLayout.addRow("Turn Direction:", self.turnDirectionCombo)
        
        # Show Points Checkbox
        self.showPointsCheckBox = QtWidgets.QCheckBox(self)
        self.showPointsCheckBox.setChecked(True)
        
        # Añadir el widget al formulario
        self.formLayout.addRow("Show Construction Points:", self.showPointsCheckBox)

    def update_unit(self, param_name, unit):
        """Actualizar la unidad seleccionada para un parámetro"""
        self.units[param_name] = unit

    def store_exact_value(self, param_name, text):
        """Almacenar el valor exacto ingresado por el usuario"""
        try:
            # Intentar convertir a float para validar
            value = float(text.replace(',', '.'))
            # Si es válido, almacenar el texto original
            self.exact_values[param_name] = text.replace(',', '.')
        except ValueError:
            # Si no es un número válido, no hacer nada
            pass

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def get_desktop_path(self):
        """Get the path to the desktop"""
        if os.name == 'nt':  # Windows
            return os.path.join(os.environ['USERPROFILE'], 'Desktop')
        elif os.name == 'posix':  # macOS or Linux
            return os.path.join(os.path.expanduser('~'), 'Desktop')
        else:
            return os.path.expanduser('~')

    def browse_output_folder(self):
        """Open a folder browser dialog"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.outputFolderLineEdit.text()
        )
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        """Add a message to the log"""
        self.logTextEdit.append(message)
        # Ensure the latest message is visible
        self.logTextEdit.ensureCursorVisible()

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

    def calculate(self):
        """Run the calculation"""
        self.log("Starting calculation...")
        
        # Validate inputs
        if not self.validate_inputs():
            return
        
        # Get parameters
        point_layer = self.pointLayerComboBox.currentLayer()
        reference_layer = self.referenceLayerComboBox.currentLayer()
        
        # Usar valores exactos si están disponibles, de lo contrario usar los valores de los QLineEdit
        ad_elev = self.exact_values.get('adElev', self.adElevLineEdit.text())
        temp_ref = self.exact_values.get('tempRef', self.tempRefLineEdit.text())
        ias = self.exact_values.get('IAS', self.IASLineEdit.text())
        altitude = self.exact_values.get('altitude', self.altitudeLineEdit.text())
        bank_angle = self.exact_values.get('bankAngle', self.bankAngleLineEdit.text())
        wind_speed = self.exact_values.get('w', self.windSpeedLineEdit.text())
        turn_direction = self.turnDirectionCombo.currentText()
        show_points = self.showPointsCheckBox.isChecked()
        
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()
        
        # Prepare parameters
        params = {
            'ad_elev': ad_elev,
            'temp_ref': temp_ref,
            'ias': ias,
            'altitude': altitude,
            'bank_angle': bank_angle,
            'w': wind_speed,
            'turn_direction': turn_direction,
            'show_points': show_points,
            'export_kml': export_kml,
            'output_dir': output_dir,
            # Añadir información de unidades
            'ad_elev_unit': self.units.get('adElev', 'ft'),
            'altitude_unit': self.units.get('altitude', 'ft')
        }
        
        # Registrar las unidades utilizadas
        self.log(f"Using units - Aerodrome Elevation: {self.units.get('adElev', 'ft')}, Altitude: {self.units.get('altitude', 'ft')}")
        
        try:
            # Import here to avoid circular imports
            from .modules.wind_spiral import calculate_wind_spiral
            result = calculate_wind_spiral(self.iface, point_layer, reference_layer, params)
            
            # Log results
            if result:
                if export_kml:
                    self.log(f"Wind Spiral KML exported to: {result.get('kml_path', 'N/A')}")
                self.log("Calculation completed successfully!")
                self.log("You can now use the 'Copy Parameters as JSON' button to copy the parameters for documentation.")
            else:
                self.log("Calculation completed but no results were returned.")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())