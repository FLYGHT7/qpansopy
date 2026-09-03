# -*- coding: utf-8 -*-
"""
Tests for issue #193 (and its follow-up): registering the 'view parameters
as HTML Table' QGIS layer action with the correct name/scopes, resolving a
readable popup title, building the multi-section HTML, and the clipboard
bridge used by the popup's 'Copy to Word' button.
"""
import importlib


def _mod():
    return importlib.import_module('Q_Pansopy.parameters_inspector_dialog')


# ---------------------------------------------------------------------------
# resolve_inspector_title
# ---------------------------------------------------------------------------

def test_title_uses_calculation_type_when_present():
    mod = _mod()
    title = mod.resolve_inspector_title({'calculation_type': 'Basic ILS'}, fallback='My Layer')
    assert title == 'Basic ILS — Feature Parameters'


def test_title_falls_back_to_layer_name_when_missing():
    mod = _mod()
    title = mod.resolve_inspector_title({}, fallback='My Layer')
    assert title == 'My Layer — Feature Parameters'


def test_title_falls_back_for_non_dict_input():
    mod = _mod()
    title = mod.resolve_inspector_title(None, fallback='My Layer')
    assert title == 'My Layer — Feature Parameters'


# ---------------------------------------------------------------------------
# register_parameters_action
# ---------------------------------------------------------------------------

class _FakeActions:
    def __init__(self):
        self.added = []

    def addAction(self, action):
        self.added.append(action)


class _FakeLayer:
    def __init__(self):
        self._actions = _FakeActions()

    def actions(self):
        return self._actions


class _FakeQgsAction:
    GenericPython = 'generic-python'

    def __init__(self, action_type, name, action_code):
        self.action_type = action_type
        self.name = name
        self.action_code = action_code
        self.action_scopes = None

    def setActionScopes(self, scopes):
        self.action_scopes = scopes


def test_register_parameters_action_uses_safe_substitution_tokens(monkeypatch):
    """
    Regression guard: the action code must resolve the feature via
    '[% @layer_id %]' / '[% $id %]' substitution (safe, quote-free) rather
    than interpolating the raw JSON string, which could contain characters
    that break the generated Python literal.
    """
    mod = _mod()
    monkeypatch.setattr(mod, 'QgsAction', _FakeQgsAction)

    layer = _FakeLayer()
    mod.register_parameters_action(layer)

    assert len(layer._actions.added) == 1
    action = layer._actions.added[0]
    code = action.action_code
    assert 'show_parameters_inspector' in code
    assert '@layer_id' in code
    assert '$id' in code
    # Never interpolate the raw parameters JSON directly into the action code.
    assert '"parameters"' not in code


def test_register_parameters_action_name_and_scopes(monkeypatch):
    """
    Regression guard for issue #193's follow-up: the action must be named
    exactly 'view parameters as HTML Table', and must explicitly set the
    Feature/Canvas action scopes -- without this the action is registered
    but invisible until a user manually enables those scopes.
    """
    mod = _mod()
    monkeypatch.setattr(mod, 'QgsAction', _FakeQgsAction)

    layer = _FakeLayer()
    mod.register_parameters_action(layer)

    action = layer._actions.added[0]
    assert action.name == 'view parameters as HTML Table'
    assert action.action_scopes == {'Feature', 'Canvas'}


# ---------------------------------------------------------------------------
# HTML builder (_build_page_html / _build_rows_html / _build_section_html)
# ---------------------------------------------------------------------------

def test_build_page_html_single_section_has_no_subheading():
    mod = _mod()
    page = mod._build_page_html("Wind Spiral — Feature Parameters", [("Wind Spiral", {'IAS': 205})])

    assert "Wind Spiral — Feature Parameters" in page
    assert 'class="section-title"' not in page
    assert "<td><b>IAS</b></td><td>205</td>" in page
    assert 'class="dark-theme"' in page  # dark mode by default


def test_build_page_html_multiple_sections_get_subheadings():
    mod = _mod()
    page = mod._build_page_html("Basic ILS — Feature Parameters", [
        ("Layer A", {'thr_elev': 100}),
        ("Layer B", {'thr_elev': 200}),
    ])

    assert page.count('class="section-title"') == 2
    assert "Layer A" in page
    assert "Layer B" in page


def test_build_page_html_escapes_values():
    mod = _mod()
    page = mod._build_page_html("Title", [("Section", {'note': '<script>alert(1)</script>'})])

    assert '<script>alert(1)</script>' not in page
    assert '&lt;script&gt;' in page


def test_build_page_html_uses_complete_table_content():
    mod = _mod()
    content = mod.TableContent(
        '<table id="complete"><tr><th>Parameters</th><th>CAT A</th></tr></table>',
        'Parameters\tCAT A',
    )

    page = mod._build_page_html(
        "Circling", [("CAT A", {'IAS': 100})], table_content=content)

    assert page.count('<table') == 1
    assert 'id="complete"' in page
    assert '<td><b>IAS</b></td>' not in page
    assert 'complete-table-card' in page


# ---------------------------------------------------------------------------
# ClipboardBridge
# ---------------------------------------------------------------------------

def test_clipboard_bridge_copies_word_table(monkeypatch):
    mod = _mod()

    captured = {}

    class _FakeMimeData:
        def setHtml(self, value):
            captured['html'] = value

        def setText(self, value):
            captured['text'] = value

    class _FakeClipboard:
        def setMimeData(self, mime):
            captured['mime'] = mime

    class _FakeQApplication:
        @staticmethod
        def clipboard():
            return _FakeClipboard()

    monkeypatch.setattr(mod, 'QMimeData', _FakeMimeData)
    monkeypatch.setattr(mod, 'QApplication', _FakeQApplication)

    bridge = mod.ClipboardBridge([("Wind Spiral", {'IAS': 205})])
    bridge.copyToClipboard()

    assert '205' in captured['html']
    assert '205' in captured['text']
    assert captured['mime'] is not None


def test_clipboard_bridge_uses_custom_single_table_content(monkeypatch):
    """A caller can override the generic one-table-per-section export."""
    mod = _mod()
    captured = {}

    class _FakeMimeData:
        def setHtml(self, value):
            captured['html'] = value

        def setText(self, value):
            captured['text'] = value

    class _FakeClipboard:
        def setMimeData(self, mime):
            captured['mime'] = mime

    class _FakeQApplication:
        @staticmethod
        def clipboard():
            return _FakeClipboard()

    monkeypatch.setattr(mod, 'QMimeData', _FakeMimeData)
    monkeypatch.setattr(mod, 'QApplication', _FakeQApplication)
    content = mod.TableContent(
        html='<table><tr><th>Parameters</th><th>CAT A</th></tr></table>',
        text='Parameters\tCAT A',
    )

    bridge = mod.ClipboardBridge(
        [('CAT A', {'IAS': 100}), ('CAT B', {'IAS': 135})],
        table_content=content,
    )
    bridge.copyToClipboard()

    assert captured['html'] == content.html
    assert captured['text'] == content.text
    assert captured['html'].count('<table') == 1


# ---------------------------------------------------------------------------
# QTextBrowser fallback (QtWebEngine unavailable -- issue #193 follow-up)
# ---------------------------------------------------------------------------

def test_build_fallback_page_html_single_section_has_no_subheading():
    mod = _mod()
    page = mod._build_fallback_page_html("Wind Spiral — Feature Parameters", [("Wind Spiral", {'IAS': 205})])

    # The title itself is shown via a native QLabel in the dialog header, not
    # embedded in the browser HTML -- only "Feature Parameters" + the table are.
    assert "Feature Parameters" in page
    assert "<h4" not in page
    assert "205" in page
    assert "#0f172a" in page  # dark background by default


def test_build_fallback_page_html_light_theme_uses_light_palette():
    mod = _mod()
    dark_page = mod._build_fallback_page_html("Title", [("Section", {'a': 1})], theme='dark')
    light_page = mod._build_fallback_page_html("Title", [("Section", {'a': 1})], theme='light')

    assert "#f4f6f9" in light_page  # light body background
    assert "#f4f6f9" not in dark_page
    assert "#0f172a" in dark_page  # dark body background
    assert dark_page != light_page


def test_fallback_dialog_toggle_theme_flips_state():
    """Regression guard: the fallback popup must offer a working light/dark
    toggle even without QtWebEngine/JS -- a plain button flips this state
    and re-renders the static HTML."""
    mod = _mod()
    dialog = mod._FallbackParametersDialog("Title", [("Section", {'a': 1})])

    assert dialog._theme == 'dark'
    dialog._toggle_theme()
    assert dialog._theme == 'light'
    dialog._toggle_theme()
    assert dialog._theme == 'dark'


def test_build_fallback_page_html_multiple_sections_get_subheadings():
    mod = _mod()
    page = mod._build_fallback_page_html("Basic ILS — Feature Parameters", [
        ("Layer A", {'thr_elev': 100}),
        ("Layer B", {'thr_elev': 200}),
    ])

    assert page.count("<h4") == 2
    assert "Layer A" in page
    assert "Layer B" in page


def test_build_fallback_page_html_escapes_values():
    mod = _mod()
    page = mod._build_fallback_page_html("Title", [("Section", {'note': '<script>alert(1)</script>'})])

    assert '<script>alert(1)</script>' not in page
    assert '&lt;script&gt;' in page


def test_build_fallback_page_html_uses_complete_table_content():
    mod = _mod()
    content = mod.TableContent(
        '<table id="complete"><tr><th>Parameters</th><th>CAT A</th></tr></table>',
        'Parameters\tCAT A',
    )

    page = mod._build_fallback_page_html(
        "Circling", [("CAT A", {'IAS': 100})], table_content=content)

    assert page.count('<table') == 1
    assert 'id="complete"' in page
    assert '<b>IAS</b>' not in page


def test_show_web_popup_falls_back_when_webengine_unavailable(monkeypatch):
    """
    Regression guard: on systems missing the optional QtWebEngine Qt
    bindings (e.g. python-pyqt6-webengine not installed), show_web_popup()
    must degrade to the QTextBrowser popup instead of raising.
    """
    mod = _mod()
    monkeypatch.setattr(mod, '_WEBENGINE_AVAILABLE', False)

    result = mod.show_web_popup("Wind Spiral — Feature Parameters", [("Wind Spiral", {'IAS': 205})])

    assert isinstance(result, mod._FallbackParametersDialog)


def test_show_web_popup_uses_webengine_when_available(monkeypatch):
    mod = _mod()
    monkeypatch.setattr(mod, '_WEBENGINE_AVAILABLE', True)

    calls = []
    monkeypatch.setattr(
        mod, '_show_webengine_popup',
        lambda title, sections, table_content: calls.append(
            (title, sections, table_content)))
    monkeypatch.setattr(mod, '_show_textbrowser_popup', lambda *args: (_ for _ in ()).throw(
        AssertionError('should not use the fallback when WebEngine is available')))

    mod.show_web_popup("Title", [("Section", {'a': 1})])

    assert calls == [("Title", [("Section", {'a': 1})], None)]


def test_show_web_popup_forwards_custom_content_to_webengine(monkeypatch):
    mod = _mod()
    monkeypatch.setattr(mod, '_WEBENGINE_AVAILABLE', True)
    content = mod.TableContent('<table>complete</table>', 'complete')
    calls = []

    monkeypatch.setattr(
        mod,
        '_show_webengine_popup',
        lambda title, sections, table_content: calls.append(
            (title, sections, table_content)),
    )

    mod.show_web_popup(
        "Title", [("CAT A", {'IAS': 100})],
        table_content=content,
    )

    assert calls == [("Title", [("CAT A", {'IAS': 100})], content)]


def test_show_web_popup_forwards_custom_content_to_fallback(monkeypatch):
    mod = _mod()
    monkeypatch.setattr(mod, '_WEBENGINE_AVAILABLE', False)
    content = mod.TableContent('<table>complete</table>', 'complete')
    calls = []

    monkeypatch.setattr(
        mod,
        '_show_textbrowser_popup',
        lambda title, sections, table_content: calls.append(
            (title, sections, table_content)),
    )

    mod.show_web_popup(
        "Title", [("CAT A", {'IAS': 100})],
        table_content=content,
    )

    assert calls == [("Title", [("CAT A", {'IAS': 100})], content)]
