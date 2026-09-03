# -*- coding: utf-8 -*-
"""Dockwidget for the Visual Manoeuvring (Circling) Protection Area tool."""
import os
import traceback
from typing import Dict, Mapping, Tuple

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
_CATEGORY_WIDGET_NAMES = {
    'A': ('catACheckBox', 'iasASpinBox', 'protHeightASpinBox'),
    'B': ('catBCheckBox', 'iasBSpinBox', 'protHeightBSpinBox'),
    'C': ('catCCheckBox', 'iasCSpinBox', 'protHeightCSpinBox'),
    'D': ('catDCheckBox', 'iasDSpinBox', 'protHeightDSpinBox'),
    'E': ('catECheckBox', 'iasESpinBox', 'protHeightESpinBox'),
}


class QPANSOPYCirclingDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """Wire the circling UI to :func:`Q_Pansopy.modules.utilities.circling.run_circling`."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        self._configure_category_grid()
        self.last_summary = None
        self.last_params = None
        self._isa_updating = False
        self.isa_calculation_metadata = {'method': 'manual'}

        self.thresholdLayerComboBox.setFilters(MLPM_PointLayer)
        preseed_active_layer(iface, self.thresholdLayerComboBox, Qgis_GeomType_Point)

        self.outputFolderLineEdit.setText(self.get_desktop_path())

        self.calculateButton.clicked.connect(self.calculate)
        self.isaCalculateButton.clicked.connect(self._calculate_isa)
        self.isaSpinBox.valueChanged.connect(self._handle_isa_manual_change)
        self.elevSpinBox.valueChanged.connect(self._handle_isa_context_change)
        self.elevUnitCombo.currentTextChanged.connect(
            self._handle_isa_context_change)
        self.browseButton.clicked.connect(self.browse_output_folder)
        self.showTableButton.clicked.connect(self.show_parameters_table)
        self.copyCompleteTableButton.clicked.connect(self.copy_complete_table)

    def _configure_category_grid(self) -> None:
        """Balance numeric columns with Qt5/Qt6-safe integer arguments."""
        self.categoryGridLayout.setColumnStretch(1, 1)
        self.categoryGridLayout.setColumnStretch(2, 1)

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

    def _handle_isa_manual_change(self, _value: float) -> None:
        """Discard calculator provenance after a manual ISA value change."""
        if not self._isa_updating:
            self.isa_calculation_metadata = {'method': 'manual'}

    def _handle_isa_context_change(self, _value: object) -> None:
        """Invalidate ISA provenance when its source elevation changes."""
        self._handle_isa_manual_change(0.0)

    def _apply_calculated_isa(
            self, isa_variation: float,
            metadata: Mapping[str, object]) -> bool:
        """Apply a calculator result without allowing silent spinbox clamps."""
        minimum = self.isaSpinBox.minimum()
        maximum = self.isaSpinBox.maximum()
        if not minimum <= isa_variation <= maximum:
            self.log(
                'Error: Calculated ΔT ISA {0:.4f} °C is outside the allowed '
                'range ({1:.4f} to {2:.4f} °C)'.format(
                    isa_variation, minimum, maximum))
            return False

        self._isa_updating = True
        try:
            self.isaSpinBox.setValue(isa_variation)
        finally:
            self._isa_updating = False
        self.isa_calculation_metadata = dict(metadata)
        self.log(
            'Calculated ΔT ISA: {0:.4f} °C'.format(isa_variation))
        return True

    def _calculate_isa(self) -> None:
        """Calculate ISA deviation using this tool's aerodrome elevation."""
        from ...isa_calculator_dialog import ISACalculatorDialog

        dialog = ISACalculatorDialog(
            self,
            fixed_elevation=self.elevSpinBox.value(),
            fixed_elevation_unit=self.elevUnitCombo.currentText(),
        )
        if not dialog.exec():
            return

        isa_variation = dialog.get_isa_variation()
        if isa_variation is None:
            return
        self._apply_calculated_isa(
            isa_variation, dialog.get_calculation_metadata())

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def _category_inputs(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Return aligned speed and protected-height maps for enabled CATs."""
        ias_by_cat = {}
        prot_height_ft_by_cat = {}
        for cat in _CATEGORIES:
            checkbox_name, ias_name, height_name = _CATEGORY_WIDGET_NAMES[cat]
            if not getattr(self, checkbox_name).isChecked():
                continue
            ias_by_cat[cat] = getattr(self, ias_name).value()
            prot_height_ft_by_cat[cat] = getattr(self, height_name).value()
        return ias_by_cat, prot_height_ft_by_cat

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

        ias_by_cat, prot_height_ft_by_cat = self._category_inputs()
        if not ias_by_cat:
            self.log("Error: Enable at least one aircraft category")
            return

        params = {
            'elev': self.elevSpinBox.value(),
            'elev_unit': self.elevUnitCombo.currentText(),
            'bank_deg': self.bankSpinBox.value(),
            'delta_isa': self.isaSpinBox.value(),
            'isa_calculation_metadata': dict(
                self.isa_calculation_metadata),
            'ias_by_cat': ias_by_cat,
            'prot_height_ft_by_cat': prot_height_ft_by_cat,
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
                "CAT {0} | Height {1:.0f} ft AGL | K {2:.4f} | "
                "TAS+25 {3:.2f} kt | R {4:.3f} deg/s | r {5:.3f} NM | "
                "Circling R {6:.3f} NM".format(
                    cat, res['protected_height_ft'], res['k_factor'],
                    res['tas_plus_wind_kt'], res['rate_turn_used'],
                    res['nominal_radius_nm'], res['circling_radius_nm']))

    def show_parameters_table(self):
        summary = self.last_summary
        if not summary:
            self.log("Error: No calculation available to show")
            return

        sections = []
        for cat in _CATEGORIES:
            res = summary.get(cat)
            if not res:
                continue
            sections.append(("CAT {0}".format(cat), {
                'IAS_kt': "{0:.0f}".format(res['ias_kt']),
                'Protected_height_ft_AGL': "{0:.0f}".format(
                    res['protected_height_ft']),
                'Altitude_h1_ft': "{0:.1f}".format(res['h1_ft']),
                'K_factor': "{0:.4f}".format(res['k_factor']),
                'TAS_plus_25kt': "{0:.4f}".format(res['tas_plus_wind_kt']),
                'Rate_of_turn_calc_deg_s': "{0:.4f}".format(res['rate_turn_calc']),
                'Rate_of_turn_used_deg_s': "{0:.4f}".format(res['rate_turn_used']),
                'Nominal_radius_r_NM': "{0:.4f}".format(res['nominal_radius_nm']),
                'Straight_segment_S_NM': "{0:.1f}".format(res['straight_segment_nm']),
                'Circling_radius_NM': "{0:.4f}".format(res['circling_radius_nm']),
            }))

        from ...parameters_inspector_dialog import show_web_popup
        show_web_popup("Circling Protection Area - Parameters", sections)
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
