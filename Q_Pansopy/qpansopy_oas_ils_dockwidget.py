# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYOASILSDockWidget
                                A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - OAS ILS Module
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
   os.path.dirname(__file__), 'qpansopy_oas_ils_dockwidget.ui'))


class QPANSOPYOASILSDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

   closingPlugin = pyqtSignal()

   def __init__(self, iface):
       """Constructor."""
       super(QPANSOPYOASILSDockWidget, self).__init__(iface.mainWindow())
       # Set up the user interface from Designer.
       self.setupUi(self)
       self.iface = iface
       
       # Diccionario para almacenar los valores exactos ingresados
       self.exact_values = {}
       # Diccionario para almacenar las unidades seleccionadas
       self.units = {
           'THR_elev': 'm'
       }
       
       # Configure the dock widget to be resizable
       self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                        QtWidgets.QDockWidget.DockWidgetFloatable |
                        QtWidgets.QDockWidget.DockWidgetClosable)
       
       # Set minimum and maximum sizes
       self.setMinimumWidth(400)
       self.setMinimumHeight(450)
       self.setMaximumHeight(700)
       
       # Aumentar el espaciado en los layouts
       self.verticalLayout.setSpacing(8)
       self.verticalLayout.setContentsMargins(8, 8, 8, 8)
       
       # Connect signals
       self.calculateButton.clicked.connect(self.calculate)
       self.browseButton.clicked.connect(self.browse_output_folder)
       
       # Set default output folder
       self.outputFolderLineEdit.setText(self.get_desktop_path())
       
       # Filter layers in comboboxes
       self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
       self.runwayLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
       
       # Reemplazar los spinboxes con QLineEdit y añadir selectores de unidades
       self.setup_lineedits()
       
       # Añadir botón para copiar parámetros
       self.setup_copy_button()
       
       # Log message
       self.log("QPANSOPY OAS ILS plugin loaded. Select layers and parameters, then click Calculate.")
   
   def setup_copy_button(self):
       """Configurar el botón para copiar parámetros al portapapeles"""
       self.copyParamsButton = QtWidgets.QPushButton("Copy Parameters to Clipboard", self)
       self.copyParamsButton.clicked.connect(self.copy_parameters_to_clipboard)
       self.copyParamsButton.setMinimumHeight(30)
       
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
                           if 'ILS_surface' in [field.name() for field in layer.fields()]:
                               desc = feature.attribute('ILS_surface')
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
       self.formLayout.setSpacing(8)
       self.formLayout.setContentsMargins(8, 8, 8, 8)
       
       # Threshold Elevation con selector de unidades
       self.thrElevLineEdit = QtWidgets.QLineEdit(self)
       self.thrElevLineEdit.setValidator(validator)
       self.thrElevLineEdit.setText("0")
       self.thrElevLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('THR_elev', text))
       self.thrElevLineEdit.setMinimumHeight(25)
       
       self.thrElevUnitCombo = QtWidgets.QComboBox(self)
       self.thrElevUnitCombo.addItems(['m', 'ft'])
       self.thrElevUnitCombo.currentTextChanged.connect(
           lambda text: self.update_unit('THR_elev', text))
       self.thrElevUnitCombo.setMinimumHeight(25)
       self.thrElevUnitCombo.setMinimumWidth(45)
       
       # Crear un widget contenedor para el campo y el selector de unidades
       thrElevContainer = QtWidgets.QWidget(self)
       thrElevLayout = QtWidgets.QHBoxLayout(thrElevContainer)
       thrElevLayout.setContentsMargins(0, 0, 0, 0)
       thrElevLayout.setSpacing(5)
       thrElevLayout.addWidget(self.thrElevLineEdit)
       thrElevLayout.addWidget(self.thrElevUnitCombo)
       
       # Añadir el widget al formulario
       self.formLayout.addRow("Threshold Elevation:", thrElevContainer)
       
       # Delta
       self.deltaLineEdit = QtWidgets.QLineEdit(self)
       self.deltaLineEdit.setValidator(validator)
       self.deltaLineEdit.setText("0")
       self.deltaLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('delta', text))
       self.deltaLineEdit.setMinimumHeight(25)
       
       # Añadir el widget al formulario
       self.formLayout.addRow("Delta:", self.deltaLineEdit)
   
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
       
       if not self.runwayLayerComboBox.currentLayer():
           self.log("Error: Please select a runway layer")
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
       runway_layer = self.runwayLayerComboBox.currentLayer()
       
       # Usar valores exactos si están disponibles, de lo contrario usar los valores de los QLineEdit
       THR_elev = self.exact_values.get('THR_elev', self.thrElevLineEdit.text())
       delta = self.exact_values.get('delta', self.deltaLineEdit.text())
       
       export_kml = self.exportKmlCheckBox.isChecked()
       output_dir = self.outputFolderLineEdit.text()
       
       # Prepare parameters
       params = {
           'THR_elev': THR_elev,
           'delta': delta,
           'export_kml': export_kml,
           'output_dir': output_dir,
           # Añadir información de unidades
           'THR_elev_unit': self.units.get('THR_elev', 'm')
       }
       
       # Registrar las unidades utilizadas
       self.log(f"Using units - Threshold Elevation: {self.units.get('THR_elev', 'm')}")
       
       try:
           # Run calculation for OAS ILS
           self.log("Running OAS ILS CAT I calculation...")
           # Import here to avoid circular imports
           from .modules.oas_ils import calculate_oas_ils
           result = calculate_oas_ils(self.iface, point_layer, runway_layer, params)
           
           # Log results
           if result:
               if export_kml:
                   self.log(f"OAS ILS KML exported to: {result.get('oas_path', 'N/A')}")
               self.log("Calculation completed successfully!")
               self.log("You can now use the 'Copy Parameters to Clipboard' button to copy the parameters for documentation.")
           else:
               self.log("Calculation completed but no results were returned.")
               
       except Exception as e:
           self.log(f"Error during calculation: {str(e)}")
           import traceback
           self.log(traceback.format_exc())