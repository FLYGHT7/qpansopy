# -*- coding: utf-8 -*-
"""
OAS ILS CAT I Generator
"""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsPointXY, QgsWkbTypes, QgsField, QgsFields, QgsPoint,
    QgsLineString, QgsPolygon, QgsVectorFileWriter
)
from qgis.PyQt.QtCore import QVariant, Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox
from qgis.core import Qgis
from qgis.utils import iface
import math
import os
import datetime
import json
import numpy as np
import re
from ..utils import get_selected_feature

# Global variables to store computed values
OAS_template = None
OAS_extended_to_FAP = None
OAS_W = None
OAS_X = None
OAS_Y = None
OAS_Z = None

def solve_plane_intersection(plane1, plane2, target_height):
    """
    Solve the intersection of two planes at a given height
    
    :param plane1: First plane constants (A, B, C)
    :param plane2: Second plane constants (A, B, C)
    :param target_height: Target height for intersection
    :return: Intersection point (X, Y, Z) or None if no intersection
    """
    A1, B1, C1 = plane1
    A2, B2, C2 = plane2
    if (A1==0 and B1==0) or (A2==0 and B2==0):
        return None
    rhs1 = target_height - C1
    rhs2 = target_height - C2
    matrix = np.array([[A1, B1], [A2, B2]])
    rhs = np.array([rhs1, rhs2])
    try:
        solution = np.linalg.solve(matrix, rhs)
        X = round(solution[0], 12)
        Y = round(solution[1], 12)
        return (X, Y, target_height)
    except np.linalg.LinAlgError:
        return None

def csv_to_structured_json(THR_elev, FAP_elev, MOC_intermediate, FAP_height, ILS_extension_height):
    """
    Read OAS constants from a CSV file and convert to structured JSON
    
    :param THR_elev: Threshold elevation in meters
    :param FAP_elev: FAP elevation in feet
    :param MOC_intermediate: MOC intermediate in meters
    :param FAP_height: FAP height in meters
    :param ILS_extension_height: ILS extension height in meters
    :return: Dictionary with structured data or None if file not selected
    """
    global OAS_template, OAS_extended_to_FAP, OAS_W, OAS_X, OAS_Y, OAS_Z
    
    csv_path, _ = QFileDialog.getOpenFileName(None, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)")
    if not csv_path:
        return None
    
    data = {}
    current_section = None
    stop_section = "---OAS Template coordinates -m(meters)"
    plane_constants = {}
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('---') and line.strip() == stop_section:
                break
            if line.startswith('---'):
                current_section = line.strip('- \t\n')
                data[current_section] = {}
                continue
            if '\t' in line:
                parts = [p.strip().rstrip(',') for p in line.split('\t') if p.strip()]
            else:
                parts = [p.strip().rstrip(',') for p in re.split(r',|\s{2,}', line) if p.strip()]
            if len(parts)==2:
                key, value = parts
            elif len(parts)>2:
                key = ' '.join(parts[:-1])
                value = parts[-1]
            else:
                continue
            key = key.strip().rstrip(',')
            try:
                value = float(value)
            except ValueError:
                pass
            if current_section and current_section=="OAS constants":
                match = re.fullmatch(r'([WXYZ])([ABC])', key)
                if match:
                    plane, coeff = match.groups()
                    plane_key = f"{plane} plane"
                    if plane_key not in plane_constants:
                        plane_constants[plane_key] = [None, None, None]
                    index = "ABC".index(coeff)
                    plane_constants[plane_key][index] = value
                    continue
            if current_section:
                data[current_section][key] = value
    
    if "OAS constants" in data:
        data["OAS constants"].update(plane_constants)
    else:
        data["OAS constants"] = plane_constants
    
    required_planes = ["W plane", "X plane", "Y plane", "Z plane"]
    missing_planes = [p for p in required_planes if p not in data["OAS constants"] or None in data["OAS constants"][p]]
    
    if missing_planes:
        iface.messageBar().pushMessage("Warning", f"Missing plane constants for: {', '.join(missing_planes)}", level=Qgis.Warning)
        return None
    else:
        # Extract plane constants
        OAS_W = data["OAS constants"]["W plane"]
        OAS_X = data["OAS constants"]["X plane"]
        OAS_Y = data["OAS constants"]["Y plane"]
        OAS_Z = data["OAS constants"]["Z plane"]
        
        # Calculate intersections for template
        lower = {
            "C": solve_plane_intersection(OAS_W, OAS_X, 0),
            "D": solve_plane_intersection(OAS_X, OAS_Y, 0),
            "E": solve_plane_intersection(OAS_Y, OAS_Z, 0)
        }
        upper_template = {
            "C'": solve_plane_intersection(OAS_W, OAS_X, 300),
            "D'": solve_plane_intersection(OAS_X, OAS_Y, 300),
            "D0'": solve_plane_intersection(OAS_X, OAS_Y, 300),
            "E'": solve_plane_intersection(OAS_Y, OAS_Z, 300)
        }
        OAS_template = {**lower, **upper_template}
        
        # Calculate intersections for extended
        upper_extended = {
            "C'": solve_plane_intersection(OAS_W, OAS_X, ILS_extension_height),
            "D'": solve_plane_intersection(OAS_X, OAS_Y, ILS_extension_height),
            "D0'": solve_plane_intersection(OAS_X, OAS_Y, 300),
            "E'": solve_plane_intersection(OAS_Y, OAS_Z, 300)  # E' is always at 300m
        }
        OAS_extended_to_FAP = {**lower, **upper_extended}
        
        # Store in data dictionary
        data["OAS_template"] = OAS_template
        data["OAS_extended"] = OAS_extended_to_FAP
        data["individual_planes"] = {"W": OAS_W, "X": OAS_X, "Y": OAS_Y, "Z": OAS_Z}
    
    data["used_parameters"] = {
        "THR_elev": f"{THR_elev} m",
        "FAP_elev": f"{FAP_elev} ft",
        "MOC_intermediate": f"{MOC_intermediate} m",
        "FAP_height": f"{FAP_height} m",
        "ILS_extension_height": f"{ILS_extension_height} m"
    }
    
    json_path = os.path.splitext(csv_path)[0] + "_cleaned.json"
    with open(json_path, 'w', encoding='utf-8') as out_f:
        json.dump(data, out_f, indent=2)
    
    iface.messageBar().pushMessage("Success", f"Cleaned JSON saved to: {json_path}", level=Qgis.Success)
    return data

def build_mirrors(intersect_dict):
    """
    Build mirrored points for the given intersections
    
    :param intersect_dict: Dictionary with intersection points
    :return: Dictionary with original and mirrored points
    """
    d = {}
    for k, v in intersect_dict.items():
        d[k] = v
        d[k + "mirror"] = (v[0], -v[1], v[2])
    return d

def compute_geom(intersections, new_geom, angle0, THR_elev):
    """
    Compute geometry for the given intersections
    
    :param intersections: Dictionary with intersection points
    :param new_geom: Reference geometry point
    :param angle0: Reference angle
    :param THR_elev: Threshold elevation
    :return: Dictionary with computed geometry points
    """
    geom_dict = {}
    for m, v in intersections.items():
        try:
            OffsetAngle = math.atan(abs(v[1] / v[0])) if v[0] != 0 else math.pi/2
            DistanceOAS = math.sqrt(v[0]**2 + v[1]**2)
            Z_val = v[2] + THR_elev
            
            if v[0] > 0 and v[1] > 0:
                dY = -math.cos(OffsetAngle + math.radians(angle0)) * DistanceOAS
                dX = -math.sin(OffsetAngle + math.radians(angle0)) * DistanceOAS
            elif v[0] > 0 and v[1] < 0:
                dY = -math.cos(-OffsetAngle + math.radians(angle0)) * DistanceOAS
                dX = -math.sin(-OffsetAngle + math.radians(angle0)) * DistanceOAS
            elif v[0] < 0 and v[1] > 0:
                dY = math.cos(OffsetAngle + math.radians(angle0)) * DistanceOAS
                dX = math.sin(OffsetAngle + math.radians(angle0)) * DistanceOAS
            elif v[0] < 0 and v[1] < 0:
                dY = math.cos(-OffsetAngle + math.radians(angle0)) * DistanceOAS
                dX = math.sin(-OffsetAngle + math.radians(angle0)) * DistanceOAS
            else:  # v[0] == 0 case
                if v[1] > 0:
                    dY = -math.cos(math.radians(angle0)) * DistanceOAS
                    dX = -math.sin(math.radians(angle0)) * DistanceOAS
                else:  # v[1] < 0
                    dY = math.cos(math.radians(angle0)) * DistanceOAS
                    dX = math.sin(math.radians(angle0)) * DistanceOAS
                    
            geom_dict[m] = QgsPoint(new_geom.x() + dX, new_geom.y() + dY, Z_val)
        except Exception as e:
            iface.messageBar().pushMessage("Error", f"Error computing geometry for point {m}: {str(e)}", level=Qgis.Critical)
            # Use a default point at the threshold
            geom_dict[m] = QgsPoint(new_geom.x(), new_geom.y(), THR_elev)
    
    return geom_dict

def calculate_oas_ils(iface, point_layer, runway_layer, params):
    """
    Create OAS ILS CAT I surfaces
    
    :param iface: QGIS interface
    :param point_layer: Point layer with the threshold point
    :param runway_layer: Runway layer
    :param params: Dictionary with calculation parameters
    :return: Dictionary with results
    """
    global OAS_template, OAS_extended_to_FAP, OAS_W, OAS_X, OAS_Y, OAS_Z
    
    # Extract parameters
    THR_elev = float(params.get('THR_elev', 0))  # This is already in meters
    THR_elev_raw = params.get('THR_elev_raw', THR_elev)  # Original value before conversion
    THR_elev_unit = params.get('THR_elev_unit', 'm')  # Original unit
    delta = float(params.get('delta', 0))
    FAP_elev = float(params.get('FAP_elev', 2000))
    MOC_intermediate = float(params.get('MOC_intermediate', 150))
    oas_type = params.get('oas_type', 'Both')
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', os.path.expanduser('~'))
    
    # Calculate derived values (THR_elev is already in meters)
    FAP_height = FAP_elev * 0.3048 - THR_elev  # Convert ft to m and calculate height above threshold
    ILS_extension_height = FAP_height - MOC_intermediate
    
    # Create a parameters dictionary for JSON storage
    parameters_dict = {
        'THR_elev': str(THR_elev),  # Converted value in meters
        'THR_elev_raw': str(THR_elev_raw),  # Original value as entered by user
        'THR_elev_unit': THR_elev_unit,  # Original unit
        'delta': str(delta),
        'FAP_elev': str(FAP_elev),
        'MOC_intermediate': str(MOC_intermediate),
        'FAP_height': str(FAP_height),
        'ILS_extension_height': str(ILS_extension_height),
        'calculation_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'calculation_type': 'OAS ILS CAT I'
    }
    
    # Convert parameters to JSON string
    parameters_json = json.dumps(parameters_dict)
    
    # Load constants from CSV file - this is now mandatory
    csv_path = params.get('csv_path')
    if not csv_path:
        raise ValueError("CSV file path is required but not provided")
    
    # Load constants from the provided CSV file
    csv_data = csv_to_structured_json_from_path(csv_path, THR_elev, FAP_elev, MOC_intermediate, FAP_height, ILS_extension_height)
    if not csv_data:
        raise ValueError("Failed to load constants from CSV file")
    
    # CSV constants have been loaded and applied to global variables OAS_W, OAS_X, OAS_Y, OAS_Z
    # and OAS_template, OAS_extended_to_FAP have been calculated
    
    # Validate that CSV constants were loaded properly
    if not OAS_template or not OAS_extended_to_FAP:
        raise ValueError("Failed to calculate OAS intersections from CSV constants")
    
    # Check if any of the calculated intersections is None
    if None in OAS_template.values() or None in OAS_extended_to_FAP.values():
        raise ValueError("Invalid CSV constants resulted in failed intersection calculations")
    
    # Log start
    iface.messageBar().pushMessage("QPANSOPY:", "Executing OAS CAT I", level=Qgis.Info)
    
    # Check if layers exist
    if not point_layer or not runway_layer:
        iface.messageBar().pushMessage("Error", "Point or runway layer not provided", level=Qgis.Critical)
        return None
    
    # Usar la función auxiliar para obtener las features
    def show_error(message):
        iface.messageBar().pushMessage("Error", message, level=Qgis.Critical)
    
    point_feature = get_selected_feature(point_layer, show_error)
    if not point_feature:
        return None
    
    runway_feature = get_selected_feature(runway_layer, show_error)
    if not runway_feature:
        return None
    
    # Set start point (0 for start, -1 for end)
    s = 0
    s2 = 180 if s == 0 else 0
    
    # Get map CRS
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Get runway geometry
    geom = runway_feature.geometry().asPolyline()
    if not geom:
        iface.messageBar().pushMessage("Error", "Invalid runway geometry", level=Qgis.Critical)
        return None
    
    start_point = QgsPoint(geom[-1-s])
    end_point = QgsPoint(geom[s])
    angle0 = start_point.azimuth(end_point) + 180
    
    # Initial true azimuth data
    azimuth = angle0 + s2
    
    # Get threshold point
    new_geom = point_feature.geometry().asPoint()
    
    # Determine which OAS options to process
    layer_options = {}
    if oas_type == "Template Only":
        layer_options["Template"] = OAS_template
    elif oas_type == "Extended Only":
        layer_options["Extended"] = OAS_extended_to_FAP
    elif oas_type == "Both":
        layer_options["Template"] = OAS_template
        layer_options["Extended"] = OAS_extended_to_FAP
    
    # Results dictionary
    result = {}
    
    # Process each OAS option
    for key, constants in layer_options.items():
        # Create mirrored points
        mirrored_constants = build_mirrors(constants)
        
        # Compute geometry
        geometry_dict = compute_geom(mirrored_constants, new_geom, angle0, THR_elev)
        
        # Create memory layer
        layer_name = f"OAS ILS CAT I - {key}"
        v_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, layer_name, "memory")
        
        # Add fields
        pr = v_layer.dataProvider()
        fields = [
            QgsField('id', QVariant.Int),
            QgsField('ILS_surface', QVariant.String),
            QgsField('parameters', QVariant.String),
            QgsField('constants', QVariant.String)
        ]
        pr.addAttributes(fields)
        v_layer.updateFields()
        
        # Add features
        features = []
        
        # Y Surface Left
        seg = QgsFeature()
        line_start = [geometry_dict["Dmirror"], geometry_dict["Emirror"], 
                      geometry_dict["E'mirror"], geometry_dict["D0'"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start)))
        seg.setAttributes([1, 'Surface Y - Left', parameters_json,str(OAS_Y)])
        features.append(seg)
        
        # Y Surface Right
        seg = QgsFeature()
        line_start = [geometry_dict["D"], geometry_dict["E"], 
                      geometry_dict["E'"], geometry_dict["D0'mirror"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start)))
        seg.setAttributes([2, 'Surface Y - Right', parameters_json,str(OAS_Y)])
        features.append(seg)
        
        # X Surface Left
        seg = QgsFeature()
        line_start = [geometry_dict["C"], geometry_dict["Dmirror"], 
                      geometry_dict["D'"], geometry_dict["C'"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start)))
        seg.setAttributes([3, 'Surface X - Left', parameters_json,str(OAS_X)])
        features.append(seg)
        
        # X Surface Right
        seg = QgsFeature()
        line_start = [geometry_dict["Cmirror"], geometry_dict["D"], 
                      geometry_dict["D'mirror"], geometry_dict["C'mirror"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start)))
        seg.setAttributes([4, 'Surface X - Right', parameters_json,str(OAS_X)])
        features.append(seg)
        
        # W Surface
        seg = QgsFeature()
        line_start = [geometry_dict["C"], geometry_dict["Cmirror"], 
                      geometry_dict["C'mirror"], geometry_dict["C'"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start)))
        seg.setAttributes([5, 'Surface W', parameters_json,str(OAS_W)])
        features.append(seg)
        
        # Z Surface
        seg = QgsFeature()
        line_start = [geometry_dict["E"], geometry_dict["Emirror"], 
                      geometry_dict["E'mirror"], geometry_dict["E'"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start)))
        seg.setAttributes([6, 'Surface Z', parameters_json,str(OAS_Z)])
        features.append(seg)
        
        # Ground
        seg = QgsFeature()
        line_start = [geometry_dict["C"], geometry_dict["Cmirror"], 
                      geometry_dict["D"], geometry_dict["E"], 
                      geometry_dict["Emirror"], geometry_dict["Dmirror"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start)))
        seg.setAttributes([7, 'Ground', parameters_json,'[0,0,0]'])
        features.append(seg)
        
        # Add all features
        pr.addFeatures(features)
        
        # Set layer style
        symbol = v_layer.renderer().symbol()
        if key == "Extended":
            symbol.setColor(QColor(0, 255, 0, 127))
            symbol.symbolLayer(0).setStrokeColor(QColor(0, 255, 0))
        else:
            symbol.setColor(QColor(255, 0, 0, 127))
            symbol.symbolLayer(0).setStrokeColor(QColor(255, 0, 0))
        symbol.symbolLayer(0).setStrokeWidth(0.5)
        
        # Update layer extents
        v_layer.updateExtents()
        
        # Add layer to the project
        QgsProject.instance().addMapLayer(v_layer)
        
        # Store in results
        result[f'oas_layer_{key.lower()}'] = v_layer
        
        # Export to KML if requested
        if export_kml:
            # Get current timestamp for unique filenames
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Define KML export path
            oas_export_path = os.path.join(output_dir, f'oas_ils_cat_i_{key.lower()}_{timestamp}.kml')
            
            # Export to KML
            crs = QgsCoordinateReferenceSystem("EPSG:4326")
            
            # Export OAS layer
            oas_error = QgsVectorFileWriter.writeAsVectorFormat(
                v_layer,
                oas_export_path,
                'utf-8',
                crs,
                'KML',
                layerOptions=['MODE=2']
            )
            
            # Apply corrections to KML file
            if oas_error[0] == QgsVectorFileWriter.NoError:
                result[f'oas_path_{key.lower()}'] = oas_export_path
    
    # Zoom to the first layer
    if result:
        first_layer = next(iter(result.values()))
        if isinstance(first_layer, QgsVectorLayer):
            first_layer.selectAll()
            canvas = iface.mapCanvas()
            canvas.zoomToSelected(first_layer)
            first_layer.removeSelection()
            
            # Adjust scale
            sc = canvas.scale()
            if sc < 20000:
                sc = 20000
            canvas.zoomScale(sc)
    
    # Show success message
    iface.messageBar().pushMessage("QPANSOPY:", "Finished OAS CAT I", level=Qgis.Success)
    
    return result

def copy_parameters_table(params):
    """Generate formatted table for OAS ILS parameters"""
    from ..utils import format_parameters_table
    
    params_dict = {
        'airport_data': {
            'threshold_elevation': {'value': params.get('THR_elev', 0), 'unit': 'm'},
            'delta': {'value': params.get('delta', 0), 'unit': ''}
        },
        'approach_data': {
            'fap_elevation': {'value': params.get('FAP_elev', 2000), 'unit': 'ft'},
            'moc_intermediate': {'value': params.get('MOC_intermediate', 150), 'unit': 'm'}
        },
        'configuration': {
            'oas_type': {'value': params.get('oas_type', 'Both'), 'unit': ''}
        }
    }

    sections = {
        'threshold_elevation': 'Airport Data',
        'delta': 'Airport Data',
        'fap_elevation': 'Approach Data',
        'moc_intermediate': 'Approach Data',
        'oas_type': 'Configuration'
    }

    return format_parameters_table(
        "QPANSOPY OAS ILS PARAMETERS",
        params_dict,
        sections
    )

def csv_to_structured_json_from_path(csv_path, THR_elev, FAP_elev, MOC_intermediate, FAP_height, ILS_extension_height):
    """
    Read OAS constants from a CSV file path and convert to structured JSON
    
    :param csv_path: Path to the CSV file
    :param THR_elev: Threshold elevation in meters
    :param FAP_elev: FAP elevation in feet
    :param MOC_intermediate: MOC intermediate in meters
    :param FAP_height: FAP height in meters
    :param ILS_extension_height: ILS extension height in meters
    :return: Dictionary with structured data or None if error occurs
    """
    global OAS_template, OAS_extended_to_FAP, OAS_W, OAS_X, OAS_Y, OAS_Z
    
    if not csv_path or not os.path.exists(csv_path):
        return None
    
    data = {}
    current_section = None
    stop_section = "---OAS Template coordinates -m(meters)"
    plane_constants = {}
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('---') and line.strip() == stop_section:
                    break
                if line.startswith('---'):
                    current_section = line.strip('- \t\n')
                    data[current_section] = {}
                    continue
                if '\t' in line:
                    parts = [p.strip().rstrip(',') for p in line.split('\t') if p.strip()]
                else:
                    parts = [p.strip().rstrip(',') for p in re.split(r',|\s{2,}', line) if p.strip()]
                if len(parts)==2:
                    key, value = parts
                elif len(parts)>2:
                    key = ' '.join(parts[:-1])
                    value = parts[-1]
                else:
                    continue
                
                if current_section:
                    try:
                        if value.replace('.', '').replace('-', '').isdigit():
                            data[current_section][key] = float(value)
                        else:
                            data[current_section][key] = value
                    except ValueError:
                        data[current_section][key] = value
        
        # Extract plane constants
        for section, values in data.items():
            if 'W' in values and 'X' in values and 'Y' in values and 'Z' in values:
                plane_constants = {
                    'W': [values['W'], 0, 0],
                    'X': [values['X'], values['X'], 0],
                    'Y': [-values['Y'], values['Y'], 0],
                    'Z': [0, values['Z'], 0]
                }
                break
        
        if plane_constants:
            OAS_W = plane_constants['W']
            OAS_X = plane_constants['X']
            OAS_Y = plane_constants['Y']
            OAS_Z = plane_constants['Z']
            
            # Calculate intersections
            OAS_template = {
                "C": solve_plane_intersection(OAS_W, OAS_X, 0),
                "D": solve_plane_intersection(OAS_X, OAS_Y, 0),
                "E": solve_plane_intersection(OAS_Y, OAS_Z, 0),
                "C'": solve_plane_intersection(OAS_W, OAS_X, 300),
                "D0'": solve_plane_intersection(OAS_X, OAS_Y, 300),
                "E'": solve_plane_intersection(OAS_Y, OAS_Z, 300)
            }
            
            OAS_extended_to_FAP = {
                "C": OAS_template["C"],
                "D": OAS_template["D"],
                "E": OAS_template["E"],
                "C'": solve_plane_intersection(OAS_W, OAS_X, ILS_extension_height),
                "D0'": solve_plane_intersection(OAS_X, OAS_Y, ILS_extension_height),
                "E'": solve_plane_intersection(OAS_Y, OAS_Z, ILS_extension_height)
            }
            
            return data
        else:
            return None
            
    except Exception as e:
        print(f"Error reading CSV file: {str(e)}")
        return None