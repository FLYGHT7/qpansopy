import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsMapLayerProxyModel
from ...qt_compat import MLPM_PointLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'pbn', 'qpansopy_pbn_target_dockwidget.ui'))


class QPANSOPYPBNTargetDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)

        self.pointLayerComboBox.setFilters(MLPM_PointLayer)
        self.calculateButton.clicked.connect(self.calculate)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log(self, msg):
        if hasattr(self, 'logTextEdit') and self.logTextEdit:
            self.logTextEdit.append(msg)
            self.logTextEdit.ensureCursorVisible()

    def calculate(self):
        layer = self.pointLayerComboBox.currentLayer()
        if not layer:
            self.log('Error: Please select a point layer')
            return

        try:
            from ...modules.pbn.pbn_target import run_pbn_target
            result = run_pbn_target(self.iface, layer)
            if result:
                self.log('PBN Target rings created successfully (15 NM / 30 NM ARP)')
            else:
                self.log('PBN Target creation failed — check the QGIS message bar for details')
        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
