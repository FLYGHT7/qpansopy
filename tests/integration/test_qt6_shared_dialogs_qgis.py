"""Real Qt6 acceptance, cancellation, inspector actions and clipboard behavior."""
import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import QgsAction, QgsApplication, QgsVectorLayer  # noqa: E402
from qgis.PyQt.QtCore import QSettings, QTimer  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication, QDialog, QDialogButtonBox  # noqa: E402


@pytest.fixture(scope='module', autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


@pytest.mark.parametrize('accept', [True, False])
def test_settings_accept_and_cancel_with_scoped_buttons(tmp_path, accept):
    from Q_Pansopy.settings_dialog import SettingsDialog

    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    settings.setValue('qpansopy/enable_kml', False)
    settings.setValue('qpansopy/show_log', True)
    dialog = SettingsDialog(settings=settings)
    assert dialog.get_values() == {'enable_kml': False, 'show_log': True}
    dialog.kml_checkbox.setChecked(True)
    box = dialog.findChild(QDialogButtonBox)
    button = QDialogButtonBox.StandardButton.Ok if accept else QDialogButtonBox.StandardButton.Cancel
    QTimer.singleShot(0, box.button(button).click)
    expected = QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
    assert dialog.exec() == expected
    assert settings.value('qpansopy/enable_kml', type=bool) is False
    dialog.deleteLater()


@pytest.mark.parametrize('accept', [True, False])
def test_isa_calculate_or_cancel_preserves_result_contract(accept):
    from Q_Pansopy.isa_calculator_dialog import ISACalculatorDialog

    dialog = ISACalculatorDialog(fixed_elevation=1000, fixed_elevation_unit='ft')
    assert dialog.elevation_edit.isReadOnly()
    assert not dialog.elevation_unit_combo.isEnabled()
    dialog.temperature_edit.setText('25')
    QTimer.singleShot(0, (dialog.calculate_btn if accept else dialog.cancel_btn).click)
    result = dialog.exec()
    if accept:
        assert result == QDialog.DialogCode.Accepted
        assert dialog.get_isa_variation() == pytest.approx(11.98)
        assert dialog.get_calculation_metadata()['elevation_original'] == 1000
    else:
        assert result == QDialog.DialogCode.Rejected
        assert dialog.get_isa_variation() is None
    dialog.deleteLater()


def test_inspector_registers_real_scoped_python_action():
    from Q_Pansopy.parameters_inspector_dialog import register_parameters_action

    layer = QgsVectorLayer('Point?crs=EPSG:32616', 'parameters', 'memory')
    register_parameters_action(layer)
    actions = layer.actions().actions()
    assert len(actions) == 1
    assert actions[0].type() == QgsAction.ActionType.GenericPython
    assert actions[0].actionScopes() == {'Feature', 'Canvas'}


def test_textbrowser_fallback_and_webchannel_bridge_copy_the_same_content(monkeypatch):
    from Q_Pansopy import parameters_inspector_dialog as inspector

    content = inspector.TableContent('<table><tr><td>IAS</td><td>205</td></tr></table>', 'IAS\t205')
    monkeypatch.setattr(inspector, '_WEBENGINE_AVAILABLE', False)
    inspector.show_web_popup('Test', [('Parameters', {'IAS': 205})], table_content=content)
    dialogs = [w for w in QApplication.topLevelWidgets()
               if isinstance(w, inspector._FallbackParametersDialog)]
    assert len(dialogs) == 1
    dialog = dialogs[0]
    try:
        assert '205' in dialog._browser.toPlainText()
        dialog._copy_to_word()
        assert QApplication.clipboard().mimeData().text() == content.text
        assert QApplication.clipboard().mimeData().hasHtml()
        dialog._toggle_theme()
        assert '205' in dialog._browser.toPlainText()
        bridge = inspector.ClipboardBridge([], table_content=content)
        QApplication.clipboard().clear()
        bridge.copyToClipboard()
        assert QApplication.clipboard().mimeData().text() == content.text
    finally:
        dialog.close()
        dialog.deleteLater()


def test_legacy_extraction_dialog_is_a_valid_qt6_dialog_and_returns_cancel():
    from Q_Pansopy.object_extraction_dialog import ObjectExtractionDialog

    dialog = ObjectExtractionDialog()
    assert dialog.windowTitle() == ''
    assert dialog.exec() is False
    dialog.deleteLater()
