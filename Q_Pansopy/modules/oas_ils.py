'''
ILS OAS CAT I
'''

# ----- IMPORTS -----
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox
from PyQt5.QtGui import QColor
from math import *
import json
import os
import re
import numpy as np
import math  # For math.cos, math.sin, radians, etc.

# ----- GLOBALS (will be updated via the dialog) -----
myglobals = set(globals().keys())

# These globals will get their values from the dialog.
THR_elev = None       # Runway threshold elevation in meters
FAP_elev = None       # FAP elevation in feet
MOC_intermediate = None  # MOC intermediate in meters

# The following will be computed based on the above:
FAP_height = None
ILS_extension_height = None

# Global variables for computed outputs and plane coefficients.
OAS_template = None
OAS_extended_to_FAP = None

OAS_W = None
OAS_X = None
OAS_Y = None
OAS_Z = None

# ----- DIALOG DEFINITION -----
class InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OAS CAT I Input Parameters")
        layout = QFormLayout(self)
        
        # Create input fields with defaults.
        self.thr_line = QLineEdit("31.199328")  # default in meters
        self.fap_line = QLineEdit("2000")         # default in feet
        self.moc_line = QLineEdit("150")          # default in meters

        # Create combo boxes for layer selection.
        self.runway_combo = QComboBox()
        self.active_combo = QComboBox()
        self.layer_dict = {}  # Dictionary to store layers with key=layer name

        # Populate the combo boxes with all vector layers from the project.
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                self.layer_dict[layer.name()] = layer
        
        # If no layers are available, the combo boxes will remain empty.
        sorted_layer_names = sorted(self.layer_dict.keys())
        self.runway_combo.addItems(sorted_layer_names)
        self.active_combo.addItems(sorted_layer_names)
        
        # Add fields to the layout.
        layout.addRow("THR Elevation (m):", self.thr_line)
        layout.addRow("FAP Elevation (ft):", self.fap_line)
        layout.addRow("MOC Intermediate (m):", self.moc_line)
        layout.addRow("Runway Layer:", self.runway_combo)
        layout.addRow("Active Layer:", self.active_combo)
        
        # OK and Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def getValues(self):
        try:
            thr = float(self.thr_line.text())
        except ValueError:
            thr = 31.199328
        try:
            fap = float(self.fap_line.text())
        except ValueError:
            fap = 2000
        try:
            moc = float(self.moc_line.text())
        except ValueError:
            moc = 150
        
        runway_layer = self.layer_dict.get(self.runway_combo.currentText(), None)
        active_layer = self.layer_dict.get(self.active_combo.currentText(), None)
        return thr, fap, moc, runway_layer, active_layer

# ----- FUNCTIONS -----
def solve_plane_intersection(plane1, plane2, target_height):
    A1, B1, C1 = plane1
    A2, B2, C2 = plane2

    if (A1 == 0 and B1 == 0) or (A2 == 0 and B2 == 0):
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
        print("No file selected.")
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

            # Break when the designated stopping section is reached.
            if line.startswith('---') and line.strip() == stop_section:
                break

            if line.startswith('---'):
                current_section = line.strip('- \t\n')
                data[current_section] = {}
                continue

            # Split on tabs first; if none, split on commas or multiple spaces.
            if '\t' in line:
                parts = [p.strip().rstrip(',') for p in line.split('\t') if p.strip()]
            else:
                parts = [p.strip().rstrip(',') for p in re.split(r',|\s{2,}', line) if p.strip()]

            if len(parts) == 2:
                key, value = parts
            elif len(parts) > 2:
                key = ' '.join(parts[:-1])
                value = parts[-1]
            else:
                continue

            key = key.strip().rstrip(',')
            try:
                value = float(value)
            except ValueError:
                pass

            # In the "OAS constants" section, group keys like WA, WB, WC into plane coefficients.
            if current_section and current_section == "OAS constants":
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

    # ------------------ Compute Intersections ------------------
    required_planes = ["W plane", "X plane", "Y plane", "Z plane"]
    missing_planes = [p for p in required_planes if p not in data["OAS constants"] or None in data["OAS constants"][p]]
    if missing_planes:
        print("❌ Missing plane constants for:", missing_planes)
    else:
        # Compute lower intersections (at height 0)
        lower = {
            "C": solve_plane_intersection(data["OAS constants"]["W plane"],
                                          data["OAS constants"]["X plane"], 0),
            "D": solve_plane_intersection(data["OAS constants"]["X plane"],
                                          data["OAS constants"]["Y plane"], 0),
            "E": solve_plane_intersection(data["OAS constants"]["Y plane"],
                                          data["OAS constants"]["Z plane"], 0)
        }
        # Upper intersections at height 300 for the OAS_template.
        upper_template = {
            "C'": solve_plane_intersection(data["OAS constants"]["W plane"],
                                           data["OAS constants"]["X plane"], 300),
            "D'": solve_plane_intersection(data["OAS constants"]["X plane"],
                                           data["OAS constants"]["Y plane"], 300),
            "E'": solve_plane_intersection(data["OAS constants"]["Y plane"],
                                           data["OAS constants"]["Z plane"], 300)
        }
        OAS_template = {**lower, **upper_template}

        # For OAS_extended_to_FAP, compute "C'" and "D'" at ILS_extension_height and "E'" remains at 300.
        upper_extended = {
            "C'": solve_plane_intersection(data["OAS constants"]["W plane"],
                                           data["OAS constants"]["X plane"], ILS_extension_height),
            "D'": solve_plane_intersection(data["OAS constants"]["X plane"],
                                           data["OAS constants"]["Y plane"], ILS_extension_height),
            "E'": solve_plane_intersection(data["OAS constants"]["Y plane"],
                                           data["OAS constants"]["Z plane"], 300)
        }
        OAS_extended_to_FAP = {**lower, **upper_extended}

        # Extract individual plane coefficients from the OAS constants section.
        OAS_W = data["OAS constants"].get("W plane", None)
        OAS_X = data["OAS constants"].get("X plane", None)
        OAS_Y = data["OAS constants"].get("Y plane", None)
        OAS_Z = data["OAS constants"].get("Z plane", None)
        # Optionally, add them to the data dictionary.
        data["individual_planes"] = {"W": OAS_W, "X": OAS_X, "Y": OAS_Y, "Z": OAS_Z}

    json_path = os.path.splitext(csv_path)[0] + "_cleaned.json"
    # Dump to JSON (tuples convert to lists).
    with open(json_path, 'w', encoding='utf-8') as out_f:
        json.dump(data, out_f, indent=2)
    print(f"✅ Cleaned JSON saved to: {json_path}")
    
    return data

def main_process(thr, fap, moc, runway_layer, active_layer):
    global THR_elev, FAP_elev, MOC_intermediate, FAP_height, ILS_extension_height
    global OAS_template, OAS_extended_to_FAP, OAS_W, OAS_X, OAS_Y, OAS_Z

    # Set globals from dialog.
    THR_elev = thr            # in meters
    FAP_elev = fap            # in feet
    MOC_intermediate = moc    # in meters
    FAP_height = FAP_elev * 0.3048 - THR_elev
    ILS_extension_height = FAP_height - MOC_intermediate

    # Run CSV parsing and computations.
    full_data = csv_to_structured_json()
    
    # Create mirror values.
    OASconstants = OAS_extended_to_FAP
    OASconstants2 = {}
    for m in OASconstants.keys():
        val = OASconstants[m]
        lst1 = list(val)
        lst1[1] = -val[1]
        OASconstants2[m + "mirror"] = lst1
    # Merge the dictionaries.
    OASconstants3 = OASconstants | OASconstants2

    from qgis.core import Qgis
    iface.messageBar().pushMessage("QPANSOPY:", "Executing OAS CAT I", level=Qgis.Info)

    # --- Compute runway geometry and true azimuth using the user-selected runway layer ---
    # Use 0 for start, -1 for end (s variable).
    s = 0
    s2 = 180 if s != -1 else 0
    selection_runway = runway_layer.selectedFeatures()
    angle0 = None
    # Compute the runway angle from the selected feature(s).
    for feat in selection_runway:
        geom = feat.geometry().asPolyline()
        if not geom:
            continue
        start_point = QgsPoint(geom[-1 - s])
        end_point = QgsPoint(geom[s])
        angle0 = start_point.azimuth(end_point) + 180
        # If more than one feature is selected, the final value is used.
    if angle0 is None:
        print("No runway feature selected in the runway layer.")
        return
    print("angle:", angle0)
    azimuth = angle0 + s2

    # Get map spatial reference.
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    print(map_srid)

    # Set up coordinate transformation.
    source_crs = QgsCoordinateReferenceSystem(4326)
    dest_crs = QgsCoordinateReferenceSystem(map_srid)
    trto = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    trfm = QgsCoordinateTransform(dest_crs, source_crs, QgsProject.instance())

    # --- Use the provided active layer (instead of iface.activeLayer()) for obtaining the reference point ---
    selection_active = active_layer.selectedFeatures()
    new_geom = None
    for feat in selection_active:
        new_geom = feat.geometry().asPoint()
    if new_geom is None:
        print("No feature selected in the active layer.")
        return

    # Create memory layer for OAS surfaces.
    v_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, "OAS_ILS_Surfaces_template", "memory")
    provider = v_layer.dataProvider()
    provider.addAttributes([
        QgsField('id', QVariant.Int),
        QgsField('ILS_surface', QVariant.String),
        QgsField('constants', QVariant.String)
    ])
    v_layer.updateFields()

    # Calculate new geometry for each OAS constant.
    OASconstants4 = {}
    for m in OASconstants3.keys():
        val = OASconstants3[m]
        # Calculate the offset angle and distance.
        OffsetAngle = atan(abs(val[1] / val[0]))
        DistanceOAS = sqrt(abs(val[0] ** 2 + val[1] ** 2))
        # Adjust the Z value with the threshold elevation.
        Z = val[2] + THR_elev
        if val[0] > 0 and val[1] > 0:
            delY = -math.cos(OffsetAngle + radians(angle0)) * DistanceOAS
            delX = -math.sin(OffsetAngle + radians(angle0)) * DistanceOAS
        elif val[0] > 0 and val[1] < 0:
            delY = -math.cos(-OffsetAngle + radians(angle0)) * DistanceOAS
            delX = -math.sin(-OffsetAngle + radians(angle0)) * DistanceOAS
        elif val[0] < 0 and val[1] > 0:
            delY = math.cos(OffsetAngle + radians(angle0)) * DistanceOAS
            delX = math.sin(OffsetAngle + radians(angle0)) * DistanceOAS
        elif val[0] < 0 and val[1] < 0:
            delY = math.cos(-OffsetAngle + radians(angle0)) * DistanceOAS
            delX = math.sin(-OffsetAngle + radians(angle0)) * DistanceOAS

        # Compute new coordinates.
        drawX, drawY = (new_geom[0] + delX, new_geom[1] + delY)
        line_start = QgsPoint(drawX, drawY, Z)
        OASconstants4[m] = line_start

    # --- Create polygon features for the various surfaces ---
    pr = v_layer.dataProvider()
    
    # Y Surface Left 
    line_coords = [OASconstants4["Dmirror"], OASconstants4["Emirror"], OASconstants4["E'mirror"], OASconstants4["D'"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_coords), rings=[]))
    seg.setAttributes([1, 'Surface Y - Left', str(OAS_Y)])
    pr.addFeatures([seg])
    
    # Y Surface Right 
    line_coords = [OASconstants4["D"], OASconstants4["D'mirror"], OASconstants4["E'"], OASconstants4["E"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_coords), rings=[]))
    seg.setAttributes([2, 'Surface Y - Right', str(OAS_Y)])
    pr.addFeatures([seg])
    
    # X Surface Left 
    line_coords = [OASconstants4["C'"], OASconstants4["D'"], OASconstants4["Dmirror"], OASconstants4["C"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_coords), rings=[]))
    seg.setAttributes([3, 'Surface X - Left', str(OAS_X)])
    pr.addFeatures([seg])
    
    # X Surface Right 
    line_coords = [OASconstants4["C'mirror"], OASconstants4["D'mirror"], OASconstants4["D"], OASconstants4["Cmirror"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_coords), rings=[]))
    seg.setAttributes([4, 'Surface X - Right', str(OAS_X)])
    pr.addFeatures([seg])
    
    # W Surface Left 
    line_coords = [OASconstants4["C'"], OASconstants4["C'mirror"], OASconstants4["Cmirror"], OASconstants4["C"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_coords), rings=[]))
    seg.setAttributes([5, 'Surface W', str(OAS_W)])
    pr.addFeatures([seg])
    
    # Z Surface
    line_coords = [OASconstants4["E"], OASconstants4["Emirror"], OASconstants4["E'mirror"], OASconstants4["E'"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_coords), rings=[]))
    seg.setAttributes([6, 'Surface Z', str(OAS_Z)])
    pr.addFeatures([seg])
    
    # Ground 
    line_coords = [OASconstants4["Cmirror"], OASconstants4["C"], OASconstants4["Dmirror"], OASconstants4["Emirror"], OASconstants4["E"], OASconstants4["D"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_coords), rings=[]))
    seg.setAttributes([7, 'Ground', '[0,0,0]'])
    pr.addFeatures([seg])
    
    # --- Style the memory layer ---
    symbol = v_layer.renderer().symbol()
    symbol.setColor(QColor(24, 0, 0, 127))  # Green with 50% opacity (adjust as needed)
    symbol.symbolLayer(0).setStrokeColor(QColor(24, 0, 0))
    symbol.symbolLayer(0).setStrokeWidth(0.5)
    
    # Zoom to layer.
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
    iface.messageBar().pushMessage("QPANSOPY:", "Finished OAS CAT I", level=Qgis.Success)
    
    # Clear any globals added by this script.
    for g in set(globals().keys()).difference(myglobals):
        if g != 'myglobals':
            del globals()[g]

# ----- SHOW THE NON-BLOCKING POP-UP AND START THE PROCESS -----
# Create and show the input dialog (modeless, so it won't block the event loop).
dialog = InputDialog()
# When the dialog is accepted, call main_process with the returned values.
dialog.accepted.connect(lambda: main_process(*dialog.getValues()))
dialog.show()
