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
import json
import datetime
import traceback
from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, QFileInfo, Qt, QRegExp, QMimeData
from PyQt5.QtGui import QRegExpValidator
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes, QgsCoordinateReferenceSystem, QgsMapLayerProxyModel
from qgis.utils import iface
from qgis.core import Qgis

# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
   os.path.dirname(__file__), '..', '..', 'ui', 'ils', 'qpansopy_oas_ils_dockwidget.ui'))


class QPANSOPYOASILSDockWidgetBase(QtWidgets.QDockWidget, FORM_CLASS):

   closingPlugin = pyqtSignal()

   def __init__(self, iface):
       """Constructor."""
       super(QPANSOPYOASILSDockWidgetBase, self).__init__(iface.mainWindow())
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
       
       # Configure the dock widget to be resizable without forcing main window geometry
       self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                        QtWidgets.QDockWidget.DockWidgetFloatable |
                        QtWidgets.QDockWidget.DockWidgetClosable)
       try:
           self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
       except Exception:
           pass
       # Aumentar el espaciado en los layouts
       self.verticalLayout.setSpacing(8)
       self.verticalLayout.setContentsMargins(8, 8, 8, 8)
       
       # Connect signals
       self.calculateButton.clicked.connect(self.calculate)
       self.browseButton.clicked.connect(self.browse_output_folder)
       
       # Remove the redundant load CSV button functionality
       # CSV loading is now mandatory during calculation
       
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
           # Use a preferred height but don't enforce a hard maximum
           try:
               self.logTextEdit.setMaximumHeight(0)  # 0 means no max; layout manages size
           except Exception:
               pass
           self.logTextEdit.setVisible(True)  # El valor real lo pone qpansopy.py
       
       # Asegura que el checkbox de KML existe
       if not hasattr(self, "exportKmlCheckBox") or self.exportKmlCheckBox is None:
           self.exportKmlCheckBox = QtWidgets.QCheckBox("Export to KML", self)
           self.exportKmlCheckBox.setChecked(True)
           self.verticalLayout.addWidget(self.exportKmlCheckBox)
       
       # Log message
       self.log("QPANSOPY OAS ILS plugin loaded. Select layers and parameters, then click Calculate.")
       self.log("Note: A CSV file with OAS constants will be required when you click Calculate.")
   
   def request_csv_file(self):
       """Request CSV file from user - mandatory for calculation"""
       from PyQt5.QtWidgets import QFileDialog
       
       csv_path, _ = QFileDialog.getOpenFileName(
           self,
           "Select CSV File with OAS Constants (Required)",
           "",
           "CSV Files (*.csv);;All Files (*)"
       )
       
       if csv_path:
           # Validate that the file exists and is readable
           if os.path.exists(csv_path):
               try:
                   with open(csv_path, 'r', encoding='utf-8-sig') as f:
                       # Try to read first few lines to validate format
                       lines = f.readlines()[:10]
                       # Accept any CSV; skip format warning
                       self.csv_path = csv_path
                       self.log(f"CSV file selected: {os.path.basename(csv_path)}")
                       self.iface.messageBar().pushMessage("QPANSOPY", f"OAS Constants file loaded: {os.path.basename(csv_path)}", level=Qgis.Success)
                       return True
               except Exception as e:
                   error_msg = f"Error reading CSV file: {str(e)}"
                   self.log(error_msg)
                   self.iface.messageBar().pushMessage("QPANSOPY Error", error_msg, level=Qgis.Critical)
                   return False
           else:
               error_msg = "Selected CSV file does not exist"
               self.log(error_msg)
               self.iface.messageBar().pushMessage("QPANSOPY Error", error_msg, level=Qgis.Critical)
               return False
       else:
           error_msg = "OAS Constants file is required for calculation"
           self.log(error_msg)
           self.iface.messageBar().pushMessage("QPANSOPY", error_msg, level=Qgis.Warning)
           return False
   
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
       import json
       from ...utils import format_parameters_table
       
       layers = QgsProject.instance().mapLayers().values()
       vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
       html_chunks = []
       found_params = False
       
       for layer in vector_layers:
           has_oas_params = False
           if 'parameters' in [field.name() for field in layer.fields()]:
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       try:
                           params_dict = json.loads(params_json)
                           if 'calculation_type' in params_dict and 'OAS ILS' in params_dict['calculation_type']:
                               has_oas_params = True
                               # Build table data
                               layer_params = {}
                               layer_sections = {}
                               thr_value = params_dict.get('THR_elev', '')
                               thr_unit = params_dict.get('THR_elev_unit', 'm')
                               layer_params['THR_elev'] = {'value': thr_value, 'unit': thr_unit}
                               layer_sections['THR_elev'] = 'Runway Data'
                               
                               layer_params['FAP_elev'] = {'value': params_dict.get('FAP_elev', ''), 'unit': 'ft'}
                               layer_sections['FAP_elev'] = 'Calculation Inputs'
                               
                               layer_params['MOC_intermediate'] = {'value': params_dict.get('MOC_intermediate', ''), 'unit': 'm'}
                               layer_sections['MOC_intermediate'] = 'Calculation Inputs'
                               
                               layer_params['calculation_date'] = {'value': params_dict.get('calculation_date', ''), 'unit': ''}
                               layer_sections['calculation_date'] = 'Calculation Info'
                               
                               layer_params['calculation_type'] = {'value': params_dict.get('calculation_type', ''), 'unit': ''}
                               layer_sections['calculation_type'] = 'Calculation Info'
                               
                               if 'ILS_surface' in [field.name() for field in layer.fields()]:
                                   surface_type = feature.attribute('ILS_surface') or ''
                                   layer_params['surface_type'] = {'value': surface_type, 'unit': ''}
                                   layer_sections['surface_type'] = 'Surface Information'
                               
                               table_html = format_parameters_table(
                                   "QPANSOPY OAS ILS PARAMETERS",
                                   layer_params,
                                   layer_sections
                               )
                               html_chunks.append(f"<h3>LAYER: {layer.name()}</h3>" + table_html)
                               found_params = True
                               break
                       except Exception:
                           pass
           
           if has_oas_params:
               continue
       
       if not found_params:
           html_chunks.append("<p>No OAS ILS parameters found in any layer. Please run a calculation first.</p>")
       
       html_content = "<div>" + "<br>".join(html_chunks) + "</div>"
       mime = QMimeData()
       mime.setHtml(html_content)
       mime.setText("\n\n".join([chunk.replace('<', '').replace('>', '') for chunk in html_chunks]))
       clipboard = QtWidgets.QApplication.clipboard()
       clipboard.setMimeData(mime)
       
       self.log("OAS ILS parameters copied to clipboard in Word format (HTML table).")
       self.iface.messageBar().pushMessage("QPANSOPY", "OAS ILS parameters copied to clipboard in Word format", level=Qgis.Success)

   def copy_parameters_as_json(self):
       """Copiar los parámetros de las capas seleccionadas al portapapeles en formato JSON"""
       import json
       import datetime
       
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
       
       # First identify OAS ILS layers
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
                       except json.JSONDecodeError:
                           pass
       
       # Process identified layers
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
                       
                       # Get surface type
                       surface_type = "Unknown"
                       if 'ILS_surface' in [field.name() for field in layer.fields()]:
                           surface_type = feature.attribute('ILS_surface')
                       
                       # Add to structure
                       feature_data = {
                           "id": feature.id(),
                           "surface_type": surface_type,
                           "parameters": params_dict
                       }
                       
                       layer_data["features"].append(feature_data)
                       found_params = True
                   except json.JSONDecodeError:
                       continue
           
           # Add layer only if it has features with parameters
           if layer_data["features"]:
               all_params["layers"].append(layer_data)
       
       if not found_params:
           all_params["error"] = "No OAS ILS parameters found in any layer. Please run a calculation first."
       
       # Convert to JSON with pretty formatting
       json_text = json.dumps(all_params, indent=2)
       
       # Copy to clipboard
       clipboard = QtWidgets.QApplication.clipboard()
       clipboard.setText(json_text)
       
       # Show success message
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
       
       # Delta - Hidden for now, kept for future use
       self.deltaLineEdit = QtWidgets.QLineEdit(self)
       self.deltaLineEdit.setValidator(validator)
       self.deltaLineEdit.setText("0")
       self.deltaLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('delta', text))
       self.deltaLineEdit.setMinimumHeight(25)
       self.deltaLineEdit.setVisible(False)  # Hide the Delta field
       
       # Don't add Delta to the form layout (hidden)
       
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
   
   def convert_threshold_elevation_to_meters(self, thr_elev_value, unit):
       """Convert threshold elevation to meters based on selected unit"""
       try:
           value = float(thr_elev_value)
           if unit == 'ft':
               # Convert feet to meters (1 ft = 0.3048 m)
               return value * 0.3048
           else:
               # Already in meters
               return value
       except (ValueError, TypeError):
           return 0.0
   
   def calculate(self):
       """Run the calculation"""
       self.log("Starting calculation...")
       
       # First, request CSV file - this is mandatory
       if not self.request_csv_file():
           return
       
       # Validate inputs
       if not self.validate_inputs():
           return
       
       # Get parameters
       point_layer = self.pointLayerComboBox.currentLayer()
       runway_layer = self.runwayLayerComboBox.currentLayer()
       
       # Get raw values from UI
       THR_elev_raw = self.exact_values.get('THR_elev', self.thrElevLineEdit.text())
       THR_elev_unit = self.units.get('THR_elev', 'm')
       
       # Convert threshold elevation to meters for internal calculations
       THR_elev_meters = self.convert_threshold_elevation_to_meters(THR_elev_raw, THR_elev_unit)
       
       # Other parameters (already in correct units)
       delta = self.exact_values.get('delta', self.deltaLineEdit.text())
       FAP_elev = self.exact_values.get('FAP_elev', self.fapElevLineEdit.text())
       MOC_intermediate = self.exact_values.get('MOC_intermediate', self.mocIntermediateLineEdit.text())
       oas_type = self.oasTypeComboBox.currentText()
       
       export_kml = self.exportKmlCheckBox.isChecked()
       output_dir = self.outputFolderLineEdit.text()
       
       # Prepare parameters
       params = {
           'THR_elev': THR_elev_meters,  # Use converted value in meters
           'THR_elev_raw': THR_elev_raw,  # Keep original value for documentation
           'delta': delta,
           'FAP_elev': FAP_elev,
           'MOC_intermediate': MOC_intermediate,
           'oas_type': oas_type,
           'export_kml': export_kml,
           'output_dir': output_dir,
           # Añadir información de unidades
           'THR_elev_unit': THR_elev_unit,
           # Añadir ruta del CSV si está disponible
           'csv_path': self.csv_path
       }
       
       # Registrar las unidades utilizadas y la conversión
       self.log(f"Threshold Elevation: {THR_elev_raw} {THR_elev_unit} = {THR_elev_meters:.4f} m (converted)")
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
           error_msg = f"Error during calculation: {str(e)}"
           self.log(error_msg)
           # Also show as an info message for better UX as requested by client
           self.iface.messageBar().pushMessage("QPANSOPY Error", error_msg, level=Qgis.Critical)
           self.log(traceback.format_exc())