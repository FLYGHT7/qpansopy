"""Inputs and progress for simplified straight VOR/VOR en-route areas."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis

from ...qt_compat import (
    MLPM_PointLayer, Qgis_GeomType_Point, Qt_WaitCursor, preseed_active_layer,
)


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv',
    'qpansopy_enroute_vor_vor_dockwidget.ui'))


class QPANSOPYEnrouteVorVorDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Collect two selected stations and create the primary and buffer layers."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self._calculating = False
        self.vorLayerComboBox.setFilters(MLPM_PointLayer)
        self.vorLayerComboBox.setAllowEmptyLayer(True)
        preseed_active_layer(iface, self.vorLayerComboBox, Qgis_GeomType_Point)
        self.calculateButton.clicked.connect(self.calculate)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log(self, message):
        self.logTextEdit.append(str(message))
        self.logTextEdit.ensureCursorVisible()

    def calculate(self):
        if self._calculating:
            return
        self._calculating = True
        self.calculateButton.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(Qt_WaitCursor)
        try:
            from ...modules.conv.enroute_vor_vor import run_enroute_vor_vor

            self.log('Calculating simplified VOR/VOR en-route areas...')
            QtWidgets.QApplication.processEvents()
            run_enroute_vor_vor(self.iface, self.vorLayerComboBox.currentLayer(), {
                'include_construction_lines': self.constructionCheckBox.isChecked(),
                'log': self.log,
            })
        except Exception as error:
            self.log(f'Error: {error}')
            if not isinstance(error, ValueError):
                self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage('QPANSOPY', str(error), level=Qgis.Warning)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.calculateButton.setEnabled(True)
            self._calculating = False
