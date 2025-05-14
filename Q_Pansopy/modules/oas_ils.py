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
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import Qgis
from qgis.utils import iface
import math
import os
import datetime
import json
import numpy as np

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

def calculate_oas_ils(iface, point_layer, runway_layer, params):
    """
    Create OAS ILS CAT I surfaces
    
    :param iface: QGIS interface
    :param point_layer: Point layer with the threshold point
    :param runway_layer: Runway layer
    :param params: Dictionary with calculation parameters
    :return: Dictionary with results
    """
    # Extract parameters
    THR_elev = float(params.get('THR_elev', 0))
    delta = float(params.get('delta', 0))
    FAP_elev = float(params.get('FAP_elev', 2000))
    MOC_intermediate = float(params.get('MOC_intermediate', 150))
    oas_type = params.get('oas_type', 'Both')
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', os.path.expanduser('~'))
    
    # Calculate derived values
    FAP_height = FAP_elev * 0.3048 - THR_elev  # Convert ft to m and calculate height above threshold
    ILS_extension_height = FAP_height - MOC_intermediate
    
    # Create a parameters dictionary for JSON storage
    parameters_dict = {
        'THR_elev': str(THR_elev),
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
    
    # Define plane constants for OAS surfaces
    # Format: (A, B, C) where Ax + By + C = z
    OAS_W = [0.0267, 0, 0]
    OAS_X = [0.026, 0.026, 0]
    OAS_Y = [-0.026, 0.026, 0]
    OAS_Z = [0, 0.026, 0]
    
    # Calculate OAS template intersections
    OAS_template = {
        "C": solve_plane_intersection(OAS_W, OAS_X, 0),
        "D": solve_plane_intersection(OAS_X, OAS_Y, 0),
        "E": solve_plane_intersection(OAS_Y, OAS_Z, 0),
        "C'": solve_plane_intersection(OAS_W, OAS_X, 300),
        "D'": solve_plane_intersection(OAS_X, OAS_Y, 300),
        "E'": solve_plane_intersection(OAS_Y, OAS_Z, 300)
    }
    
    # Calculate OAS extended intersections
    OAS_extended_to_FAP = {
        "C": OAS_template["C"],
        "D": OAS_template["D"],
        "E": OAS_template["E"],
        "C'": solve_plane_intersection(OAS_W, OAS_X, ILS_extension_height),
        "D'": solve_plane_intersection(OAS_X, OAS_Y, ILS_extension_height),
        "E'": OAS_template["E'"]  # E' is always at 300m
    }
    
    # If any of the calculated intersections is None, fall back to hardcoded values
    if None in OAS_template.values() or None in OAS_extended_to_FAP.values():
        # OAS constants for CAT I (hardcoded)
        OAS_template = {
            "C": (264.912280701755, 51.5006231718033, 0),
            "D": (-314.787533274559, 139.427992202075, 0),
            "E": (-900, 206.14654526464, 0),
            "C'": (16260.701754386, 23.2302945102742, 300),
            "D'": (8383.82771078259, 1217.97418460436, 300),
            "E'": (-12900, 2936.60225698781, 300)
        }
        
        # For extended, use the same values but adjust C' and D' heights
        OAS_extended_to_FAP = {
            "C": OAS_template["C"],
            "D": OAS_template["D"],
            "E": OAS_template["E"],
            "C'": (16260.701754386, 23.2302945102742, ILS_extension_height),
            "D'": (8383.82771078259, 1217.97418460436, ILS_extension_height),
            "E'": OAS_template["E'"]
        }
    
    # Log start
    iface.messageBar().pushMessage("QPANSOPY:", "Executing OAS CAT I", level=Qgis.Info)
    
    # Set start point (0 for start, -1 for end)
    s = 0
    s2 = 180 if s == 0 else 0
    
    # Get map CRS
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Setup coordinate transformations
=======
'''
ILS OAS CAT I
'''

# ----- IMPORTS -----
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox
from PyQt5.QtGui import QColor
from math import *
import json, os, re, numpy as np, math

# ----- GLOBALS (will be updated via the dialog) -----
myglobals = set(globals().keys())

THR_elev = None         # Runway threshold elevation (m)
FAP_elev = None         # FAP elevation (ft)
MOC_intermediate = None # MOC intermediate (m)

# Derived globals.
FAP_height = None
ILS_extension_height = None

# Global variables for computed intersections.
OAS_template = None
OAS_extended_to_FAP = None

# The individual plane constants (W, X, Y, Z) as read from CSV.
OAS_W = None
OAS_X = None
OAS_Y = None
OAS_Z = None

# ----- DIALOG DEFINITION -----
class InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OAS CAT I Input Parameters")
        # Always on top.
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        layout = QFormLayout(self)
        self.thr_line = QLineEdit("31.199328")  # meters
        self.fap_line = QLineEdit("2000")         # feet
        self.moc_line = QLineEdit("150")          # meters
        self.runway_combo = QComboBox()
        self.thr_combo = QComboBox()  # THR layer (points only)
        self.runway_layer_dict = {}
        self.thr_layer_dict = {}
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                if layer.geometryType() == QgsWkbTypes.LineGeometry:
                    self.runway_layer_dict[layer.name()] = layer
                elif layer.geometryType() == QgsWkbTypes.PointGeometry:
                    self.thr_layer_dict[layer.name()] = layer
        sorted_runway = sorted(self.runway_layer_dict.keys())
        sorted_thr = sorted(self.thr_layer_dict.keys())
        self.runway_combo.addItems(sorted_runway)
        self.thr_combo.addItems(sorted_thr)
        self.oas_selection_combo = QComboBox()
        self.oas_selection_combo.addItems(["Template Only", "Extended Only", "Both"])
        self.oas_selection_combo.setCurrentText("Both")
        layout.addRow("THR Elevation (m):", self.thr_line)
        layout.addRow("FAP Elevation (ft):", self.fap_line)
        layout.addRow("MOC Intermediate (m):", self.moc_line)
        layout.addRow("Runway Layer (Line):", self.runway_combo)
        layout.addRow("THR Layer (Points):", self.thr_combo)
        layout.addRow("OAS option:", self.oas_selection_combo)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    def getValues(self):
        try: thr = float(self.thr_line.text())
        except ValueError: thr = 31.199328
        try: fap = float(self.fap_line.text())
        except ValueError: fap = 2000
        try: moc = float(self.moc_line.text())
        except ValueError: moc = 150
        runway_layer = self.runway_layer_dict.get(self.runway_combo.currentText(), None)
        thr_layer = self.thr_layer_dict.get(self.thr_combo.currentText(), None)
        oas_selection = self.oas_selection_combo.currentText()  # "Template Only", "Extended Only", or "Both"
        return thr, fap, moc, runway_layer, thr_layer, oas_selection

# ----- HELPER FUNCTIONS -----
def solve_plane_intersection(plane1, plane2, target_height):
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

def csv_to_structured_json():
    global OAS_template, OAS_extended_to_FAP, OAS_W, OAS_X, OAS_Y, OAS_Z
    csv_path, _ = QFileDialog.getOpenFileName(None, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)")
    if not csv_path:
        # print("No file selected.")
        return
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
        # print("❌ Missing plane constants for:", missing_planes)
        pass
    else:
        lower = {
            "C": solve_plane_intersection(data["OAS constants"]["W plane"],
                                           data["OAS constants"]["X plane"], 0),
            "D": solve_plane_intersection(data["OAS constants"]["X plane"],
                                           data["OAS constants"]["Y plane"], 0),
            "E": solve_plane_intersection(data["OAS constants"]["Y plane"],
                                           data["OAS constants"]["Z plane"], 0)
        }
        upper_template = {
            "C'": solve_plane_intersection(data["OAS constants"]["W plane"],
                                            data["OAS constants"]["X plane"], 300),
            "D'": solve_plane_intersection(data["OAS constants"]["X plane"],
                                            data["OAS constants"]["Y plane"], 300),
            "E'": solve_plane_intersection(data["OAS constants"]["Y plane"],
                                            data["OAS constants"]["Z plane"], 300)
        }
        OAS_template = {**lower, **upper_template}
        upper_extended = {
            "C'": solve_plane_intersection(data["OAS constants"]["W plane"],
                                            data["OAS constants"]["X plane"], ILS_extension_height),
            "D'": solve_plane_intersection(data["OAS constants"]["X plane"],
                                            data["OAS constants"]["Y plane"], ILS_extension_height),
            "E'": solve_plane_intersection(data["OAS constants"]["Y plane"],
                                            data["OAS constants"]["Z plane"], 300)
        }
        OAS_extended_to_FAP = {**lower, **upper_extended}
        data["OAS_template"] = OAS_template
        data["OAS_extended"] = OAS_extended_to_FAP
        OAS_W = data["OAS constants"].get("W plane", None)
        OAS_X = data["OAS constants"].get("X plane", None)
        OAS_Y = data["OAS constants"].get("Y plane", None)
        OAS_Z = data["OAS constants"].get("Z plane", None)
        data["individual_planes"] = {"W": OAS_W, "X": OAS_X, "Y": OAS_Y, "Z": OAS_Z}
    data["used_parameters"] = {
        "FAP_elev": f"{FAP_elev} ft",
        "MOC_intermediate": f"{MOC_intermediate} m"
    }
    json_path = os.path.splitext(csv_path)[0] + "_cleaned.json"
    with open(json_path, 'w', encoding='utf-8') as out_f:
        json.dump(data, out_f, indent=2)
    # print(f"✅ Cleaned JSON saved to: {json_path}")
    return data

# ----- EXTENDED HELPER FUNCTIONS -----
def build_mirrors(intersect_dict):
    d = {}
    for k, v in intersect_dict.items():
        d[k] = v
        d[k + "mirror"] = (v[0], -v[1], v[2])
    return d

def compute_geom(intersections, new_geom, angle0, THR_elev):
    geom_dict = {}
    for m, v in intersections.items():
        OffsetAngle = atan(abs(v[1] / v[0]))
        DistanceOAS = sqrt(v[0]**2 + v[1]**2)
        Z_val = v[2] + THR_elev
        if v[0] > 0 and v[1] > 0:
            dY = -math.cos(OffsetAngle + radians(angle0)) * DistanceOAS
            dX = -math.sin(OffsetAngle + radians(angle0)) * DistanceOAS
        elif v[0] > 0 and v[1] < 0:
            dY = -math.cos(-OffsetAngle + radians(angle0)) * DistanceOAS
            dX = -math.sin(-OffsetAngle + radians(angle0)) * DistanceOAS
        elif v[0] < 0 and v[1] > 0:
            dY = math.cos(OffsetAngle + radians(angle0)) * DistanceOAS
            dX = math.sin(OffsetAngle + radians(angle0)) * DistanceOAS
        elif v[0] < 0 and v[1] < 0:
            dY = math.cos(-OffsetAngle + radians(angle0)) * DistanceOAS
            dX = math.sin(-OffsetAngle + radians(angle0)) * DistanceOAS
        geom_dict[m] = QgsPoint(new_geom[0] + dX, new_geom[1] + dY, Z_val)
    return geom_dict

# ----- MAIN PROCESS -----
def main_process(thr, fap, moc, runway_layer, thr_layer, oas_selection):
    global THR_elev, FAP_elev, MOC_intermediate, FAP_height, ILS_extension_height
    global OAS_template, OAS_extended_to_FAP
    THR_elev = thr
    FAP_elev = fap
    MOC_intermediate = moc
    FAP_height = FAP_elev * 0.3048 - THR_elev
    ILS_extension_height = FAP_height - MOC_intermediate
    full_data = csv_to_structured_json()
    
    # Extract individual plane constants.
    individual = full_data.get("individual_planes", {"W": None, "X": None, "Y": None, "Z": None})
    current_W = individual.get("W")
    current_X = individual.get("X")
    current_Y = individual.get("Y")
    current_Z = individual.get("Z")
    
    # Build layer options.
    layer_options = {}
    if oas_selection == "Template Only":
        layer_options["Template"] = OAS_template
    elif oas_selection == "Extended Only":
        layer_options["Extended"] = OAS_extended_to_FAP
    elif oas_selection == "Both":
        layer_options["Template"] = OAS_template
        layer_options["Extended"] = OAS_extended_to_FAP
    
    from qgis.core import Qgis
    # iface.messageBar().pushMessage("QPANSOPY:", "Executing OAS CAT I", level=Qgis.Info)  # Commented out
    
    s = 0
    s2 = 180 if s != -1 else 0
    selection_runway = runway_layer.selectedFeatures()
    angle0 = None
    for feat in selection_runway:
        geom = feat.geometry().asPolyline()
        if not geom:
            continue
        start_point = QgsPoint(geom[-1 - s])
        end_point = QgsPoint(geom[s])
        angle0 = start_point.azimuth(end_point) + 180
    if angle0 is None:
        return
    # print("angle:", angle0)  # Commented out
    azimuth = angle0 + s2
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    # print(map_srid)  # Commented out
    
    source_crs = QgsCoordinateReferenceSystem(4326)
    dest_crs = QgsCoordinateReferenceSystem(map_srid)
    trto = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    trfm = QgsCoordinateTransform(dest_crs, source_crs, QgsProject.instance())
    
    # Get runway geometry
    if runway_layer and runway_layer.featureCount() > 0:
        runway_feature = next(runway_layer.getFeatures())
        geom = runway_feature.geometry().asPolyline()
        start_point = QgsPoint(geom[-1-s])
        end_point = QgsPoint(geom[s])
        angle0 = start_point.azimuth(end_point) + 180
        back_angle0 = angle0 + 180
    else:
        iface.messageBar().pushMessage("Error", "Runway layer not provided or empty", level=Qgis.Critical)
        return None
    
    # Initial true azimuth data
    azimuth = angle0 + s2
    
    # Get threshold point
    if point_layer and point_layer.featureCount() > 0:
        point_feature = next(point_layer.getFeatures())
        der_geom = point_feature.geometry().asPoint()
        new_geom = der_geom
    else:
        iface.messageBar().pushMessage("Error", "Point layer not provided or empty", level=Qgis.Critical)
        return None
    
    # Determine which OAS options to process
    layer_options = {}
    if oas_type == "Template Only":
        layer_options["Template"] = OAS_template
    elif oas_type == "Extended Only":
        layer_options["Extended"] = OAS_extended_to_FAP
    elif oas_type == "Both":
        layer_options["Template"] = OAS_template
        layer_options["Extended"] = OAS_extended_to_FAP
    
    # Helper function to build mirrored points
    def build_mirrors(intersect_dict):
        d = {}
        for k, v in intersect_dict.items():
            d[k] = v
            d[k + "mirror"] = (v[0], -v[1], v[2])
        return d
    
    # Helper function to compute geometry
    def compute_geom(intersections, new_geom, angle0, THR_elev):
        geom_dict = {}
        for m, v in intersections.items():
            OffsetAngle = math.atan(abs(v[1] / v[0]))
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
            geom_dict[m] = QgsPoint(new_geom[0] + dX, new_geom[1] + dY, Z_val)
        return geom_dict
    
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
            QgsField('parameters', QVariant.String)
        ]
        pr.addAttributes(fields)
        v_layer.updateFields()
        
        # Add features
        features = []
        
        # Y Surface Left
        seg = QgsFeature()
        line_start = [geometry_dict["Dmirror"], geometry_dict["Emirror"], 
                      geometry_dict["E'mirror"], geometry_dict["D'"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
        seg.setAttributes([1, 'Surface Y - Left', parameters_json])
        features.append(seg)
        
        # Y Surface Right
        seg = QgsFeature()
        line_start = [geometry_dict["D"], geometry_dict["D'mirror"], 
                      geometry_dict["E'"], geometry_dict["E"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
        seg.setAttributes([2, 'Surface Y - Right', parameters_json])
        features.append(seg)
        
        # X Surface Left
        seg = QgsFeature()
        line_start = [geometry_dict["C'"], geometry_dict["D'"], 
                      geometry_dict["Dmirror"], geometry_dict["C"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
        seg.setAttributes([3, 'Surface X - Left', parameters_json])
        features.append(seg)
        
        # X Surface Right
        seg = QgsFeature()
        line_start = [geometry_dict["C'mirror"], geometry_dict["D'mirror"], 
                      geometry_dict["D"], geometry_dict["Cmirror"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
        seg.setAttributes([4, 'Surface X - Right', parameters_json])
        features.append(seg)
        
        # W Surface
        seg = QgsFeature()
        line_start = [geometry_dict["C'"], geometry_dict["C'mirror"], 
                      geometry_dict["Cmirror"], geometry_dict["C"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
        seg.setAttributes([5, 'Surface W', parameters_json])
        features.append(seg)
        
        # Z Surface
        seg = QgsFeature()
        line_start = [geometry_dict["E"], geometry_dict["Emirror"], 
                      geometry_dict["E'mirror"], geometry_dict["E'"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
        seg.setAttributes([6, 'Surface Z', parameters_json])
        features.append(seg)
        
        # Ground
        seg = QgsFeature()
        line_start = [geometry_dict["Cmirror"], geometry_dict["C"], 
                      geometry_dict["Dmirror"], geometry_dict["Emirror"], 
                      geometry_dict["E"], geometry_dict["D"]]
        seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
        seg.setAttributes([7, 'Ground', parameters_json])
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
=======
    selection_thr = thr_layer.selectedFeatures()
    new_geom = None
    for feat in selection_thr:
        new_geom = feat.geometry().asPoint()
    if new_geom is None:
        return
    
    # For the Extended option, build hybrid geometry:
    # For Y and Z surfaces, use geometry from Template intersections.
    # For X and W surfaces, use geometry from Extended intersections.
    if "Extended" in layer_options:
        temp_dict = build_mirrors(OAS_template)
        ext_dict = build_mirrors(OAS_extended_to_FAP)
        geom_temp = compute_geom(temp_dict, new_geom, angle0, THR_elev)
        geom_ext = compute_geom(ext_dict, new_geom, angle0, THR_elev)
    
    # Process each OAS option.
    for key, constants in layer_options.items():
        # For non-Extended options, compute geometry normally.
        if key != "Extended":
            geometry_dict = compute_geom(build_mirrors(OAS_template), new_geom, angle0, THR_elev)
        # Create memory layer.
        if key == "Extended":
            layer_name = f"OAS_ILS_Surfaces_Extended_FAP_{FAP_elev}_ft"
        else:
            layer_name = f"OAS_ILS_Surfaces_{key}"
        v_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, layer_name, "memory")
        provider = v_layer.dataProvider()
        fields = [
            QgsField('id', QVariant.Int),
            QgsField('ILS_surface', QVariant.String),
            QgsField('constants', QVariant.String)
        ]
        provider.addAttributes(fields)
        v_layer.updateFields()
        
        # Helper function to add feature.
        def add_feat(id_val, surface, keys_list):
            feat = QgsFeature()
            # Choose geometry dictionary for Extended: if surface is Y or Z use geom_temp, else use geom_ext.
            if key == "Extended":
                if surface.startswith("Surface Y") or surface.startswith("Surface Z") or surface=="Ground":
                    d = geom_temp
                else:
                    d = geom_ext
            else:
                d = geometry_dict
            # For each key in keys_list, if not present, fallback to new_geom.
            line_coords = [d.get(k, new_geom) for k in keys_list]
            geom_poly = QgsPolygon(QgsLineString(line_coords), rings=[])
            feat.setGeometry(geom_poly)
            if surface.startswith("Surface Y"):
                constant_val = current_Y
            elif surface.startswith("Surface X"):
                constant_val = current_X
            elif surface.startswith("Surface W"):
                constant_val = current_W
            elif surface.startswith("Surface Z"):
                constant_val = current_Z
            else:
                constant_val = "[0,0,0]"
            feat.setAttributes([id_val, surface, str(constant_val)])
            provider.addFeatures([feat])
        
        # Add features:
        # Y surfaces & Z surface use keys from template.
        add_feat(1, "Surface Y - Left", ["Dmirror", "Emirror", "E'mirror", "D'"])
        add_feat(2, "Surface Y - Right", ["D", "D'mirror", "E'", "E"])
        # X surfaces & W surface: for Extended key, use keys from ext dictionary;
        # for Template, use template keys.
        add_feat(3, "Surface X - Left", ["C'", "D'", "Dmirror", "C"])
        add_feat(4, "Surface X - Right", ["C'mirror", "D'mirror", "D", "Cmirror"])
        add_feat(5, "Surface W", ["C'", "C'mirror", "Cmirror", "C"])
        # Z surface always from template.
        add_feat(6, "Surface Z", ["E", "Emirror", "E'mirror", "E'"])
        # Ground (use template).
        add_feat(7, "Ground", ["Cmirror", "C", "Dmirror", "Emirror", "E", "D"])
        
        symbol = v_layer.renderer().symbol()
        if key == "Extended":
            symbol.setColor(QColor(0, 255, 0, 127))
            symbol.symbolLayer(0).setStrokeColor(QColor(0, 255, 0))
        else:
            symbol.setColor(QColor(24, 0, 0, 127))
            symbol.symbolLayer(0).setStrokeColor(QColor(24, 0, 0))
        symbol.symbolLayer(0).setStrokeWidth(0.5)
        
        v_layer.selectAll()
        canvas = iface.mapCanvas()
        canvas.zoomToSelected(v_layer)
        sc = canvas.scale()
        if sc < 20000:
            sc = 20000
        canvas.zoomScale(sc)
        
        v_layer.updateExtents()
        QgsProject.instance().addMapLayers([v_layer])
        v_layer.removeSelection()
        # iface.messageBar().pushMessage("QPANSOPY:", f"Finished OAS CAT I for {key}", level=Qgis.Success)  # Commented out
    
    for g in set(globals().keys()).difference(myglobals):
        if g != 'myglobals':
            del globals()[g]

# ----- SHOW THE NON-BLOCKING, ALWAYS-ON-TOP POP-UP AND START THE PROCESS -----
dialog = InputDialog()
dialog.accepted.connect(lambda: main_process(*dialog.getValues()))
dialog.show()