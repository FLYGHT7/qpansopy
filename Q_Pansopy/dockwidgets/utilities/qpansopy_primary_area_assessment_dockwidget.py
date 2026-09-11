"""Dockwidget for the generic primary-area obstacle assessment."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import Qgis

from ...qt_compat import (
    MLPM_PointLayer,
    MLPM_PolygonLayer,
    MLPM_RasterLayer,
    Qgis_GeomType_Polygon,
    Qt_WaitCursor,
    preseed_active_layer,
)


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "ui",
    "utilities",
    "qpansopy_primary_area_assessment_dockwidget.ui",
))


class QPANSOPYPrimaryAreaAssessmentDockWidget(
        QtWidgets.QDockWidget, FORM_CLASS):
    """Collect assessment inputs and report progress to the user."""

    closingPlugin = pyqtSignal()

    _FIELD_CANDIDATES = {
        "idFieldComboBox": ("id", "identifier", "idnumber", "name"),
        "typeFieldComboBox": (
            "obstacle_type", "obstype", "type", "feattype"
        ),
        "elevationFieldComboBox": (
            "elev", "elevation", "height", "altitude"
        ),
        "toleranceFieldComboBox": (
            "tolerances", "tolerance", "vertical_tolerance", "vconf"
        ),
    }

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        self._assessing = False

        self.areaLayerComboBox.setFilters(MLPM_PolygonLayer)
        self.terrainLayerComboBox.setFilters(MLPM_RasterLayer)
        self.obstacleLayerComboBox.setFilters(MLPM_PointLayer)
        self.terrainLayerComboBox.setAllowEmptyLayer(True)
        self.obstacleLayerComboBox.setAllowEmptyLayer(True)
        self.terrainLayerComboBox.setLayer(None)
        self.obstacleLayerComboBox.setLayer(None)
        preseed_active_layer(
            iface, self.areaLayerComboBox, Qgis_GeomType_Polygon
        )

        self.obstacleLayerComboBox.layerChanged.connect(
            self._populate_field_choices
        )
        self.overrideToleranceCheckBox.toggled.connect(
            self._update_tolerance_controls
        )
        self.calculateButton.clicked.connect(self.calculate)
        self._populate_field_choices(None)
        self._update_tolerance_controls(False)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    @staticmethod
    def _select_candidate(combo, candidates):
        names = {
            str(combo.itemData(index)).lower(): index
            for index in range(combo.count())
            if combo.itemData(index)
        }
        for candidate in candidates:
            if candidate in names:
                combo.setCurrentIndex(names[candidate])
                return

    def _populate_field_choices(self, layer):
        combos = [
            self.idFieldComboBox,
            self.typeFieldComboBox,
            self.elevationFieldComboBox,
            self.toleranceFieldComboBox,
        ]
        names = [] if layer is None else layer.fields().names()
        for combo in combos:
            combo.clear()
            if combo is self.toleranceFieldComboBox:
                combo.addItem("Not mapped", "")
            for name in names:
                combo.addItem(name, name)
        self.fieldMappingGroup.setEnabled(layer is not None)
        for object_name, candidates in self._FIELD_CANDIDATES.items():
            self._select_candidate(getattr(self, object_name), candidates)
        self._update_tolerance_controls(
            self.overrideToleranceCheckBox.isChecked()
        )

    def _update_tolerance_controls(self, checked):
        self.overrideToleranceDoubleSpinBox.setEnabled(checked)
        has_obstacles = self.obstacleLayerComboBox.currentLayer() is not None
        self.toleranceFieldComboBox.setEnabled(has_obstacles and not checked)

    def _field_mapping(self):
        from ...modules.utilities.primary_area_assessment import FieldMapping

        return FieldMapping(
            identifier=self.idFieldComboBox.currentData() or "",
            obstacle_type=self.typeFieldComboBox.currentData() or "",
            elevation=self.elevationFieldComboBox.currentData() or "",
            tolerance=self.toleranceFieldComboBox.currentData() or None,
        )

    def _confirm_missing(self, warnings):
        message = "\n".join(f"• {warning}" for warning in warnings)
        message += "\n\nRun the assessment anyway?"
        try:
            yes = QtWidgets.QMessageBox.StandardButton.Yes
            no = QtWidgets.QMessageBox.StandardButton.No
        except AttributeError:
            yes = QtWidgets.QMessageBox.Yes
            no = QtWidgets.QMessageBox.No
        reply = QtWidgets.QMessageBox.question(
            self,
            "Incomplete obstacle data",
            message,
            yes | no,
            no,
        )
        return reply == yes

    def _validate_inputs(self):
        area_layer = self.areaLayerComboBox.currentLayer()
        if area_layer is None:
            raise ValueError("Please select an assessment-area layer")
        if (self.useSelectedAreaCheckBox.isChecked()
                and area_layer.selectedFeatureCount() == 0):
            raise ValueError(
                "Use selected areas is checked, but no area is selected"
            )

        obstacle_layer = self.obstacleLayerComboBox.currentLayer()
        mapping = None
        if obstacle_layer is not None:
            mapping = self._field_mapping()
            required = [
                mapping.identifier,
                mapping.obstacle_type,
                mapping.elevation,
            ]
            if not self.overrideToleranceCheckBox.isChecked():
                required.append(mapping.tolerance)
            if any(not field for field in required):
                raise ValueError(
                    "Map ID, obstacle type, elevation, and tolerance fields"
                )
        return area_layer, obstacle_layer, mapping

    def calculate(self):
        """Execute the assessment while keeping the dock state consistent."""
        if self._assessing:
            return

        cursor_set = False
        try:
            area_layer, obstacle_layer, mapping = self._validate_inputs()
            self._assessing = True
            self.calculateButton.setEnabled(False)
            QtWidgets.QApplication.setOverrideCursor(Qt_WaitCursor)
            cursor_set = True
            QtWidgets.QApplication.processEvents()
            self.log("Starting primary-area obstacle assessment...")

            from ...modules.utilities.primary_area_assessment import (
                AssessmentCancelled,
                run_primary_area_assessment,
            )

            override = (
                self.overrideToleranceDoubleSpinBox.value()
                if self.overrideToleranceCheckBox.isChecked()
                else None
            )
            try:
                result = run_primary_area_assessment(
                    self.iface,
                    area_layer,
                    terrain_layer=self.terrainLayerComboBox.currentLayer(),
                    obstacle_layer=obstacle_layer,
                    field_mapping=mapping,
                    moc_m=self.mocDoubleSpinBox.value(),
                    terrain_tolerance_m=(
                        self.terrainToleranceDoubleSpinBox.value()
                    ),
                    override_tolerance_m=override,
                    terrain_band=self.terrainBandSpinBox.value(),
                    use_selected_area=(
                        self.useSelectedAreaCheckBox.isChecked()
                    ),
                    confirm_missing=self._confirm_missing,
                )
            except AssessmentCancelled:
                self.log("Assessment cancelled.")
                return

            message = (
                f"Assessment complete: {result.assessed_count} point(s), "
                f"{result.control_count} controlling obstacle(s)."
            )
            self.log(message)
            for warning in result.warnings:
                self.log(f"Warning: {warning}")
            self.iface.messageBar().pushMessage(
                "QPANSOPY", message, level=Qgis.Success
            )
        except Exception as error:
            message = f"Primary-area assessment failed: {error}"
            self.log(message)
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                "QPANSOPY", message, level=Qgis.Critical
            )
        finally:
            if cursor_set:
                QtWidgets.QApplication.restoreOverrideCursor()
            if self._assessing:
                self.calculateButton.setEnabled(True)
                self._assessing = False
