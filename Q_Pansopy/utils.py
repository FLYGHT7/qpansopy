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
    Format parameters as a standardized table for Word/text output
    Args:
        title: Title for the table
        params_dict: Dictionary of parameters and their values
        sections: Optional dictionary mapping parameter names to section names
    Returns:
        Formatted table as string
    """
    # Header
    table = f"{title}\n{'='*50}\n\n"
    
    if sections:
        current_section = None
        for param, value in params_dict.items():
            section = sections.get(param, "General")
            if section != current_section:
                table += f"\n{section}\n{'-'*len(section)}\n"
                table += "PARAMETER                    VALUE           UNIT\n"
                table += "-"*50 + "\n"
                current_section = section
            
            param_name = param.replace('_', ' ').title()
            if isinstance(value, dict):
                val, unit = value.get('value', ''), value.get('unit', '')
            else:
                val, unit = str(value), params_dict.get(f"{param}_unit", '')
            
            table += f"{param_name:<25} {val:<15} {unit}\n"
    else:
        table += "PARAMETER                    VALUE           UNIT\n"
        table += "-"*50 + "\n"
        for param, value in params_dict.items():
            if param.endswith('_unit'):
                continue
            param_name = param.replace('_', ' ').title()
            unit = params_dict.get(f"{param}_unit", '')
            table += f"{param_name:<25} {value:<15} {unit}\n"
    
    return table