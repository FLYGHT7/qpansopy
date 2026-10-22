"""Dockwidget for the generic slope primary-area assessment."""

import os
import traceback

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QSignalBlocker, pyqtSignal
from qgis.core import Qgis

from ...qt_compat import (
    MLPM_LineLayer,
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
    "qpansopy_slope_primary_area_assessment_dockwidget.ui",
))


class QPANSOPYSlopePrimaryAreaAssessmentDockWidget(
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
        self._processing_message = None
        self._align_form_fields()
        self._slope_angle_deg = self.slopeAngleDoubleSpinBox.value()
        self._slope_angle_limit_deg = self.slopeAngleDoubleSpinBox.maximum()
        self.slopeAngleDoubleSpinBox.valueChanged.connect(self._update_slope_value)
        self.slopeUnitComboBox.currentTextChanged.connect(self._update_slope_unit)

        self.areaLayerComboBox.setFilters(MLPM_PolygonLayer)
        self.referenceLayerComboBox.setFilters(MLPM_LineLayer)
        self.referenceLayerComboBox.setAllowEmptyLayer(True)
        self.referenceLayerComboBox.setLayer(None)
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

    def _update_slope_value(self, value: float):
        from ...modules.utilities.slope_primary_area_assessment import slope_to_degrees

        self._slope_angle_deg = slope_to_degrees(value, self.slopeUnitComboBox.currentText())

    def _update_slope_unit(self, unit: str):
        from ...modules.utilities.slope_primary_area_assessment import slope_from_degrees

        # Keep the unrounded angle: the displayed conversion has only four decimals.
        limit = slope_from_degrees(self._slope_angle_limit_deg, unit)
        with QSignalBlocker(self.slopeAngleDoubleSpinBox):
            self.slopeAngleDoubleSpinBox.setRange(-limit, limit)
            self.slopeAngleDoubleSpinBox.setValue(slope_from_degrees(self._slope_angle_deg, unit))

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def _show_processing_message(self):
        message_bar = self.iface.messageBar()
        message_bar.pushMessage(
            "QPANSOPY",
            "Slope primary-area assessment is in progress. "
            "This may take several minutes.",
            level=Qgis.Info,
            duration=30,
        )
        self._processing_message = message_bar.currentItem()

    def _clear_processing_message(self):
        item = self._processing_message
        self._processing_message = None
        if item is None:
            return

        message_bar = self.iface.messageBar()
        try:
            if item in message_bar.items():
                message_bar.popWidget(item)
        except (AttributeError, RuntimeError):
            # Cleanup must not mask the original assessment result or error.
            pass

    def _align_form_fields(self):
        """Give every form the same label-column width."""
        labels = [
            self.areaLabel,
            self.areaBufferLabel,
            self.terrainLabel,
            self.obstacleLabel,
            self.idFieldLabel,
            self.typeFieldLabel,
            self.elevationFieldLabel,
            self.toleranceFieldLabel,
            self.referenceLabel,
            self.surfaceElevationLabel,
            self.slopeAngleLabel,
            self.terrainToleranceLabel,
            self.overrideToleranceCheckBox,
        ]
        label_width = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setMinimumWidth(label_width)

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
        self.fieldMappingGroup.setVisible(layer is not None)
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
        wait_cursor_active = QtWidgets.QApplication.overrideCursor() is not None
        if wait_cursor_active:
            QtWidgets.QApplication.restoreOverrideCursor()
        try:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Incomplete assessment data",
                message,
                yes | no,
                no,
            )
        finally:
            if wait_cursor_active:
                QtWidgets.QApplication.setOverrideCursor(Qt_WaitCursor)
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

        reference_layer = self.referenceLayerComboBox.currentLayer()
        if reference_layer is None:
            raise ValueError("Please select a reference-line layer")
        if reference_layer.selectedFeatureCount() != 1:
            raise ValueError("Select exactly one reference line")

        terrain_layer = self.terrainLayerComboBox.currentLayer()
        obstacle_layer = self.obstacleLayerComboBox.currentLayer()
        if terrain_layer is None and obstacle_layer is None:
            raise ValueError("Please select a terrain or survey layer")
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

    def _report_crs_warning(self, error):
        message = f"Assessment not run: {error}"
        self.log(message)
        self.iface.messageBar().pushMessage(
            "QPANSOPY", message, level=Qgis.Warning
        )

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
            self.log("Starting slope primary-area assessment...")
            self._show_processing_message()
            QtWidgets.QApplication.processEvents()

            from ...modules.utilities.primary_area_assessment import (
                AssessmentCancelled,
                CrsValidationError,
                area_buffer_to_metres,
            )
            from ...modules.utilities.slope_primary_area_assessment import (
                run_slope_primary_area_assessment,
            )

            override = (
                self.overrideToleranceDoubleSpinBox.value()
                if self.overrideToleranceCheckBox.isChecked()
                else None
            )
            try:
                result = run_slope_primary_area_assessment(
                    self.iface,
                    area_layer,
                    self.referenceLayerComboBox.currentLayer(),
                    terrain_layer=self.terrainLayerComboBox.currentLayer(),
                    obstacle_layer=obstacle_layer,
                    field_mapping=mapping,
                    surface_elevation_m=self.surfaceElevationDoubleSpinBox.value(),
                    slope_angle_deg=self._slope_angle_deg,
                    terrain_tolerance_m=(
                        self.terrainToleranceDoubleSpinBox.value()
                    ),
                    override_tolerance_m=override,
                    terrain_band=1,
                    use_selected_area=(
                        self.useSelectedAreaCheckBox.isChecked()
                    ),
                    confirm_missing=self._confirm_missing,
                    area_buffer_m=area_buffer_to_metres(
                        self.areaBufferDoubleSpinBox.value(),
                        self.areaBufferUnitComboBox.currentText(),
                    ),
                )
            except AssessmentCancelled:
                self.log("Assessment cancelled.")
                return
            except CrsValidationError as error:
                self._report_crs_warning(error)
                return

            message = (
                f"Assessment complete: {result.assessed_count} point(s), "
                f"{result.penetration_count} penetrating point(s)."
            )
            self.log(message)
            for warning in result.warnings:
                self.log(f"Warning: {warning}")
            self.iface.messageBar().pushMessage(
                "QPANSOPY", message, level=Qgis.Success
            )
        except Exception as error:
            message = f"Slope primary-area assessment failed: {error}"
            self.log(message)
            self.log(traceback.format_exc())
            self.iface.messageBar().pushMessage(
                "QPANSOPY", message, level=Qgis.Critical
            )
        finally:
            self._clear_processing_message()
            if cursor_set:
                QtWidgets.QApplication.restoreOverrideCursor()
            if self._assessing:
                self.calculateButton.setEnabled(True)
                self._assessing = False
