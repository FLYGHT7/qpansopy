"""Dockwidget for radial/bearing intersection fix tolerance."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis

from ...qt_compat import MLPM_PointLayer, Qgis_GeomType_Point, preseed_active_layer


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv',
    'qpansopy_radial_bearing_intersection_dockwidget.ui'))


class QPANSOPYRadialBearingIntersectionDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Choose two facilities and their nominal intersection point."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        for combo in (self.trackingLayerComboBox, self.crossingLayerComboBox,
                      self.fixLayerComboBox):
            combo.setFilters(MLPM_PointLayer)
            preseed_active_layer(iface, combo, Qgis_GeomType_Point)
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

    def _log_result(self, result):
        self.log('Early: {0:.3f} NM; late: {1:.3f} NM'.format(
            result.early_nm, result.late_nm))

    def calculate(self):
        params = {
            'tracking_type': self.trackingTypeComboBox.currentText(),
            'crossing_type': self.crossingTypeComboBox.currentText(),
            'flight_direction': self.flightDirectionComboBox.currentText().lower(),
            'export_kml': self.exportKmlCheckBox.isChecked(),
            'output_dir': self.outputFolderLineEdit.text().strip(),
            'on_result': self._log_result,
        }
        try:
            from ...modules.conv.radial_bearing_intersection import (
                run_radial_bearing_intersection,
            )
            result = run_radial_bearing_intersection(
                self.iface, self.trackingLayerComboBox.currentLayer(),
                self.crossingLayerComboBox.currentLayer(),
                self.fixLayerComboBox.currentLayer(), params)
            if result:
                self.log('Radial/bearing fix tolerance created.')
        except (ValueError, RuntimeError) as error:
            self.log('Error: {0}'.format(error))
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(error), level=Qgis.Warning)
        except Exception as error:
            self.log('Error: {0}'.format(error))
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                'QPANSOPY', str(error), level=Qgis.Critical)
