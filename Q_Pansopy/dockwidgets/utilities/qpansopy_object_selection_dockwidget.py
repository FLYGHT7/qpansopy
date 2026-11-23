from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import Qgis, QgsMapLayerProxyModel
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_object_selection_dockwidget.ui'))


class QPANSOPYObjectSelectionDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super(QPANSOPYObjectSelectionDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        self._extracting = False

        # Setup layer combos
        self.pointLayerComboBox.setFilters(QgsMapLayerProxyModel.Filter.PointLayer)
        self.surfaceLayerComboBox.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)

        # Set default output folder
        self.outputFolderLineEdit.setText(self.get_desktop_path())

        # Connect signals
        self.setup_connections()

    def setup_connections(self):
        """Setup signal/slot connections"""
        # Conectar el botón Extract directamente a la función extract_objects
        self.calculateButton.clicked.connect(self.extract_objects)
        self.browseButton.clicked.connect(self.browse_output_folder)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def get_desktop_path(self):
        from ...utils import get_desktop_path as _gdp
        return _gdp()

    def browse_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.outputFolderLineEdit.text()
        )
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def extract_objects(self):
        """Extract intersecting objects"""
        if self._extracting:
            return

        cursor_set = False
        try:
            point_layer = self.pointLayerComboBox.currentLayer()
            surface_layer = self.surfaceLayerComboBox.currentLayer()

            if not point_layer or not surface_layer:
                self.log("Error: Please select both input layers")
                return

            # Get options
            export_kml = self.exportKmlCheckBox.isChecked()
            output_dir = self.outputFolderLineEdit.text() if export_kml else None
            use_selection_only = self.useSelectionOnlyCheckBox.isChecked()

            # 'Use selection only' limits the assessment surfaces. Every
            # obstacle point inside those selected surfaces is considered.
            if (use_selection_only
                    and surface_layer.selectedFeatureCount() == 0):
                message = (
                    "Error: 'Use selection only' is checked but no features "
                    "are selected in the surface layer '" +
                    surface_layer.name() + "'."
                )
                self.log(message)
                self.iface.messageBar().pushMessage(
                    "QPANSOPY", message, level=Qgis.MessageLevel.Warning
                )
                return

            self._extracting = True
            self.calculateButton.setEnabled(False)

            QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            cursor_set = True

            self.log("Starting object extraction...")
            self.iface.messageBar().pushMessage(
                "QPANSOPY",
                "Extracting objects...",
                level=Qgis.MessageLevel.Info,
                duration=0,
            )
            QtWidgets.QApplication.processEvents()

            from ...modules.utilities.selection_of_objects import extract_objects

            result = extract_objects(
                self.iface,
                point_layer,
                surface_layer,
                export_kml=export_kml,
                output_dir=output_dir,
                use_selection_only=use_selection_only
            )

            if result:
                msg = f"Extracted {result['count']} objects"
                if export_kml and 'kml_path' in result:
                    msg += f"\nKML exported to: {result['kml_path']}"
                self.log(msg)
                self.iface.messageBar().pushMessage("QPANSOPY", msg, level=Qgis.MessageLevel.Success)

        except Exception as e:
            self.log(f"Error during extraction: {str(e)}")
            self.iface.messageBar().pushMessage("Error", str(e), level=Qgis.MessageLevel.Critical)
            import traceback
            self.log(traceback.format_exc())
        finally:
            if cursor_set:
                QtWidgets.QApplication.restoreOverrideCursor()
            if self._extracting:
                self.calculateButton.setEnabled(True)
                self._extracting = False
