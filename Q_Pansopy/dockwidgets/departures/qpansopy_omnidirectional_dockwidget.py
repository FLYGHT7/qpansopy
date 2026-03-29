# -*- coding: utf-8 -*-
"""
/***************************************************************************
QPANSOPYOmnidirectionalDockWidget
                            A QGIS plugin
Procedure Analysis - Omnidirectional SID Departure Surface Tool
                        -------------------
   begin                : 2025
   copyright            : (C) 2025 by FLYGHT7
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
from PyQt5.QtCore import pyqtSignal, Qt
from qgis.core import QgsProject, QgsMapLayerProxyModel
from qgis.utils import iface
from qgis.core import Qgis


# Use __file__ to get the current script path
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'departures', 'qpansopy_omnidirectional_dockwidget.ui'))


class QPANSOPYOmnidirectionalDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        """Constructor."""
        super(QPANSOPYOmnidirectionalDockWidget, self).__init__(iface.mainWindow())
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.iface = iface
        
        # Configure the dock widget to be resizable
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable |
                         QtWidgets.QDockWidget.DockWidgetClosable)
        try:
            self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        except Exception:
            pass
        # Don't set minimum height - let dock adjust naturally to prevent QGIS window resize
        
        # Connect signals
        self.calculateButton.clicked.connect(self.calculate)
        self.directionButton.clicked.connect(self.toggle_direction)
        
        # Filter layers in comboboxes - Runway layer should be a line
        self.runwayLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        
        # Direction state: False = Start to End, True = End to Start
        self.is_reversed = False
        
        # Set default values
        self.derElevationSpinBox.setValue(0.0)
        self.pdgSpinBox.setValue(3.3)
        self.tnaSpinBox.setValue(2000)
        self.msaSpinBox.setValue(6300)
        self.cwyDistanceSpinBox.setValue(0)
        
        # Ensure checkboxes exist
        if not hasattr(self, "exportKmlCheckBox") or self.exportKmlCheckBox is None:
            self.exportKmlCheckBox = QtWidgets.QCheckBox("Export to KML", self)
            self.exportKmlCheckBox.setChecked(False)
        
        # Log message
        self.log("QPANSOPY Omnidirectional SID plugin loaded.")
        self.log("Select runway layer and set parameters, then click Calculate.")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def toggle_direction(self):
        """Toggle the runway direction between Start→End and End→Start"""
        self.is_reversed = not self.is_reversed
        if self.is_reversed:
            self.directionButton.setText("End → Start")
            self.log("Direction changed: End to Start (reversed)")
        else:
            self.directionButton.setText("Start → End")
            self.log("Direction changed: Start to End (normal)")

    def log(self, message):
        """Add a message to the log"""
        if hasattr(self, 'logTextEdit') and self.logTextEdit is not None:
            self.logTextEdit.append(message)
            self.logTextEdit.ensureCursorVisible()

    def validate_inputs(self):
        """Validate user inputs"""
        # Check if runway layer is selected
        if not self.runwayLayerComboBox.currentLayer():
            self.log("Error: Please select a runway layer")
            return False
        
        runway_layer = self.runwayLayerComboBox.currentLayer()
        
        # Log CRS information
        self.log(f"Runway layer CRS: {runway_layer.crs().authid()} ({runway_layer.crs().description()})")
        
        # Check if layer is in projected CRS
        if runway_layer.crs().isGeographic():
            self.log("ERROR: Runway layer is in a geographic coordinate system")
            self.log("ERROR: Calculation will not be performed. Please reproject to a projected CRS")
            return False
        
        self.log(f"SUCCESS: Runway layer uses projected CRS: {runway_layer.crs().authid()}")
        
        # Validate PDG
        pdg = self.pdgSpinBox.value()
        if pdg <= 0 or pdg > 15:
            self.log("Error: PDG must be between 0 and 15%")
            return False
        
        # Validate TNA < MSA
        tna = self.tnaSpinBox.value()
        msa = self.msaSpinBox.value()
        if tna >= msa:
            self.log("Error: TNA must be less than MSA")
            return False
        
        return True

    def calculate(self):
        """Run the calculation"""
        self.log("Starting Omnidirectional SID calculation...")
        
        # Validate inputs
        if not self.validate_inputs():
            return
        
        # Get parameters
        runway_layer = self.runwayLayerComboBox.currentLayer()
        
        # Prepare parameters
        params = {
            'der_elevation_m': self.derElevationSpinBox.value(),
            'pdg': self.pdgSpinBox.value(),
            'TNA_ft': self.tnaSpinBox.value(),
            'msa_ft': self.msaSpinBox.value(),
            'cwy_distance_m': self.cwyDistanceSpinBox.value(),
            'allow_turns_before_der': 'YES' if self.turnsBeforeDerCheckBox.isChecked() else 'NO',
            'include_construction_points': 'YES' if self.constructionPointsCheckBox.isChecked() else 'NO',
            'reverse_direction': 'YES' if self.is_reversed else 'NO'
        }
        
        try:
            # Import and run the omnidirectional SID module
            from ...modules.departures.omnidirectional_sid import run_omnidirectional_sid
            
            result = run_omnidirectional_sid(
                self.iface, 
                runway_layer, 
                params, 
                log_callback=self.log
            )
            
            # Log results
            if result:
                self.log("=" * 50)
                self.log("RESULTS SUMMARY:")
                self.log(f"Layer created: {result.get('layer_name', 'N/A')}")
                self.log(f"Areas: {', '.join(result.get('areas', []))}")
                distances = result.get('distances', [])
                if distances:
                    total_dist = sum(distances)
                    self.log(f"Total distance: {total_dist:.2f}m ({total_dist/1852:.2f}NM)")
                self.log("=" * 50)
                self.iface.messageBar().pushMessage(
                    "QPANSOPY", 
                    "Omnidirectional SID calculation completed successfully", 
                    level=Qgis.Success
                )
            else:
                self.log("Calculation completed but no results were returned.")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                "QPANSOPY", 
                f"Error: {str(e)}", 
                level=Qgis.Critical
            )
