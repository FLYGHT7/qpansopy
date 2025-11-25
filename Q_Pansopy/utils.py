# -*- coding: utf-8 -*-
"""
/***************************************************************************
Utility functions for QPANSOPY
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces
                        -------------------
   begin                : 2023-04-29
   git sha              : $Format:%H$
   copyright            : (C) 2023 by Your Name
   email                : your.email@example.com
***************************************************************************/

/***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************/
"""

from qgis.core import Qgis
from xml.etree import ElementTree as ET

def get_selected_feature(layer, show_error):
    """
    Selecciona la feature a usar según la lógica:
    - Si hay exactamente una seleccionada, usarla.
    - Si hay más de una seleccionada, error.
    - Si ninguna seleccionada y solo hay una en la capa, usarla.
    - Si ninguna seleccionada y hay varias, error.
    """
    if not layer:
        show_error("No layer provided")
        return None

    selected = layer.selectedFeatures()
    if len(selected) == 1:
        return selected[0]
    elif len(selected) > 1:
        show_error("More than one feature is selected. Please select only one feature.")
        return None
    else:
        all_features = list(layer.getFeatures())
        if len(all_features) == 1:
            return all_features[0]
        elif len(all_features) == 0:
            show_error("No features found in the layer")
            return None
        else:
            show_error("Multiple features found but none selected. Please select one feature.")
            return None

def format_parameters_table(title, params_dict, sections=None):
    """
    Format parameters as a standardized table for Word/text output.
    Supports both flat dictionaries and nested dictionaries grouped by sections.

    Args:
        title: Title for the table
        params_dict: Dictionary of parameters and their values. Can be:
            - flat: {"param": value, "param_unit": "m"}
            - nested: {"group": {"param": {"value": v, "unit": u}, ...}, ...}
        sections: Optional dict mapping param names to section names.

    Returns:
        Formatted table as string.
    """
    # Collect normalized entries as tuples: (section, param_key, value, unit)
    entries = []

    def is_terminal_param(val_dict):
        return isinstance(val_dict, dict) and (
            'value' in val_dict or 'unit' in val_dict
        )

    def traverse(d, group=None):
        # d may be a flat param dict or a nested group dict
        for key, val in d.items():
            # Skip explicit unit-only keys in flat dicts
            if isinstance(val, (str, int, float)) and str(key).endswith('_unit'):
                continue

            if is_terminal_param(val):
                sec = sections.get(key, group or 'General') if sections else (group or 'General')
                v = val.get('value', '')
                u = val.get('unit', '')
                entries.append((sec, key, v, u))
            elif isinstance(val, dict):
                # Could be a nested group or a flat mapping of params -> primitive values
                # Peek to see if children look terminal
                child_keys = list(val.keys())
                looks_like_group = any(isinstance(val.get(k), dict) for k in child_keys)
                if looks_like_group:
                    traverse(val, group=group if sections else (key if group is None else key))
                else:
                    # Treat as flat mapping with optional sibling *_unit keys at parent level
                    for sub_key, sub_val in val.items():
                        if str(sub_key).endswith('_unit'):
                            continue
                        sec = sections.get(sub_key, group or (key if not sections else 'General')) if sections else (group or key or 'General')
                        unit = ''
                        # First look for unit alongside sub_key in this dict
                        unit = val.get(f"{sub_key}_unit", '')
                        entries.append((sec, sub_key, sub_val, unit))
            else:
                # Primitive value at this level (flat dict case)
                sec = sections.get(key, group or 'General') if sections else (group or 'General')
                unit = d.get(f"{key}_unit", '')
                entries.append((sec, key, val, unit))

    traverse(params_dict)

    # Build output grouped by section preserving insertion order
    table = f"{title}\n{'='*50}\n\n"


    if not entries:
        # Fallback: print raw dict if nothing was recognized
        table += "PARAMETER                    VALUE           UNIT\n"
        table += "-"*50 + "\n"
        table += str(params_dict)
        return table

    # Order sections by first appearance
    section_order = []
    for sec, _, _, _ in entries:
        if sec not in section_order:
            section_order.append(sec)

    for sec in section_order:
        section_rows = [(p, v, u) for s, p, v, u in entries if s == sec]
        table += f"\n{sec}\n{'-'*len(sec)}\n"
        table += "PARAMETER                    VALUE           UNIT\n"
        table += "-"*50 + "\n"
        for param_key, value, unit in section_rows:
            param_name = str(param_key).replace('_', ' ').title()
            table += f"{param_name:<25} {str(value):<15} {unit}\n"

    return table