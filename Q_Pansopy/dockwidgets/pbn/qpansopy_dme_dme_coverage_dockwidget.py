"""Dock widget for theoretical DME/DME coverage assessment."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis

from ...qt_compat import MLPM_PointLayer, Qgis_GeomType_Point, preseed_active_layer


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), "..", "..", "ui", "pbn",
    "qpansopy_dme_dme_coverage_dockwidget.ui"))


class QPANSOPYDMEDMECoverageDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Collect DME pair and DOC inputs for the PBN coverage calculation."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self.dmeLayerComboBox.setFilters(MLPM_PointLayer)
        self.dmeLayerComboBox.setAllowEmptyLayer(True)
        preseed_active_layer(iface, self.dmeLayerComboBox,
                             Qgis_GeomType_Point)
        self.dmeLayerComboBox.layerChanged.connect(self._populate_doc_fields)
        self.calculateButton.clicked.connect(self.calculate)
        self._populate_doc_fields(self.dmeLayerComboBox.currentLayer())
        self.log("Select exactly two DME stations. Missing DOC values use 200 NM.")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log(self, message):
        self.logTextEdit.append(str(message))
        self.logTextEdit.ensureCursorVisible()

    def _populate_doc_fields(self, layer):
        self.docFieldComboBox.clear()
        self.docFieldComboBox.addItem("Not provided — use 200 NM", "")
        if layer is not None:
            for field in layer.fields():
                is_boolean = field.typeName().lower() in ("bool", "boolean")
                if field.isNumeric() and not is_boolean:
                    self.docFieldComboBox.addItem(field.name(), field.name())
        self.docFieldComboBox.setCurrentIndex(0)

    def calculate(self):
        try:
            layer = self.dmeLayerComboBox.currentLayer()
            params = {
                "doc_field": self.docFieldComboBox.currentData() or "",
                "include_construction_layers": self.constructionCheckBox.isChecked(),
                "log": self.log,
            }
            from ...modules.pbn.dme_dme_coverage import run_dme_dme_coverage
            if run_dme_dme_coverage(self.iface, layer, params):
                self.log("Coverage calculation completed successfully.")
        except Exception as error:
            self.log("Error: {0}".format(error))
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                "QPANSOPY", str(error), level=Qgis.Warning)
