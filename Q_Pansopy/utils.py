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


def fix_kml_altitude_mode(kml_path, show_message=None):
    """
    Fix KML file to use absolute altitude mode instead of clampToGround.
    This ensures 3D surfaces display at their correct elevations in Google Earth.
    
    This function addresses Issue #87: KML exports were being clamped to ground,
    preventing proper 3D visualization of obstacle assessment surfaces.
    
    :param kml_path: Path to the KML file to fix
    :param show_message: Optional callback function to display messages (e.g., iface.messageBar().pushMessage)
    :return: True if successful, False otherwise
    """
    try:
        # Define KML namespace
        KML_NS = 'http://www.opengis.net/kml/2.2'
        GX_NS = 'http://www.google.com/kml/ext/2.2'
        
        # Register namespaces to avoid ns0 prefix in output
        ET.register_namespace('', KML_NS)
        ET.register_namespace('gx', GX_NS)
        
        # Parse the KML file
        tree = ET.parse(kml_path)
        root = tree.getroot()
        
        # Find all geometry elements that need altitude mode fix
        geometry_tags = ['Polygon', 'MultiGeometry', 'LineString', 'LinearRing', 'Point']
        
        modifications_made = 0
        
        for tag in geometry_tags:
            for geom in root.findall(f'.//{{{KML_NS}}}{tag}'):
                # Check if altitudeMode already exists
                altitude_mode = geom.find(f'{{{KML_NS}}}altitudeMode')
                
                if altitude_mode is not None:
                    if altitude_mode.text != 'absolute':
                        altitude_mode.text = 'absolute'
                        modifications_made += 1
                else:
                    # Add altitudeMode element as first child
                    altitude_mode = ET.Element('altitudeMode')
                    altitude_mode.text = 'absolute'
                    geom.insert(0, altitude_mode)
                    modifications_made += 1
                
                # Also handle gx:altitudeMode if present (Google Earth extension)
                gx_altitude_mode = geom.find(f'{{{GX_NS}}}altitudeMode')
                if gx_altitude_mode is not None:
                    if gx_altitude_mode.text != 'absolute':
                        gx_altitude_mode.text = 'absolute'
                        modifications_made += 1
        
        # Write the modified KML back to file
        tree.write(kml_path, encoding='utf-8', xml_declaration=True)
        
        # Read the file and ensure proper structure
        with open(kml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ensure proper XML declaration at the beginning
        if not content.startswith('<?xml'):
            content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content
        
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        if show_message:
            show_message("Success", f"KML altitude mode fixed ({modifications_made} modifications)", Qgis.Success)
        
        return True
        
    except Exception as e:
        if show_message:
            show_message("Warning", f"Could not fix KML altitude mode: {str(e)}", Qgis.Warning)
        return False