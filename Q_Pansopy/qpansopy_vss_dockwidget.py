# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYVSSDockWidget
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - VSS Module
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
os.path.dirname(__file__), 'qpansopy_vss_dockwidget.ui'))


class QPANSOPYVSSDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """Constructor."""
        super(QPANSOPYVSSDockWidget, self).__init__(iface.mainWindow())
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.iface = iface
        
        # Diccionario para almacenar los valores exactos ingresados
        self.exact_values = {}
        # Diccionario para almacenar las unidades seleccionadas
        self.units = {
            'thr_elev': 'm',
            'OCH': 'm',
            'RDH': 'm'
        }
        
        # Configure the dock widget to be resizable
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable |
                         QtWidgets.QDockWidget.DockWidgetClosable)
        
        # Set minimum and maximum sizes
        self.setMinimumHeight(600)
        self.setMaximumHeight(800)
        
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
        
        # Asegura que el log se puede ocultar sin error
        if hasattr(self, "logTextEdit") and self.logTextEdit is not None:
            self.logTextEdit.setVisible(True)
        # Asegura que el checkbox de KML existe
        if not hasattr(self, "exportKmlCheckBox") or self.exportKmlCheckBox is None:
            self.exportKmlCheckBox = QtWidgets.QCheckBox("Export to KML", self)
            self.exportKmlCheckBox.setChecked(True)
            self.verticalLayout.addWidget(self.exportKmlCheckBox)
        
        # Log message
        self.log("QPANSOPY VSS plugin loaded. Select layers and parameters, then click Calculate.")

    def setup_copy_button(self):
        """Configurar botones para copiar parámetros al portapapeles"""
        buttons_layout = QtWidgets.QHBoxLayout()
        self.copyParamsWordButton = QtWidgets.QPushButton("Copy for Word", self)
        self.copyParamsWordButton.clicked.connect(self.copy_parameters_for_word)
        self.copyParamsWordButton.setMinimumHeight(30)
        self.copyParamsJsonButton = QtWidgets.QPushButton("Copy as JSON", self)
        self.copyParamsJsonButton.clicked.connect(self.copy_parameters_as_json)
        self.copyParamsJsonButton.setMinimumHeight(30)
        buttons_layout.addWidget(self.copyParamsWordButton)
        buttons_layout.addWidget(self.copyParamsJsonButton)
        buttons_widget = QtWidgets.QWidget(self)
        buttons_widget.setLayout(buttons_layout)
        self.verticalLayout.addWidget(buttons_widget)

    def copy_parameters_for_word(self):
        """Copiar los parámetros VSS en formato tabla para Word"""
        params_text = "QPANSOPY VSS CALCULATION PARAMETERS\n"
        params_text += "=" * 50 + "\n\n"
        params_text += "PARAMETER\t\t\tVALUE\t\tUNIT\n"
        params_text += "-" * 50 + "\n"
        param_names = {
            'rwy_width': 'Runway Width',
            'thr_elev': 'Threshold Elevation',
            'strip_width': 'Strip Width',
            'OCH': 'OCH',
            'RDH': 'RDH',
            'VPA': 'VPA'
        }
        params = {
            'rwy_width': self.exact_values.get('rwy_width', self.rwyWidthLineEdit.text()),
            'thr_elev': self.exact_values.get('thr_elev', self.thrElevLineEdit.text()),
            'thr_elev_unit': self.units.get('thr_elev', 'm'),
            'strip_width': self.exact_values.get('strip_width', self.stripWidthLineEdit.text()),
            'OCH': self.exact_values.get('OCH', self.OCHLineEdit.text()),
            'OCH_unit': self.units.get('OCH', 'm'),
            'RDH': self.exact_values.get('RDH', self.RDHLineEdit.text()),
            'RDH_unit': self.units.get('RDH', 'm'),
            'VPA': self.exact_values.get('VPA', self.VPALineEdit.text())
        }
        for key in ['rwy_width', 'thr_elev', 'strip_width', 'OCH', 'RDH', 'VPA']:
            display_name = param_names.get(key, key.replace('_', ' ').title())
            value = params[key]
            unit = ""
            if key == 'thr_elev':
                unit = params['thr_elev_unit']
            elif key == 'OCH':
                unit = params['OCH_unit']
            elif key == 'RDH':
                unit = params['RDH_unit']
            elif key == 'rwy_width' or key == 'strip_width':
                unit = "m"
            elif key == 'VPA':
                unit = "°"
            params_text += f"{display_name:<25}\t{value}\t\t{unit}\n"
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(params_text)
        self.log("VSS parameters copied to clipboard in Word format. You can now paste them into Word.")
        self.iface.messageBar().pushMessage("QPANSOPY", "VSS parameters copied to clipboard in Word format", level=Qgis.Success)

    def copy_parameters_as_json(self):
        """Copiar los parámetros actuales al portapapeles en formato JSON"""
        params_dict = {
            "metadata": {
                "plugin": "QPANSOPY VSS",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0"
            },
            "parameters": {
                'rwy_width': self.exact_values.get('rwy_width', self.rwyWidthLineEdit.text()),
                'thr_elev': self.exact_values.get('thr_elev', self.thrElevLineEdit.text()),
                'thr_elev_unit': self.units.get('thr_elev', 'm'),
                'strip_width': self.exact_values.get('strip_width', self.stripWidthLineEdit.text()),
                'OCH': self.exact_values.get('OCH', self.OCHLineEdit.text()),
                'OCH_unit': self.units.get('OCH', 'm'),
                'RDH': self.exact_values.get('RDH', self.RDHLineEdit.text()),
                'RDH_unit': self.units.get('RDH', 'm'),
                'VPA': self.exact_values.get('VPA', self.VPALineEdit.text())
            }
        }
        params_json = json.dumps(params_dict, indent=2)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(params_json)
        self.log("VSS parameters copied to clipboard as JSON. You can now paste them into a JSON editor or processing tool.")
        self.iface.messageBar().pushMessage("QPANSOPY", "VSS parameters copied to clipboard as JSON", level=Qgis.Success)

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
        self.replace_widget_in_form(self.thrElevSpinBox, thrElevContainer, 1)
        
        # OCH con selector de unidades
        self.OCHLineEdit = QtWidgets.QLineEdit(self)
        self.OCHLineEdit.setValidator(validator)
        self.OCHLineEdit.setText(str(self.ochSpinBox.value()))
        self.OCHLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('OCH', text))
        
        self.OCHUnitCombo = QtWidgets.QComboBox(self)
        self.OCHUnitCombo.addItems(['m', 'ft'])
        self.OCHUnitCombo.currentTextChanged.connect(
            lambda text: self.update_unit('OCH', text))
        
        # Crear un widget contenedor para el campo y el selector de unidades
        OCHContainer = QtWidgets.QWidget(self)
        OCHLayout = QtWidgets.QHBoxLayout(OCHContainer)
        OCHLayout.setContentsMargins(0, 0, 0, 0)
        OCHLayout.addWidget(self.OCHLineEdit)
        OCHLayout.addWidget(self.OCHUnitCombo)
        
        # Reemplazar el widget en el formulario
        self.replace_widget_in_form(self.ochSpinBox, OCHContainer, 3)
        
        # RDH con selector de unidades
        self.RDHLineEdit = QtWidgets.QLineEdit(self)
        self.RDHLineEdit.setValidator(validator)
        self.RDHLineEdit.setText(str(self.rdhSpinBox.value()))
        self.RDHLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('RDH', text))
        
        self.RDHUnitCombo = QtWidgets.QComboBox(self)
        self.RDHUnitCombo.addItems(['m', 'ft'])
        self.RDHUnitCombo.currentTextChanged.connect(
            lambda text: self.update_unit('RDH', text))
        
        # Crear un widget contenedor para el campo y el selector de unidades
        RDHContainer = QtWidgets.QWidget(self)
        RDHLayout = QtWidgets.QHBoxLayout(RDHContainer)
        RDHLayout.setContentsMargins(0, 0, 0, 0)
        RDHLayout.addWidget(self.RDHLineEdit)
        RDHLayout.addWidget(self.RDHUnitCombo)
        
        # Reemplazar el widget en el formulario
        self.replace_widget_in_form(self.rdhSpinBox, RDHContainer, 4)
        
        # Otros campos sin unidades
        self.rwyWidthLineEdit = QtWidgets.QLineEdit(self)
        self.rwyWidthLineEdit.setValidator(validator)
        self.rwyWidthLineEdit.setText(str(self.rwyWidthSpinBox.value()))
        self.rwyWidthLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('rwy_width', text))
        self.replace_widget_in_form(self.rwyWidthSpinBox, self.rwyWidthLineEdit, 0)
        
        self.stripWidthLineEdit = QtWidgets.QLineEdit(self)
        self.stripWidthLineEdit.setValidator(validator)
        self.stripWidthLineEdit.setText(str(self.stripWidthSpinBox.value()))
        self.stripWidthLineEdit.textChanged.connect(
            lambda text: self.store_exact_value('strip_width', text))
        self.replace_widget_in_form(self.stripWidthSpinBox, self.stripWidthLineEdit, 2)
        
        self.VPALineEdit = QtWidgets.QLineEdit(self)
        self.VPALineEdit.setValidator(validator)
        self.VPALineEdit.setText(str(self.vpaSpinBox.value()))
        self.VPALineEdit.textChanged.connect(
            lambda text: self.store_exact_value('VPA', text))
        self.replace_widget_in_form(self.vpaSpinBox, self.VPALineEdit, 5)

    def update_unit(self, param_name, unit):
        """Actualizar la unidad seleccionada para un parámetro"""
        self.units[param_name] = unit

    def replace_widget_in_form(self, old_widget, new_widget, row):
        """Reemplazar un widget en el layout de parámetros"""
        # Obtener el layout de parámetros
        layout = self.parametersFormLayout
        
        # Eliminar el widget antiguo
        layout.removeWidget(old_widget)
        old_widget.hide()
        
        # Añadir el nuevo widget
        layout.setWidget(row, QtWidgets.QFormLayout.FieldRole, new_widget)

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
        
        # Check if point layer is in WGS84
        point_layer = self.pointLayerComboBox.currentLayer()
        if not point_layer.crs().authid() == 'EPSG:4326':
            self.log("Warning: Point layer should be in WGS84 (EPSG:4326)")
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
        rwy_width = self.exact_values.get('rwy_width', self.rwyWidthLineEdit.text())
        thr_elev = self.exact_values.get('thr_elev', self.thrElevLineEdit.text())
        strip_width = self.exact_values.get('strip_width', self.stripWidthLineEdit.text())
        OCH = self.exact_values.get('OCH', self.OCHLineEdit.text())
        RDH = self.exact_values.get('RDH', self.RDHLineEdit.text())
        VPA = self.exact_values.get('VPA', self.VPALineEdit.text())
        
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()
        
        # Prepare parameters
        params = {
            'rwy_width': rwy_width,
            'thr_elev': thr_elev,
            'strip_width': strip_width,
            'OCH': OCH,
            'RDH': RDH,
            'VPA': VPA,
            'export_kml': export_kml,
            'output_dir': output_dir,
            # Añadir información de unidades
            'thr_elev_unit': self.units.get('thr_elev', 'm'),
            'OCH_unit': self.units.get('OCH', 'm'),
            'RDH_unit': self.units.get('RDH', 'm')
        }
        
        # Registrar las unidades utilizadas
        self.log(f"Using units - Threshold Elevation: {self.units.get('thr_elev', 'm')}, OCH: {self.units.get('OCH', 'm')}, RDH: {self.units.get('RDH', 'm')}")
        
        try:
            # Run calculation for selected type
            # CORRECCIÓN: Usar straightInNPARadioButton en lugar de straightRadioButton
            if self.straightInNPARadioButton.isChecked():
                self.log("Running Straight In calculation...")
                # Import here to avoid circular imports
                from .modules.vss_straight import calculate_vss_straight
                result = calculate_vss_straight(self.iface, point_layer, runway_layer, params)
            else:  # LOC is selected
                self.log("Running LOC calculation...")
                # Import here to avoid circular imports
                from .modules.vss_loc import calculate_vss_loc
                result = calculate_vss_loc(self.iface, point_layer, runway_layer, params)
            
            # Log results
            if result:
                if export_kml:
                    self.log(f"VSS KML exported to: {result.get('vss_path', 'N/A')}")
                    self.log(f"OCS KML exported to: {result.get('ocs_path', 'N/A')}")
                self.log("Calculation completed successfully!")
                self.log("You can now use the 'Copy Parameters to Clipboard' button to copy the parameters for documentation.")
            else:
                self.log("Calculation completed but no results were returned.")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())