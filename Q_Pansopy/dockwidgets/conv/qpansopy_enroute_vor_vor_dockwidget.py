"""Inputs and progress for straight VOR/VOR en-route areas."""

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
    """Collect two stations and dispatch the selected ENR method."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self._calculating = False
        self.methodComboBox.addItem('Simplified', 'simplified')
        self.methodComboBox.addItem('Refined', 'refined')
        self.methodComboBox.currentIndexChanged.connect(self._update_method_description)
        self._update_method_description()
        self.vorLayerComboBox.setFilters(MLPM_PointLayer)
        self.vorLayerComboBox.setAllowEmptyLayer(True)
        preseed_active_layer(iface, self.vorLayerComboBox, Qgis_GeomType_Point)
        self.calculateButton.clicked.connect(self.calculate)

    def _update_method_description(self, *_args):
        refined = self.methodComboBox.currentData() == 'refined'
        outer = 'Secondary' if refined else 'Buffer'
        limit = '75' if refined else '99.6'
        self.outputDescriptionLabel.setText(
            f'Primary area and {outer} area will be added as separate layers. '
            f'Case 1 ≤ {limit} NM; Case 2 > {limit} NM — selected automatically '
            'from the station distance.')

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
        self.methodComboBox.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(Qt_WaitCursor)
        try:
            method = self.methodComboBox.currentData()
            if method == 'refined':
                from ...modules.conv.enroute_vor_vor_refined import run_enroute_vor_vor_refined as runner
            else:
                from ...modules.conv.enroute_vor_vor import run_enroute_vor_vor as runner
            layer = self.vorLayerComboBox.currentLayer()
            params = {
                'include_construction_lines': self.constructionCheckBox.isChecked(),
                'log': self.log,
            }
            self.log(f'Calculating {method} VOR/VOR en-route areas...')
            QtWidgets.QApplication.processEvents()
            runner(self.iface, layer, params)
        except Exception as error:
            self.log(f'Error: {error}')
            if not isinstance(error, ValueError):
                self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage('QPANSOPY', str(error), level=Qgis.Warning)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.calculateButton.setEnabled(True)
            self.methodComboBox.setEnabled(True)
            self._calculating = False
