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
from PyQt5.QtCore import pyqtSignal, QFileInfo, Qt
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes, QgsMapLayerProxyModel
from qgis.utils import iface

# Modificación clave: usar __file__ para obtener la ruta actual del script
# Esto asegura que funcione independientemente del nombre del directorio
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
        
        # Configurar el dock widget para que sea redimensionable
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable |
                         QtWidgets.QDockWidget.DockWidgetClosable)
        
        # Establecer tamaños mínimo y máximo
        self.setMinimumHeight(300)
        self.setMaximumHeight(600)
        
        # Connect signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self.browse_output_folder)
        
        # Set default output folder
        self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Filter layers in comboboxes - MODIFICADO PARA USAR QgsMapLayerProxyModel
        self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.runwayLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        
        # Log message
        self.log("QPANSOPY VSS plugin loaded. Select layers and parameters, then click Calculate.")
    
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
        if not runway_layer.crs().isGeographic():
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
        calc_type = "Straight In NPA" if self.straightInNPARadioButton.isChecked() else "ILS/LOC/APV"
        point_layer = self.pointLayerComboBox.currentLayer()
        runway_layer = self.runwayLayerComboBox.currentLayer()
        rwy_width = self.rwyWidthSpinBox.value()
        thr_elev = self.thrElevSpinBox.value()
        strip_width = self.stripWidthSpinBox.value()
        och = self.ochSpinBox.value()
        rdh = self.rdhSpinBox.value()
        vpa = self.vpaSpinBox.value()
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()
        
        # Prepare parameters
        params = {
            'rwy_width': rwy_width,
            'thr_elev': thr_elev,
            'strip_width': strip_width,
            'OCH': och,
            'RDH': rdh,
            'VPA': vpa,
            'export_kml': export_kml,
            'output_dir': output_dir
        }
        
        try:
            # Run calculation based on type
            if "Straight In NPA" in calc_type:
                self.log("Running VSS Straight In NPA calculation...")
                # Import here to avoid circular imports
                from .modules.vss_straight import calculate_vss_straight
                result = calculate_vss_straight(self.iface, point_layer, runway_layer, params)
            else:  # ILS/LOC/APV
                self.log("Running VSS ILS/LOC/APV calculation...")
                # Import here to avoid circular imports
                from .modules.vss_loc import calculate_vss_loc
                result = calculate_vss_loc(self.iface, point_layer, runway_layer, params)
            
            # Log results
            if result:
                if export_kml:
                    self.log(f"VSS KML exported to: {result.get('vss_path', 'N/A')}")
                    self.log(f"OCS KML exported to: {result.get('ocs_path', 'N/A')}")
                self.log(f"VSS {calc_type} calculation completed successfully!")
            else:
                self.log("Calculation completed but no results were returned.")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
