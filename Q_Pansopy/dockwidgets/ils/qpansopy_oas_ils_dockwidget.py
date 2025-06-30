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
import datetime  # Añadido para la función de copia de parámetros

# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
   os.path.dirname(__file__), '..', '..', 'ui', 'ils', 'qpansopy_oas_ils_dockwidget.ui'))


class QPANSOPYOASILSDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

   closingPlugin = pyqtSignal()

   def __init__(self, iface):
       """Constructor."""
       super(QPANSOPYOASILSDockWidget, self).__init__(iface.mainWindow())
       # Set up the user interface from Designer.
       self.setupUi(self)
       self.iface = iface
       
       # Variable para almacenar la ruta del archivo CSV cargado
       self.csv_path = None
       
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
       
       # Conectar el botón de carga de CSV si existe
       if hasattr(self, 'loadCsvButton'):
           self.loadCsvButton.clicked.connect(self.load_csv)
       
       # Set default output folder
       self.outputFolderLineEdit.setText(self.get_desktop_path())
       
       # Filter layers in comboboxes
       self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
       self.runwayLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
       
       # Reemplazar los spinboxes con QLineEdit y añadir selectores de unidades
       self.setup_lineedits()
       
       # Añadir botón para copiar parámetros
       self.setup_copy_button()
       
       # Limitar el tamaño del área de log
       if hasattr(self, 'logTextEdit') and self.logTextEdit is not None:
           self.logTextEdit.setMaximumHeight(120)
           self.logTextEdit.setVisible(True)  # El valor real lo pone qpansopy.py
       
       # Asegura que el checkbox de KML existe
       if not hasattr(self, "exportKmlCheckBox") or self.exportKmlCheckBox is None:
           self.exportKmlCheckBox = QtWidgets.QCheckBox("Export to KML", self)
           self.exportKmlCheckBox.setChecked(True)
           self.verticalLayout.addWidget(self.exportKmlCheckBox)
       
       # Log message
       self.log("QPANSOPY OAS ILS plugin loaded. Select layers and parameters, then click Calculate.")
   
   def load_csv(self):
       """Cargar un archivo CSV con constantes OAS"""
       from PyQt5.QtWidgets import QFileDialog
       
       csv_path, _ = QFileDialog.getOpenFileName(
           self,
           "Select CSV File with OAS Constants",
           "",
           "CSV Files (*.csv);;All Files (*)"
       )
       
       if csv_path:
           self.csv_path = csv_path
           self.log(f"CSV file loaded: {os.path.basename(csv_path)}")
           self.iface.messageBar().pushMessage("QPANSOPY", f"CSV file loaded: {os.path.basename(csv_path)}", level=Qgis.Info)
   
   def setup_copy_button(self):
       """Configurar botones para copiar parámetros al portapapeles"""
       # Crear un layout horizontal para los botones
       buttons_layout = QtWidgets.QHBoxLayout()
       
       # Botón para copiar como texto formateado (Word)
       self.copyParamsWordButton = QtWidgets.QPushButton("Copy for Word", self)
       self.copyParamsWordButton.clicked.connect(self.copy_parameters_for_word)
       self.copyParamsWordButton.setMinimumHeight(30)
       
       # Botón para copiar como JSON
       self.copyParamsJsonButton = QtWidgets.QPushButton("Copy as JSON", self)
       self.copyParamsJsonButton.clicked.connect(self.copy_parameters_as_json)
       self.copyParamsJsonButton.setMinimumHeight(30)
       
       buttons_layout.addWidget(self.copyParamsWordButton)
       buttons_layout.addWidget(self.copyParamsJsonButton)
       
       # Crear un widget contenedor para el layout
       buttons_widget = QtWidgets.QWidget(self)
       buttons_widget.setLayout(buttons_layout)
       
       # Añadir el widget al layout existente
       self.verticalLayout.addWidget(buttons_widget)

   def copy_parameters_for_word(self):
       """Copiar los parámetros OAS ILS en formato tabla para Word"""
       layers = QgsProject.instance().mapLayers().values()
       vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
       params_text = "QPANSOPY OAS ILS CALCULATION PARAMETERS\n"
       params_text += "=" * 50 + "\n\n"
       found_params = False
       for layer in vector_layers:
           if 'parameters' in [field.name() for field in layer.fields()]:
               has_oas_params = False
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       try:
                           params_dict = json.loads(params_json)
                           if 'calculation_type' in params_dict and 'OAS ILS' in params_dict['calculation_type']:
                               has_oas_params = True
                               break
                       except Exception:
                           pass
           if has_oas_params:
               params_text += f"LAYER: {layer.name()}\n"
               params_text += "-" * 30 + "\n\n"
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       found_params = True
                       try:
                           params_dict = json.loads(params_json)
                           params_text += "PARAMETER\t\t\tVALUE\t\tUNIT\n"
                           params_text += "-" * 50 + "\n"
                           for key, value in params_dict.items():
                               if key.endswith('_unit'):
                                   continue
                               display_name = key.replace('_', ' ').title()
                               unit = ""
                               unit_key = key + '_unit'
                               if unit_key in params_dict:
                                   unit = params_dict[unit_key]
                               params_text += f"{display_name:<25}\t{value}\t\t{unit}\n"
                           if 'ILS_surface' in [field.name() for field in layer.fields()]:
                               surface_type = feature.attribute('ILS_surface')
                               if surface_type:
                                   params_text += f"\nSurface Type: {surface_type}\n"
                           params_text += "\n"
                           break
                       except Exception:
                           params_text += "Error: Could not parse parameters JSON\n\n"
               params_text += "\n"
       if not found_params:
           params_text += "No OAS ILS parameters found in any layer. Please run a calculation first.\n"
       clipboard = QtWidgets.QApplication.clipboard()
       clipboard.setText(params_text)
       self.log("OAS ILS parameters copied to clipboard in Word format. You can now paste them into Word.")
       self.iface.messageBar().pushMessage("QPANSOPY", "OAS ILS parameters copied to clipboard in Word format", level=Qgis.Success)

   def copy_parameters_as_json(self):
       """Copiar los parámetros de las capas seleccionadas al portapapeles en formato JSON"""
       layers = QgsProject.instance().mapLayers().values()
       vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
       all_params = {
           "metadata": {
               "plugin": "QPANSOPY OAS ILS",
               "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "version": "1.0"
           },
           "layers": []
       }
       found_params = False
       oas_layers = []
       for layer in vector_layers:
           if 'parameters' in [field.name() for field in layer.fields()]:
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       try:
                           params_dict = json.loads(params_json)
                           if 'calculation_type' in params_dict and 'OAS ILS' in params_dict['calculation_type']:
                               if layer not in oas_layers:
                                   oas_layers.append(layer)
                               found_params = True
                       except Exception:
                           pass
       if not oas_layers:
           for layer in vector_layers:
               if 'parameters' in [field.name() for field in layer.fields()]:
                   oas_layers.append(layer)
       for layer in oas_layers:
           layer_data = {
               "name": layer.name(),
               "features": []
           }
           for feature in layer.getFeatures():
               params_json = feature.attribute('parameters')
               if params_json:
                   try:
                       params_dict = json.loads(params_json)
                       surface_type = "Unknown"
                       if 'ILS_surface' in [field.name() for field in layer.fields()]:
                           surface_type = feature.attribute('ILS_surface')
                       feature_data = {
                           "id": feature.id(),
                           "surface_type": surface_type,
                           "parameters": params_dict
                       }
                       layer_data["features"].append(feature_data)
                       found_params = True
                   except Exception:
                       continue
           if layer_data["features"]:
               all_params["layers"].append(layer_data)
       if not found_params:
           all_params["error"] = "No OAS ILS parameters found in any layer. Please run a calculation first."
       json_text = json.dumps(all_params, indent=2)
       clipboard = QtWidgets.QApplication.clipboard()
       clipboard.setText(json_text)
       self.log("OAS ILS parameters copied to clipboard as JSON. You can now paste them into a JSON editor or processing tool.")
       self.iface.messageBar().pushMessage("QPANSOPY", "OAS ILS parameters copied to clipboard as JSON", level=Qgis.Success)
   
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
       
       # FAP Elevation (ft)
       self.fapElevLineEdit = QtWidgets.QLineEdit(self)
       self.fapElevLineEdit.setValidator(validator)
       self.fapElevLineEdit.setText("2000")
       self.fapElevLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('FAP_elev', text))
       self.fapElevLineEdit.setMinimumHeight(25)
       
       # Añadir el widget al formulario
       self.formLayout.addRow("FAP Elevation (ft):", self.fapElevLineEdit)
       
       # MOC Intermediate (m)
       self.mocIntermediateLineEdit = QtWidgets.QLineEdit(self)
       self.mocIntermediateLineEdit.setValidator(validator)
       self.mocIntermediateLineEdit.setText("150")
       self.mocIntermediateLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('MOC_intermediate', text))
       self.mocIntermediateLineEdit.setMinimumHeight(25)
       
       # Añadir el widget al formulario
       self.formLayout.addRow("MOC Intermediate (m):", self.mocIntermediateLineEdit)
       
       # OAS Type
       self.oasTypeComboBox = QtWidgets.QComboBox(self)
       self.oasTypeComboBox.addItems(["Template Only", "Extended Only", "Both"])
       self.oasTypeComboBox.setCurrentText("Both")
       self.oasTypeComboBox.setMinimumHeight(25)
       
       # Añadir el widget al formulario
       self.formLayout.addRow("OAS Type:", self.oasTypeComboBox)
   
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
       FAP_elev = self.exact_values.get('FAP_elev', self.fapElevLineEdit.text())
       MOC_intermediate = self.exact_values.get('MOC_intermediate', self.mocIntermediateLineEdit.text())
       oas_type = self.oasTypeComboBox.currentText()
       
       export_kml = self.exportKmlCheckBox.isChecked()
       output_dir = self.outputFolderLineEdit.text()
       
       # Prepare parameters
       params = {
           'THR_elev': THR_elev,
           'delta': delta,
           'FAP_elev': FAP_elev,
           'MOC_intermediate': MOC_intermediate,
           'oas_type': oas_type,
           'export_kml': export_kml,
           'output_dir': output_dir,
           # Añadir información de unidades
           'THR_elev_unit': self.units.get('THR_elev', 'm'),
           # Añadir ruta del CSV si está disponible
           'csv_path': self.csv_path
       }
       
       # Registrar las unidades utilizadas
       self.log(f"Using units - Threshold Elevation: {self.units.get('THR_elev', 'm')}")
       self.log(f"FAP Elevation: {FAP_elev} ft, MOC Intermediate: {MOC_intermediate} m")
       self.log(f"OAS Type: {oas_type}")
       
       try:
           # Run calculation for OAS ILS
           self.log("Running OAS ILS CAT I calculation...")
           # Import here to avoid circular imports
           from ...modules.oas_ils import calculate_oas_ils
           result = calculate_oas_ils(self.iface, point_layer, runway_layer, params)
           
           # Log results
           if result:
               if export_kml:
                   # Log each KML path if available
                   for key, value in result.items():
                       if key.startswith('oas_path_'):
                           self.log(f"OAS ILS KML ({key.replace('oas_path_', '')}) exported to: {value}")
               self.log("Calculation completed successfully!")
               self.log("You can now use the 'Copy Parameters to Clipboard' button to copy the parameters for documentation.")
           else:
               self.log("Calculation completed but no results were returned.")
               
       except Exception as e:
           self.log(f"Error during calculation: {str(e)}")
           import traceback
           self.log(traceback.format_exc())