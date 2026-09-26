"""Dock widget for creating latitude/longitude AMA reference cells."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis

from ...qt_compat import MLPM_All


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "ui",
    "utilities",
    "qpansopy_ama_grid_dockwidget.ui",
))


class QPANSOPYAMAGridDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Collect AMA grid inputs and create the result layer."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self.extentSourceComboBox.setItemData(0, "canvas")
        self.extentSourceComboBox.setItemData(1, "layer")
        self.amaSizeComboBox.setItemData(0, "AMA_1")
        self.amaSizeComboBox.setItemData(1, "AMA_05")
        self.outputCrsComboBox.setItemData(0, "project")
        self.outputCrsComboBox.setItemData(1, "wgs84")
        self.extentLayerComboBox.setFilters(MLPM_All)
        self.extentLayerComboBox.setAllowEmptyLayer(True)
        self.extentSourceComboBox.currentIndexChanged.connect(self._update_source_controls)
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self._browse)
        self.outputFolderLineEdit.setText(self.get_desktop_path())
        self._update_source_controls(0)
        self.log("AMA grid ready. Select the canvas or a layer extent.")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    @staticmethod
    def get_desktop_path():
        from ...utils import get_desktop_path
        return get_desktop_path()

    def _update_source_controls(self, index):
        use_layer = index == 1
        self.extentLayerLabel.setEnabled(use_layer)
        self.extentLayerComboBox.setEnabled(use_layer)

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select KML output folder", self.outputFolderLineEdit.text())
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        self.logTextEdit.append(str(message))
        self.logTextEdit.ensureCursorVisible()

    def _source_extent(self):
        if self.extentSourceComboBox.currentIndex() == 1:
            layer = self.extentLayerComboBox.currentLayer()
            if layer is None:
                raise ValueError("Select a layer for the extent source")
            return layer.extent(), layer.crs(), layer.name()
        canvas = self.iface.mapCanvas()
        return canvas.extent(), canvas.mapSettings().destinationCrs(), "map canvas"

    def calculate(self):
        try:
            extent, source_crs, source_name = self._source_extent()
            grid_type = self.amaSizeComboBox.currentData() or (
                "AMA_1" if self.amaSizeComboBox.currentIndex() == 0 else "AMA_05"
            )
            params = {
                "grid_type": grid_type,
                "output_crs": self.outputCrsComboBox.currentData(),
                "export_kml": self.exportKmlCheckBox.isChecked(),
                "output_dir": self.outputFolderLineEdit.text().strip(),
            }
            from ...modules.utilities.ama_grid import run_ama_grid
            run_ama_grid(self.iface, extent, source_crs, params)
            self.log("Created {0} AMA grid from {1}.".format(
                self.amaSizeComboBox.currentText(), source_name))
        except Exception as exc:
            self.log("Error: {0}".format(exc))
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                "QPANSOPY", str(exc), level=Qgis.Warning)
