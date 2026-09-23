"""Dock for VOR/NDB overhead facility fix tolerance."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QDoubleValidator
from qgis.core import Qgis

from ...qt_compat import (
    MLPM_LineLayer, MLPM_PointLayer, Qgis_GeomType_Line, Qgis_GeomType_Point,
    preseed_active_layer,
)


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv',
    'qpansopy_overhead_tolerance_dockwidget.ui'))


class QPANSOPYOverheadToleranceDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Collect elevations and selected geometries for overhead construction."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        self.navaidLayerComboBox.setFilters(MLPM_PointLayer)
        self.trackLayerComboBox.setFilters(MLPM_LineLayer)
        preseed_active_layer(iface, self.navaidLayerComboBox, Qgis_GeomType_Point)
        preseed_active_layer(iface, self.trackLayerComboBox, Qgis_GeomType_Line)
        for field in (self.aircraftAltitudeLineEdit, self.stationElevationLineEdit):
            field.setValidator(QDoubleValidator(field))
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self._browse)
        self.exportKmlCheckBox.toggled.connect(self._update_export_controls)
        self._update_export_controls(False)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def _update_export_controls(self, enabled):
        self.outputFolderLineEdit.setEnabled(enabled)
        self.browseButton.setEnabled(enabled)

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select KML output folder', self.outputFolderLineEdit.text())
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        self.logTextEdit.append(str(message))
        self.logTextEdit.ensureCursorVisible()

    @staticmethod
    def _feet(field, unit):
        value = field.text().strip()
        if not value:
            raise ValueError('Enter both aircraft altitude and station elevation')
        number = float(value)
        return number / 0.3048 if unit.currentText() == 'm' else number

    def calculate(self):
        try:
            navaid_layer = self.navaidLayerComboBox.currentLayer()
            track_layer = self.trackLayerComboBox.currentLayer()
            if navaid_layer is None or track_layer is None:
                raise ValueError('Select a navaid point layer and a track line layer')
            params = {
                'navaid_type': self.navaidTypeComboBox.currentText(),
                'aircraft_altitude_ft': self._feet(
                    self.aircraftAltitudeLineEdit, self.aircraftUnitComboBox),
                'station_elevation_ft': self._feet(
                    self.stationElevationLineEdit, self.stationUnitComboBox),
                'reverse_direction': self.reverseDirectionCheckBox.isChecked(),
                'include_cone': self.includeConeCheckBox.isChecked(),
                'include_points': self.includePointsCheckBox.isChecked(),
                'export_kml': self.exportKmlCheckBox.isChecked(),
                'output_dir': self.outputFolderLineEdit.text().strip(),
            }
            from ...modules.conv.overhead_tolerance import run_overhead_tolerance
            run_overhead_tolerance(self.iface, navaid_layer, track_layer, params)
            self.log('{0} overhead tolerance created.'.format(params['navaid_type']))
        except (ValueError, RuntimeError) as exc:
            self.log('Error: {0}'.format(exc))
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(exc), level=Qgis.Warning)
        except Exception as exc:
            self.log('Error: {0}'.format(exc))
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(exc), level=Qgis.Critical)
