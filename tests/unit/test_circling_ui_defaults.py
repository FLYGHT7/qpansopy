"""Regression tests for Circling aircraft-category defaults."""
import pathlib
import xml.etree.ElementTree as ET


_UI_PATH = (
    pathlib.Path(__file__).parents[2]
    / 'Q_Pansopy/ui/utilities/qpansopy_circling_dockwidget.ui'
)
_EXPECTED_DEFAULTS = {
    'catACheckBox': True,
    'catBCheckBox': True,
    'catCCheckBox': True,
    'catDCheckBox': True,
    'catECheckBox': False,
}


def _category_defaults():
    root = ET.parse(_UI_PATH).getroot()
    defaults = {}
    for widget in root.findall(".//widget[@class='QCheckBox']"):
        name = widget.get('name')
        if name not in _EXPECTED_DEFAULTS:
            continue
        checked = widget.find("./property[@name='checked']/bool")
        defaults[name] = checked is not None and checked.text == 'true'
    return defaults


def test_circling_category_checkboxes_have_expected_defaults():
    """CAT E is opt-in while CAT A-D remain selected initially."""
    assert _category_defaults() == _EXPECTED_DEFAULTS
