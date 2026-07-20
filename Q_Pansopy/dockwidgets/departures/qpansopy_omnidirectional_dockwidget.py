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
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis, QgsGeometry, QgsPoint, QgsPolygon, QgsLineString,
    QgsProject, QgsCoordinateTransform,
)
from qgis.gui import QgsRubberBand
from ...qt_compat import (
    DOCK_FEATURES_DEFAULT, Qt_ALLOWED_DOCK_AREAS, MLPM_LineLayer,
    preseed_active_layer, Qgis_GeomType_Line, Qgis_GeomType_Polygon,
)

# DER marker arrow dimensions in screen pixels (converted to map units via
# mapUnitsPerPixel so the marker stays a constant, visible size at any zoom level)
_DER_MARKER_SHAFT_LENGTH_PX = 40
_DER_MARKER_SHAFT_HALF_WIDTH_PX = 4
_DER_MARKER_HEAD_LENGTH_PX = 16
_DER_MARKER_HEAD_HALF_WIDTH_PX = 12


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
        self.setFeatures(DOCK_FEATURES_DEFAULT)
        try:
            self.setAllowedAreas(Qt_ALLOWED_DOCK_AREAS)
        except Exception:
            pass
        # Don't set minimum height - let dock adjust naturally to prevent QGIS window resize

        # Connect signals
        self.calculateButton.clicked.connect(self.calculate)
        self.directionButton.clicked.connect(self.toggle_direction)

        # Filter layers in comboboxes - Runway layer should be a line
        self.runwayLayerComboBox.setFilters(MLPM_LineLayer)
        preseed_active_layer(iface, self.runwayLayerComboBox, Qgis_GeomType_Line)

        # Direction state: False = Start to End, True = End to Start
        self.is_reversed = False

        # Set default values
        self.derElevationSpinBox.setValue(0.0)
        self.derElevationUnitCombo.setCurrentText('m')
        self.pdgSpinBox.setValue(3.3)
        self.tnaSpinBox.setValue(2000)
        self.msaSpinBox.setValue(6300)
        self.cwyDistanceSpinBox.setValue(0)
        self.cwyDistanceUnitCombo.setCurrentText('m')

        # Live DER marker preview (off by default)
        self._der_marker_band = QgsRubberBand(iface.mapCanvas(), Qgis_GeomType_Polygon)
        self._der_marker_band.setColor(QColor(0, 170, 0, 120))
        self._der_marker_band.setStrokeColor(QColor(0, 120, 0, 220))
        self._der_marker_band.setWidth(1)
        self._connected_runway_layer = None

        self.runwayLayerComboBox.layerChanged.connect(self._on_runway_layer_changed)
        self.cwyDistanceSpinBox.valueChanged.connect(self._update_der_marker)
        self.showDerMarkerCheckBox.toggled.connect(self._update_der_marker)
        iface.mapCanvas().scaleChanged.connect(self._update_der_marker)
        self._on_runway_layer_changed()

        # Ensure checkboxes exist
        if not hasattr(self, "exportKmlCheckBox") or self.exportKmlCheckBox is None:
            self.exportKmlCheckBox = QtWidgets.QCheckBox("Export to KML", self)
            self.exportKmlCheckBox.setChecked(False)
            # Add the fallback checkbox to the layout so it is visible
            if hasattr(self, "verticalLayout") and self.verticalLayout is not None:
                self.verticalLayout.addWidget(self.exportKmlCheckBox)

        # Log message
        self.log("QPANSOPY Omnidirectional SID plugin loaded.")
        self.log("Select runway layer and set parameters, then click Calculate.")

    def closeEvent(self, event):
        self._clear_der_marker()
        try:
            self.iface.mapCanvas().scaleChanged.disconnect(self._update_der_marker)
        except (TypeError, RuntimeError):
            pass
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
        self._update_der_marker()

    def _on_runway_layer_changed(self, *args):
        if self._connected_runway_layer is not None:
            try:
                self._connected_runway_layer.selectionChanged.disconnect(self._update_der_marker)
            except (TypeError, RuntimeError):
                pass
            self._connected_runway_layer = None

        layer = self.runwayLayerComboBox.currentLayer()
        if layer:
            layer.selectionChanged.connect(self._update_der_marker)
            self._connected_runway_layer = layer

        self._update_der_marker()

    def _clear_der_marker(self):
        if self._der_marker_band:
            self._der_marker_band.reset(Qgis_GeomType_Polygon)

    def _update_der_marker(self, *args):
        self._clear_der_marker()

        if not self.showDerMarkerCheckBox.isChecked():
            return

        runway_layer = self.runwayLayerComboBox.currentLayer()
        if not runway_layer or runway_layer.selectedFeatureCount() != 1:
            return

        try:
            map_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            project = QgsProject.instance()

            feature = runway_layer.selectedFeatures()[0]
            geom = feature.geometry()
            geom.transform(QgsCoordinateTransform(runway_layer.crs(), map_crs, project))
            runway_geometry = geom.asPolyline()
            if len(runway_geometry) < 2:
                return

            if self.is_reversed:
                threshold_point = QgsPoint(runway_geometry[1])
                der_point = QgsPoint(runway_geometry[0])
            else:
                threshold_point = QgsPoint(runway_geometry[0])
                der_point = QgsPoint(runway_geometry[1])

            runway_azimuth = threshold_point.azimuth(der_point)
            der_cwy_point = der_point.project(self.cwyDistanceSpinBox.value(), runway_azimuth)

            # Size the marker in screen pixels so it stays visible at any zoom level
            mupp = self.iface.mapCanvas().mapUnitsPerPixel()
            shaft_length = _DER_MARKER_SHAFT_LENGTH_PX * mupp
            shaft_half_width = _DER_MARKER_SHAFT_HALF_WIDTH_PX * mupp
            head_length = _DER_MARKER_HEAD_LENGTH_PX * mupp
            head_half_width = _DER_MARKER_HEAD_HALF_WIDTH_PX * mupp

            # Arrow tip sits at the DER+CWY point, shaft trails back toward the threshold
            back_azimuth = runway_azimuth + 180
            back_point = der_cwy_point.project(shaft_length + head_length, back_azimuth)
            head_base_point = der_cwy_point.project(head_length, back_azimuth)

            back_left = back_point.project(shaft_half_width, runway_azimuth - 90)
            back_right = back_point.project(shaft_half_width, runway_azimuth + 90)
            shaft_head_left = head_base_point.project(shaft_half_width, runway_azimuth - 90)
            shaft_head_right = head_base_point.project(shaft_half_width, runway_azimuth + 90)
            head_left = head_base_point.project(head_half_width, runway_azimuth - 90)
            head_right = head_base_point.project(head_half_width, runway_azimuth + 90)

            arrow = QgsGeometry(QgsPolygon(QgsLineString([
                back_left, shaft_head_left, head_left, der_cwy_point,
                head_right, shaft_head_right, back_right,
            ])))
            self._der_marker_band.setToGeometry(arrow, None)
        except Exception:
            pass

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
            'der_elevation_unit': self.derElevationUnitCombo.currentText(),
            'pdg': self.pdgSpinBox.value(),
            'TNA_ft': self.tnaSpinBox.value(),
            'msa_ft': self.msaSpinBox.value(),
            'cwy_distance_m': self.cwyDistanceSpinBox.value(),
            'cwy_distance_unit': self.cwyDistanceUnitCombo.currentText(),
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
