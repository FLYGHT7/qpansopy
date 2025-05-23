from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt
import os

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("QPANSOPY Settings")
        self.setMinimumWidth(350)
        layout = QtWidgets.QVBoxLayout(self)

        # About section with logo
        about_layout = QtWidgets.QHBoxLayout()
        logo_path = os.path.join(os.path.dirname(__file__), "icons", "flyght7_logo.png")
        if os.path.exists(logo_path):
            logo = QtGui.QPixmap(logo_path)
            logo_label = QtWidgets.QLabel()
            logo_label.setPixmap(logo.scaledToHeight(48))
            about_layout.addWidget(logo_label)
        label = QtWidgets.QLabel("<b>QPANSOPY by FLYGHT7</b>")
        label.setAlignment(Qt.AlignVCenter)
        about_layout.addWidget(label)
        layout.addLayout(about_layout)

        layout.addWidget(QtWidgets.QLabel(" "))

        # KML export option
        self.kml_checkbox = QtWidgets.QCheckBox("Enable KML export by default")
        if settings:
            self.kml_checkbox.setChecked(settings.value("qpansopy/enable_kml", False, type=bool))
        layout.addWidget(self.kml_checkbox)

        # Log box option
        self.log_checkbox = QtWidgets.QCheckBox("Show log box by default")
        if settings:
            self.log_checkbox.setChecked(settings.value("qpansopy/show_log", True, type=bool))
        layout.addWidget(self.log_checkbox)

        # Buttons
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_values(self):
        return {
            "enable_kml": self.kml_checkbox.isChecked(),
            "show_log": self.log_checkbox.isChecked()
        }