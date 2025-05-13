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
from PyQt5 import QtGui, QtWidgets, uic
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
       
       # Set minimum and maximum sizes
       self.setMinimumWidth(400)  # Reducido de 450 a 400
       self.setMinimumHeight(450)  # Reducido de 500 a 450
       self.setMaximumHeight(700)  # Reducido de 800 a 700
       
       # Aumentar el espaciado en los layouts
       self.verticalLayout.setSpacing(8)  # Reducido de 10 a 8
       self.verticalLayout.setContentsMargins(8, 8, 8, 8)  # Reducido de 10 a 8
       
       # Connect signals
       self.calculateButton.clicked.connect(self.calculate)
       self.browseButton.clicked.connect(self.browse_output_folder)
       
       # Set default output folder
       self.outputFolderLineEdit.setText(self.get_desktop_path())
       
       # Filter layers in comboboxes
       self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
       self.referenceLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
       
       # Reemplazar los spinboxes con QLineEdit y añadir selectores de unidades
       self.setup_lineedits()
       
       # Añadir botón para copiar parámetros
       self.setup_copy_button()
       
       # Log message
       self.log("QPANSOPY Wind Spiral plugin loaded. Select layers and parameters, then click Calculate.")
   
   def setup_copy_button(self):
       """Configurar el botón para copiar parámetros al portapapeles"""
       self.copyParamsButton = QtWidgets.QPushButton("Copy Parameters to Clipboard", self)
       self.copyParamsButton.clicked.connect(self.copy_parameters_to_clipboard)
       self.copyParamsButton.setMinimumHeight(30)  # Reducido de 35 a 30
       
       # Añadir el botón al layout existente
       self.verticalLayout.addWidget(self.copyParamsButton)
   
   def copy_parameters_to_clipboard(self):
       """Copiar los parámetros de las capas seleccionadas al portapapeles"""
       # Obtener todas las capas del proyecto
       layers = QgsProject.instance().mapLayers().values()
       
       # Filtrar solo las capas vectoriales que podrían contener nuestros parámetros
       vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
       
       # Buscar capas que tengan el campo 'parameters'
       params_text = "QPANSOPY Parameters Report\n"
       params_text += "========================\n\n"
       
       found_params = False
       
       for layer in vector_layers:
           if 'parameters' in [field.name() for field in layer.fields()]:
               params_text += f"Layer: {layer.name()}\n"
               params_text += "------------------------\n"
               
               # Obtener los parámetros de cada feature
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       found_params = True
                       try:
                           params_dict = json.loads(params_json)
                           
                           # Añadir descripción si está disponible
                           if 'description' in [field.name() for field in layer.fields()]:
                               desc = feature.attribute('description')
                               if desc:
                                   params_text += f"Surface: {desc}\n"
                           
                           # Formatear los parámetros
                           params_text += "Parameters:\n"
                           for key, value in params_dict.items():
                               # Formatear mejor las claves
                               formatted_key = key.replace('_', ' ').title()
                               params_text += f"  - {formatted_key}: {value}\n"
                           
                           params_text += "\n"
                       except json.JSONDecodeError:
                           params_text += f"  Error: Could not parse parameters JSON\n\n"
               
               params_text += "\n"
       
       if not found_params:
           params_text += "No parameters found in any layer. Please run a calculation first.\n"
       
       # Copiar al portapapeles
       clipboard = QtWidgets.QApplication.clipboard()
       clipboard.setText(params_text)
       
       # Mostrar mensaje de éxito
       self.log("Parameters copied to clipboard. You can now paste them into Word or another application.")
       self.iface.messageBar().pushMessage("QPANSOPY", "Parameters copied to clipboard", level=Qgis.Success)
   
   def setup_lineedits(self):
       """Configurar QLineEdit para los campos numéricos y añadir selectores de unidades"""
       # Crear un validador para números decimales
       regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
       validator = QRegExpValidator(regex)
       
       # Configurar el espaciado y márgenes del formulario
       self.formLayout.setSpacing(8)  # Reducido de 10 a 8
       self.formLayout.setContentsMargins(8, 8, 8, 8)  # Reducido de 10 a 8
       
       # Aerodrome Elevation con selector de unidades
       self.adElevLineEdit = QtWidgets.QLineEdit(self)
       self.adElevLineEdit.setValidator(validator)
       self.adElevLineEdit.setText("0")
       self.adElevLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('adElev', text))
       self.adElevLineEdit.setMinimumHeight(25)  # Reducido de 30 a 25
       
       self.adElevUnitCombo = QtWidgets.QComboBox(self)
       self.adElevUnitCombo.addItems(['ft', 'm'])
       self.adElevUnitCombo.currentTextChanged.connect(
           lambda text: self.update_unit('adElev', text))
       self.adElevUnitCombo.setMinimumHeight(25)  # Reducido de 30 a 25
       self.adElevUnitCombo.setMinimumWidth(45)   # Reducido de 60 a 45
       
       # Crear un widget contenedor para el campo y el selector de unidades
       adElevContainer = QtWidgets.QWidget(self)
       adElevLayout = QtWidgets.QHBoxLayout(adElevContainer)
       adElevLayout.setContentsMargins(0, 0, 0, 0)
       adElevLayout.setSpacing(5)  # Añadido espaciado reducido
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
       self.tempRefLineEdit.setMinimumHeight(25)  # Reducido de 30 a 25
       
       # Añadir el widget al formulario
       self.formLayout.addRow("Temperature Reference (°C):", self.tempRefLineEdit)
       
       # IAS
       self.IASLineEdit = QtWidgets.QLineEdit(self)
       self.IASLineEdit.setValidator(validator)
       self.IASLineEdit.setText("205")
       self.IASLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('IAS', text))
       self.IASLineEdit.setMinimumHeight(25)  # Reducido de 30 a 25
       
       # Añadir el widget al formulario
       self.formLayout.addRow("IAS (kt):", self.IASLineEdit)
       
       # Altitude con selector de unidades
       self.altitudeLineEdit = QtWidgets.QLineEdit(self)
       self.altitudeLineEdit.setValidator(validator)
       self.altitudeLineEdit.setText("800")
       self.altitudeLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('altitude', text))
       self.altitudeLineEdit.setMinimumHeight(25)  # Reducido de 30 a 25
       
       self.altitudeUnitCombo = QtWidgets.QComboBox(self)
       self.altitudeUnitCombo.addItems(['ft', 'm'])
       self.altitudeUnitCombo.currentTextChanged.connect(
           lambda text: self.update_unit('altitude', text))
       self.altitudeUnitCombo.setMinimumHeight(25)  # Reducido de 30 a 25
       self.altitudeUnitCombo.setMinimumWidth(45)   # Reducido de 60 a 45
       
       # Crear un widget contenedor para el campo y el selector de unidades
       altitudeContainer = QtWidgets.QWidget(self)
       altitudeLayout = QtWidgets.QHBoxLayout(altitudeContainer)
       altitudeLayout.setContentsMargins(0, 0, 0, 0)
       altitudeLayout.setSpacing(5)  # Añadido espaciado reducido
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
       self.bankAngleLineEdit.setMinimumHeight(25)  # Reducido de 30 a 25
       
       # Añadir el widget al formulario
       self.formLayout.addRow("Bank Angle (°):", self.bankAngleLineEdit)
       
       # Wind Speed
       self.windSpeedLineEdit = QtWidgets.QLineEdit(self)
       self.windSpeedLineEdit.setValidator(validator)
       self.windSpeedLineEdit.setText("30")
       self.windSpeedLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('w', text))
       self.windSpeedLineEdit.setMinimumHeight(25)  # Reducido de 30 a 25
       
       # Añadir el widget al formulario
       self.formLayout.addRow("Wind Speed (kt):", self.windSpeedLineEdit)
       
       # Turn Direction
       self.turnDirectionCombo = QtWidgets.QComboBox(self)
       self.turnDirectionCombo.addItems(['R', 'L'])
       self.turnDirectionCombo.setMinimumHeight(25)  # Reducido de 30 a 25
       
       # Añadir el widget al formulario
       self.formLayout.addRow("Turn Direction:", self.turnDirectionCombo)
       
       # Show Points Checkbox
       self.showPointsCheckBox = QtWidgets.QCheckBox(self)
       self.showPointsCheckBox.setChecked(True)
       self.showPointsCheckBox.setMinimumHeight(20)  # Reducido de 25 a 20
       
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
       adElev = self.exact_values.get('adElev', self.adElevLineEdit.text())
       tempRef = self.exact_values.get('tempRef', self.tempRefLineEdit.text())
       IAS = self.exact_values.get('IAS', self.IASLineEdit.text())
       altitude = self.exact_values.get('altitude', self.altitudeLineEdit.text())
       bankAngle = self.exact_values.get('bankAngle', self.bankAngleLineEdit.text())
       w = self.exact_values.get('w', self.windSpeedLineEdit.text())
       
       turn_direction = self.turnDirectionCombo.currentText()
       show_points = self.showPointsCheckBox.isChecked()
       export_kml = self.exportKmlCheckBox.isChecked()
       output_dir = self.outputFolderLineEdit.text()
       
       # Prepare parameters
       params = {
           'adElev': adElev,
           'tempRef': tempRef,
           'IAS': IAS,
           'altitude': altitude,
           'bankAngle': bankAngle,
           'w': w,
           'turn_direction': turn_direction,
           'show_points': show_points,
           'export_kml': export_kml,
           'output_dir': output_dir,
           # Añadir información de unidades
           'adElev_unit': self.units.get('adElev', 'ft'),
           'altitude_unit': self.units.get('altitude', 'ft')
       }
       
       # Registrar las unidades utilizadas
       self.log(f"Using units - Aerodrome Elevation: {self.units.get('adElev', 'ft')}, Altitude: {self.units.get('altitude', 'ft')}")
       
       try:
           # Run calculation for Wind Spiral
           self.log("Running Wind Spiral calculation...")
           # Import here to avoid circular imports
           from .modules.wind_spiral import calculate_wind_spiral
           result = calculate_wind_spiral(self.iface, point_layer, reference_layer, params)
           
           # Log results
           if result:
               if export_kml:
                   self.log(f"Wind Spiral KML exported to: {result.get('spiral_path', 'N/A')}")
               self.log("Calculation completed successfully!")
               self.log("You can now use the 'Copy Parameters to Clipboard' button to copy the parameters for documentation.")
           else:
               self.log("Calculation completed but no results were returned.")
               
       except Exception as e:
           self.log(f"Error during calculation: {str(e)}")
           import traceback
           self.log(traceback.format_exc())