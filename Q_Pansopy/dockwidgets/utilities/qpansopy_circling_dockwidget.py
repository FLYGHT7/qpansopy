# -*- coding: utf-8 -*-
"""Dockwidget for the Visual Manoeuvring (Circling) Protection Area tool."""
import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QMimeData, pyqtSignal
from qgis.core import Qgis

from ...qt_compat import (
    MLPM_PointLayer, Qgis_GeomType_Point, preseed_active_layer,
)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities',
    'qpansopy_circling_dockwidget.ui'))

_CATEGORIES = ('A', 'B', 'C', 'D', 'E')


class QPANSOPYCirclingDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Wire the circling UI to :func:`Q_Pansopy.modules.utilities.circling.run_circling`."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self.last_summary = None
        self.last_params = None

        self.thresholdLayerComboBox.setFilters(MLPM_PointLayer)
        preseed_active_layer(iface, self.thresholdLayerComboBox, Qgis_GeomType_Point)

        self.outputFolderLineEdit.setText(self.get_desktop_path())

        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self.browse_output_folder)
        self.showTableButton.clicked.connect(self.show_parameters_table)
        self.copyCompleteTableButton.clicked.connect(self.copy_complete_table)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def get_desktop_path(self):
        from ...utils import get_desktop_path as _gdp
        return _gdp()

    def browse_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.outputFolderLineEdit.text())
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def _ias_by_cat(self):
        checkboxes = {
            'A': self.catACheckBox, 'B': self.catBCheckBox, 'C': self.catCCheckBox,
            'D': self.catDCheckBox, 'E': self.catECheckBox,
        }
        spinboxes = {
            'A': self.iasASpinBox, 'B': self.iasBSpinBox, 'C': self.iasCSpinBox,
            'D': self.iasDSpinBox, 'E': self.iasESpinBox,
        }
        return {
            cat: spinboxes[cat].value()
            for cat in _CATEGORIES
            if checkboxes[cat].isChecked()
        }

    def calculate(self):
        layer = self.thresholdLayerComboBox.currentLayer()
        if not layer:
            self.log("Error: Please select a threshold point layer")
            return
        if layer.selectedFeatureCount() < 2:
            msg = "Select at least 2 threshold features in the map before calculating"
            self.log("Error: {0}".format(msg))
            self.iface.messageBar().pushMessage("QPANSOPY", msg, level=Qgis.Warning)
            return

        ias_by_cat = self._ias_by_cat()
        if not ias_by_cat:
            self.log("Error: Enable at least one aircraft category")
            return

        params = {
            'elev': self.elevSpinBox.value(),
            'elev_unit': self.elevUnitCombo.currentText(),
            'bank_deg': self.bankSpinBox.value(),
            'delta_isa': self.isaSpinBox.value(),
            'prot_height_ft': self.protHeightSpinBox.value(),
            'ias_by_cat': ias_by_cat,
            'export_kml': self.exportKmlCheckBox.isChecked(),
            'output_dir': self.outputFolderLineEdit.text(),
        }

        try:
            self.log("Calculating Circling Protection Area...")
            from ...modules.utilities.circling import run_circling
            result = run_circling(self.iface, layer, params)
        except Exception as e:
            self.log("Error during calculation: {0}".format(e))
            self.log(traceback.format_exc())
            return

        if not result:
            self.log("Circling Protection Area calculation failed")
            return

        self.last_summary = result.get('summary') or {}
        self.last_params = {
            'bank_deg': params['bank_deg'],
            'delta_isa': params['delta_isa'],
            'prot_height_ft': params['prot_height_ft'],
        }
        self._log_summary(self.last_summary)
        kml_path = result.get('kml_path')
        if kml_path:
            self.log("KML exported to: {0}".format(kml_path))
        self.log("Circling Protection Area calculation completed successfully")

    def _log_summary(self, summary):
        for cat in _CATEGORIES:
            res = summary.get(cat)
            if not res:
                continue
            self.log(
                "CAT {0} | K {1:.4f} | TAS+25 {2:.2f} kt | R {3:.3f} deg/s | "
                "r {4:.3f} NM | Circling R {5:.3f} NM".format(
                    cat, res['k_factor'], res['tas_plus_wind_kt'],
                    res['rate_turn_used'], res['nominal_radius_nm'],
                    res['circling_radius_nm']))

    def show_parameters_table(self):
        summary = self.last_summary
        if not summary or not self.last_params:
            self.log("Error: No calculation available to show")
            return

        sections = []
        for cat in _CATEGORIES:
            res = summary.get(cat)
            if not res:
                continue
            sections.append(("CAT {0}".format(cat), {
                'IAS_kt': "{0:.0f}".format(res['ias_kt']),
                'Altitude_h1_ft': "{0:.1f}".format(res['h1_ft']),
                'K_factor': "{0:.4f}".format(res['k_factor']),
                'TAS_plus_25kt': "{0:.4f}".format(res['tas_plus_wind_kt']),
                'Rate_of_turn_calc_deg_s': "{0:.4f}".format(res['rate_turn_calc']),
                'Rate_of_turn_used_deg_s': "{0:.4f}".format(res['rate_turn_used']),
                'Nominal_radius_r_NM': "{0:.4f}".format(res['nominal_radius_nm']),
                'Straight_segment_S_NM': "{0:.1f}".format(res['straight_segment_nm']),
                'Circling_radius_NM': "{0:.4f}".format(res['circling_radius_nm']),
            }))

        from ...modules.utilities.circling import format_circling_complete_table
        from ...parameters_inspector_dialog import ClipboardContent, show_web_popup

        table_html, table_text = format_circling_complete_table(
            summary, self.last_params)
        show_web_popup(
            "Circling Protection Area - Parameters",
            sections,
            clipboard_content=ClipboardContent(table_html, table_text),
        )
        self.log("Circling parameters shown in Parameters Inspector.")

    def copy_complete_table(self):
        """Copy the last Circling calculation as one CAT A-E Word table."""
        if not self.last_summary or not self.last_params:
            self.log("Error: No calculation available to copy")
            return

        from ...modules.utilities.circling import format_circling_complete_table

        try:
            table_html, table_text = format_circling_complete_table(
                self.last_summary, self.last_params)
            mime = QMimeData()
            mime.setHtml(table_html)
            mime.setText(table_text)
            QtWidgets.QApplication.clipboard().setMimeData(mime)
        except Exception as exc:
            self.log(
                "Error copying complete Circling table: {0}".format(exc))
            return

        self.log("Complete Circling table copied to clipboard for Word.")
        self.iface.messageBar().pushMessage(
            "QPANSOPY", "Complete Circling table copied to clipboard",
            level=Qgis.Success,
        )
