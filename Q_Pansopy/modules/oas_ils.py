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