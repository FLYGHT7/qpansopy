# -*- coding: utf-8 -*-
"""
Tests for issue #193: registering the 'Show Parameters' QGIS layer action and
resolving a readable dialog title from the stored 'parameters' JSON.
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


def test_register_parameters_action_uses_safe_substitution_tokens(monkeypatch):
    """
    Regression guard: the action code must resolve the feature via
    '[% @layer_id %]' / '[% $id %]' substitution (safe, quote-free) rather
    than interpolating the raw JSON string, which could contain characters
    that break the generated Python literal.
    """
    mod = _mod()

    captured = {}

    class _FakeQgsAction:
        GenericPython = 'generic-python'

        def __init__(self, action_type, name, action_code):
            captured['action_type'] = action_type
            captured['name'] = name
            captured['action_code'] = action_code

    monkeypatch.setattr(mod, 'QgsAction', _FakeQgsAction)

    layer = _FakeLayer()
    mod.register_parameters_action(layer)

    assert len(layer._actions.added) == 1
    code = captured['action_code']
    assert 'show_parameters_inspector' in code
    assert '@layer_id' in code
    assert '$id' in code
    # Never interpolate the raw parameters JSON directly into the action code.
    assert '"parameters"' not in code
