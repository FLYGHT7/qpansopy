# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYILSDockWidget
                                A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - ILS Module
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
import datetime

# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
   os.path.dirname(__file__), '..', '..', 'ui', 'ils', 'qpansopy_ils_dockwidget.ui'))


class QPANSOPYILSDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

   closingPlugin = pyqtSignal()

   def __init__(self, iface):
       """Constructor."""
       super(QPANSOPYILSDockWidget, self).__init__(iface.mainWindow())
       # Set up the user interface from Designer.
       self.setupUi(self)
       self.iface = iface
       
       # Diccionario para almacenar los valores exactos ingresados
       self.exact_values = {}
       # Diccionario para almacenar las unidades seleccionadas
       self.units = {
           'thr_elev': 'm'
       }
       
       # Configure the dock widget to be resizable
       self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                        QtWidgets.QDockWidget.DockWidgetFloatable |
                        QtWidgets.QDockWidget.DockWidgetClosable)
       
       # Set minimum and maximum sizes
       self.setMinimumHeight(300)
       self.setMaximumHeight(600)
       
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
       
       # Asegurar que el log se puede ocultar sin error
       if hasattr(self, "logTextEdit") and self.logTextEdit is not None:
           self.logTextEdit.setVisible(True)
       # Asegura que el checkbox de KML existe
       if not hasattr(self, "exportKmlCheckBox") or self.exportKmlCheckBox is None:
           self.exportKmlCheckBox = QtWidgets.QCheckBox("Export to KML", self)
           self.exportKmlCheckBox.setChecked(True)
           self.verticalLayout.addWidget(self.exportKmlCheckBox)
       
       # Log message
       self.log("QPANSOPY ILS plugin loaded. Select layers and parameters, then click Calculate.")
   
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
   
   def copy_parameters_for_word(self):
       """Copiar los parámetros en formato tabla para Word"""
       # Obtener todas las capas del proyecto
       layers = QgsProject.instance().mapLayers().values()
       
       # Filtrar solo las capas vectoriales que podrían contener nuestros parámetros
       vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
       
       # Buscar capas que tengan el campo 'parameters' y sean de tipo ILS
       params_text = "QPANSOPY BASIC ILS CALCULATION PARAMETERS\n"
       params_text += "=" * 50 + "\n\n"
       
       found_params = False
       
       for layer in vector_layers:
           if 'parameters' in [field.name() for field in layer.fields()]:
               # Verificar si es una capa ILS
               has_ils_params = False
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       try:
                           params_dict = json.loads(params_json)
                           if 'calculation_type' in params_dict and 'Basic ILS' in params_dict['calculation_type']:
                               has_ils_params = True
                               break
                       except json.JSONDecodeError:
                           pass
        
           if has_ils_params:
               params_text += f"LAYER: {layer.name()}\n"
               params_text += "-" * 30 + "\n\n"
               
               # Obtener los parámetros de la primera feature (todos deberían tener los mismos parámetros)
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       found_params = True
                       try:
                           params_dict = json.loads(params_json)
                           
                           # Crear tabla formateada
                           params_text += "PARAMETER\t\t\tVALUE\t\tUNIT\n"
                           params_text += "-" * 50 + "\n"
                           
                           # Mapear parámetros a nombres más legibles
                           param_names = {
                               'thr_elev': 'Threshold Elevation',
                               'calculation_type': 'Calculation Type',
                               'calculation_date': 'Calculation Date',
                               'thr_elev_unit': 'Threshold Elevation Unit'
                           }
                           
                           # Formatear parámetros en tabla
                           for key, value in params_dict.items():
                               if key.endswith('_unit'):
                                   continue  # Skip unit fields, they'll be handled with their main parameter
                                
                               display_name = param_names.get(key, key.replace('_', ' ').title())
                               unit = ""
                               
                               # Obtener unidad si existe
                               unit_key = key + '_unit'
                               if unit_key in params_dict:
                                   unit = params_dict[unit_key]
                               
                               # Formatear la línea
                               params_text += f"{display_name:<25}\t{value}\t\t{unit}\n"
                           
                           # Añadir información de la superficie si está disponible
                           if 'ILS_surface' in [field.name() for field in layer.fields()]:
                               surface_type = feature.attribute('ILS_surface')
                               if surface_type:
                                   params_text += f"\nSurface Type: {surface_type}\n"
                           
                           params_text += "\n"
                           break  # Solo necesitamos los parámetros de una feature
                       except json.JSONDecodeError:
                           params_text += "Error: Could not parse parameters JSON\n\n"
                
               params_text += "\n"
    
       if not found_params:
           params_text += "No Basic ILS parameters found in any layer. Please run a calculation first.\n"
    
       # Copiar al portapapeles
       clipboard = QtWidgets.QApplication.clipboard()
       clipboard.setText(params_text)
    
       # Mostrar mensaje de éxito
       self.log("Parameters copied to clipboard in Word format. You can now paste them into Word.")
       self.iface.messageBar().pushMessage("QPANSOPY", "Parameters copied to clipboard in Word format", level=Qgis.Success)

   def copy_parameters_as_json(self):
       """Copiar los parámetros de las capas seleccionadas al portapapeles en formato JSON"""
       # Obtener todas las capas del proyecto
       layers = QgsProject.instance().mapLayers().values()
    
       # Filtrar solo las capas vectoriales que podrían contener nuestros parámetros
       vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
    
       # Estructura para almacenar los parámetros
       all_params = {
           "metadata": {
               "plugin": "QPANSOPY Basic ILS",
               "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "version": "1.0"
           },
           "layers": []
       }
    
       found_params = False
       ils_layers = []
    
       # Primero identificar las capas ILS
       for layer in vector_layers:
           if 'parameters' in [field.name() for field in layer.fields()]:
               # Verificar si es una capa ILS
               for feature in layer.getFeatures():
                   params_json = feature.attribute('parameters')
                   if params_json:
                       try:
                           params_dict = json.loads(params_json)
                           if 'calculation_type' in params_dict and 'Basic ILS' in params_dict['calculation_type']:
                               if layer not in ils_layers:
                                   ils_layers.append(layer)
                               found_params = True
                       except json.JSONDecodeError:
                           pass
    
       # Procesar las capas identificadas
       for layer in ils_layers:
           layer_data = {
               "name": layer.name(),
               "features": []
           }
        
           for feature in layer.getFeatures():
               params_json = feature.attribute('parameters')
               if params_json:
                   try:
                       params_dict = json.loads(params_json)
                    
                       # Obtener el tipo de superficie
                       surface_type = "Unknown"
                       if 'ILS_surface' in [field.name() for field in layer.fields()]:
                           surface_type = feature.attribute('ILS_surface')
                    
                       # Añadir a la estructura
                       feature_data = {
                           "id": feature.id(),
                           "surface_type": surface_type,
                           "parameters": params_dict
                       }
                    
                       layer_data["features"].append(feature_data)
                       found_params = True
                   except json.JSONDecodeError:
                       continue
        
           # Añadir la capa solo si tiene features con parámetros
           if layer_data["features"]:
               all_params["layers"].append(layer_data)
    
       if not found_params:
           all_params["error"] = "No Basic ILS parameters found in any layer. Please run a calculation first."
    
       # Convertir a JSON con formato bonito
       json_text = json.dumps(all_params, indent=2)
    
       # Copiar al portapapeles
       clipboard = QtWidgets.QApplication.clipboard()
       clipboard.setText(json_text)
    
       # Mostrar mensaje de éxito
       self.log("Basic ILS parameters copied to clipboard as JSON. You can now paste them into a JSON editor or processing tool.")
       self.iface.messageBar().pushMessage("QPANSOPY", "Basic ILS parameters copied to clipboard as JSON", level=Qgis.Success)
   
   def setup_lineedits(self):
       """Configurar QLineEdit para los campos numéricos y añadir selectores de unidades"""
       # Crear un validador para números decimales
       regex = QRegExp(r"[-+]?[0-9]*\.?[0-9]+")
       validator = QRegExpValidator(regex)
       
       # Threshold Elevation con selector de unidades
       self.thrElevLineEdit = QtWidgets.QLineEdit(self)
       self.thrElevLineEdit.setValidator(validator)
       self.thrElevLineEdit.setText(str(self.thrElevSpinBox.value()))
       self.thrElevLineEdit.textChanged.connect(
           lambda text: self.store_exact_value('thr_elev', text))
       
       self.thrElevUnitCombo = QtWidgets.QComboBox(self)
       self.thrElevUnitCombo.addItems(['m', 'ft'])
       self.thrElevUnitCombo.currentTextChanged.connect(
           lambda text: self.update_unit('thr_elev', text))
       
       # Crear un widget contenedor para el campo y el selector de unidades
       thrElevContainer = QtWidgets.QWidget(self)
       thrElevLayout = QtWidgets.QHBoxLayout(thrElevContainer)
       thrElevLayout.setContentsMargins(0, 0, 0, 0)
       thrElevLayout.addWidget(self.thrElevLineEdit)
       thrElevLayout.addWidget(self.thrElevUnitCombo)
       
       # Reemplazar el widget en el formulario
       self.replace_widget_in_form(self.thrElevSpinBox, thrElevContainer)
   
   def update_unit(self, param_name, unit):
       """Actualizar la unidad seleccionada para un parámetro"""
       self.units[param_name] = unit
   
   def replace_widget_in_form(self, old_widget, new_widget):
       """Reemplazar un widget en un QFormLayout"""
       parent = old_widget.parent()
       form_layout = parent.layout()
       
       # Encontrar la fila donde está el widget
       for i in range(form_layout.rowCount()):
           if form_layout.itemAt(i, QtWidgets.QFormLayout.FieldRole) and form_layout.itemAt(i, QtWidgets.QFormLayout.FieldRole).widget() == old_widget:
               # Obtener la etiqueta
               label_item = form_layout.itemAt(i, QtWidgets.QFormLayout.LabelRole)
               
               # Eliminar el widget antiguo
               form_layout.removeWidget(old_widget)
               old_widget.hide()
               
               # Añadir el nuevo widget
               form_layout.setWidget(i, QtWidgets.QFormLayout.FieldRole, new_widget)
               break
   
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
       
       # Check if both layers are in projected CRS
       point_layer = self.pointLayerComboBox.currentLayer()
       if point_layer.crs().isGeographic():
           self.log("Warning: Point layer should be in a projected coordinate system")
           # Continue anyway, but warn the user
       
       # Check if runway layer is in a projected CRS
       runway_layer = self.runwayLayerComboBox.currentLayer()
       if runway_layer.crs().isGeographic():
           self.log("Warning: Runway layer should be in a projected coordinate system")
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
       runway_layer = self.runwayLayerComboBox.currentLayer()
       
       # Usar valores exactos si están disponibles, de lo contrario usar los valores de los QLineEdit
       thr_elev = self.exact_values.get('thr_elev', self.thrElevLineEdit.text())
       
       export_kml = self.exportKmlCheckBox.isChecked()
       output_dir = self.outputFolderLineEdit.text()
       
       # Prepare parameters
       params = {
           'thr_elev': thr_elev,
           'export_kml': export_kml,
           'output_dir': output_dir,
           # Añadir información de unidades
           'thr_elev_unit': self.units.get('thr_elev', 'm')
       }
       
       # Registrar las unidades utilizadas
       self.log(f"Using units - Threshold Elevation: {self.units.get('thr_elev', 'm')}")
       
       try:
           # Run calculation for Basic ILS
           self.log("Running Basic ILS calculation...")
           # Import here to avoid circular imports
           from ...modules.basic_ils import calculate_basic_ils
           result = calculate_basic_ils(self.iface, point_layer, runway_layer, params)
           
           # Log results
           if result:
               if export_kml:
                   self.log(f"Basic ILS KML exported to: {result.get('kml_path', 'N/A')}")
               self.log("Calculation completed successfully!")
               self.log("You can now use the 'Copy Parameters to Clipboard' button to copy the parameters for documentation.")
           else:
               self.log("Calculation completed but no results were returned.")
               
       except Exception as e:
           self.log(f"Error during calculation: {str(e)}")
           import traceback
           self.log(traceback.format_exc())