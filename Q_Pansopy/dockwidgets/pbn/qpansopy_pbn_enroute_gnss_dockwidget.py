"""Inputs and progress for PBN GNSS en-route areas."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis

from ...qt_compat import (
    MLPM_LineLayer, Qgis_GeomType_Line, Qt_WaitCursor, preseed_active_layer,
)


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'pbn',
    'qpansopy_pbn_enroute_gnss_dockwidget.ui'))


class QPANSOPYPBNEnrouteGNSSDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Collect one straight route and its GNSS navigation specification."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self._calculating = False
        self.routingLayerComboBox.setFilters(MLPM_LineLayer)
        self.routingLayerComboBox.setAllowEmptyLayer(True)
        preseed_active_layer(iface, self.routingLayerComboBox, Qgis_GeomType_Line)
        from ...modules.pbn.pbn_enroute_gnss import SPECS
        for spec in SPECS:
            self.specComboBox.addItem(spec.label, spec.identifier)
        self.specComboBox.currentIndexChanged.connect(self._update_description)
        self._update_description()
        self.calculateButton.clicked.connect(self.calculate)

    def _update_description(self, *_args):
        from ...modules.pbn.pbn_enroute_gnss import resolve_spec
        width = resolve_spec(self.specComboBox.currentData()).half_width_nm
        self.outputDescriptionLabel.setText(
            f'One layer: Primary Area (±{width / 2:g} NM) and two Secondary Areas '
            f'to ±{width:g} NM. GNSS only; flat ends; constant width.')

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
            from ...modules.pbn.pbn_enroute_gnss import run_pbn_enroute_gnss

            self.log('Calculating PBN GNSS en-route areas...')
            QtWidgets.QApplication.processEvents()
            run_pbn_enroute_gnss(self.iface, self.routingLayerComboBox.currentLayer(), {
                'nav_spec': self.specComboBox.currentData(),
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
