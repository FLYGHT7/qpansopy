# -*- coding: utf-8 -*-
"""
/***************************************************************************
Parameters Inspector Dialog
                            A QGIS plugin
Renders a feature's 'parameters' JSON attribute as a readable HTML table,
with a button to copy it to the clipboard as a Word-pasteable table.
                        -------------------
   begin                : 2026-07-28
   copyright            : (C) 2026 by QPANSOPY Team
***************************************************************************/

/***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
***************************************************************************/
"""
import json

from qgis.core import QgsAction, QgsProject
from qgis.PyQt.QtCore import QMimeData
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout,
)

from .dockwidgets.base_dockwidget import load_base_qss
from .utils import format_parameters_table


def _generic_python_action_type():
    """
    QgsAction.GenericPython (Qt5/PyQt5) vs QgsAction.ActionType.GenericPython
    (Qt6/PyQt6, QGIS 4 scoped enum). Resolved lazily -- not at import time --
    so importing this module never depends on QgsAction's enum shape (e.g.
    under the test suite's QGIS stubs, which don't define either).
    """
    try:
        return QgsAction.ActionType.GenericPython
    except AttributeError:
        return QgsAction.GenericPython  # type: ignore[attr-defined]


# Reached from a QGIS layer action, which is triggered per-click rather than
# tracked by any caller -- keep non-modal dialogs alive here, otherwise PyQt
# garbage-collects the QDialog the moment show_parameters_inspector() returns.
_open_dialogs = []


class ParametersInspectorDialog(QDialog):
    """Read-only popup rendering a feature's stored parameters as an HTML table."""

    def __init__(self, title, html_table, text_table, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(480, 420)
        self.setStyleSheet(load_base_qss())
        self._html_table = html_table
        self._text_table = text_table
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        browser = QTextBrowser(self)
        # The dialog's dark QSS (load_base_qss()) styles bare QTextEdit as a
        # dark log panel (near-black background, light-gray text) -- correct
        # for the log widgets it was written for, but it also matches
        # QTextBrowser (a QTextEdit subclass), muddying the table's own
        # white/light-gray cell backgrounds and leaving text low-contrast.
        # Override locally so the rendered table stays crisp and readable.
        browser.setStyleSheet(
            "QTextBrowser { background-color: #ffffff; color: #202020; border: 1px solid #444; }"
        )
        browser.setHtml(self._html_table)
        layout.addWidget(browser)

        button_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to Word")
        copy_btn.clicked.connect(self.copy_to_word)
        button_row.addWidget(copy_btn)
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def copy_to_word(self):
        mime = QMimeData()
        mime.setHtml(self._html_table)
        mime.setText(self._text_table)
        QApplication.clipboard().setMimeData(mime)


def resolve_inspector_title(parameters_dict, fallback):
    """
    Pick a readable dialog title: the stored 'calculation_type' if present,
    else *fallback* (e.g. the layer name).
    """
    calculation_type = parameters_dict.get('calculation_type') if isinstance(parameters_dict, dict) else None
    subject = calculation_type or fallback
    return f"{subject} — Feature Parameters"


def show_parameters_inspector(layer_id, feature_id):
    """
    Entry point for the QGIS layer action registered by
    register_parameters_action(). Resolves the feature's stored 'parameters'
    JSON and shows it in a ParametersInspectorDialog.
    """
    layer = QgsProject.instance().mapLayer(layer_id)
    if layer is None:
        QMessageBox.warning(None, "Parameters Inspector", "Could not find the source layer.")
        return

    feature = layer.getFeature(feature_id)
    if not feature.isValid():
        QMessageBox.warning(None, "Parameters Inspector", "Could not find the selected feature.")
        return

    raw = feature.attribute('parameters')
    if not raw:
        QMessageBox.information(None, "Parameters Inspector", "This feature has no stored parameters.")
        return

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        QMessageBox.warning(None, "Parameters Inspector", "The stored parameters could not be parsed as JSON.")
        return

    title = resolve_inspector_title(parsed, layer.name())
    html_table = format_parameters_table(title, parsed, as_html=True)
    text_table = format_parameters_table(title, parsed, as_html=False)

    dialog = ParametersInspectorDialog(title, html_table, text_table)
    _open_dialogs.append(dialog)
    dialog.finished.connect(lambda _result: _open_dialogs.remove(dialog) if dialog in _open_dialogs else None)
    dialog.show()


def register_parameters_action(layer):
    """
    Register a 'Show Parameters' QGIS layer action on *layer*, so any
    feature with a 'parameters' attribute can be inspected as a rendered
    HTML table from the Attribute Table / Identify results (issue #193).
    """
    action_code = (
        "from Q_Pansopy.parameters_inspector_dialog import show_parameters_inspector\n"
        "show_parameters_inspector('[% @layer_id %]', [% $id %])"
    )
    action = QgsAction(_generic_python_action_type(), "Show Parameters (QPANSOPY)", action_code)
    layer.actions().addAction(action)
