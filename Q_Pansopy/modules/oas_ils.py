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
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', os.path.expanduser('~'))
    
    # Create a parameters dictionary for JSON storage
    parameters_dict = {
        'THR_elev': str(THR_elev),
        'delta': str(delta),
        'calculation_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'calculation_type': 'OAS ILS CAT I'
    }
    
    # Convert parameters to JSON string
    parameters_json = json.dumps(parameters_dict)
    
    # OAS constants for CAT I
    OASconstants = {
        "C": (264.912280701755, 51.5006231718033, 0),
        "D": (-314.787533274559, 139.427992202075, 0),
        "E": (-900, 206.14654526464, 0),
        "C'": (16260.701754386, 23.2302945102742, 455.88),
        "D'": (8383.82771078259, 1217.97418460436, 455.88),
        "E'": (-12900, 2936.60225698781, 300)
    }
    
    # Create mirrored constants
    OASconstants2 = {}
    for m in OASconstants.keys():
        val = OASconstants[m]
        lst1 = list(val)
        lst1[1] = -val[1]
        OASconstants2[m + "mirror"] = lst1
    
    # Combine original and mirrored constants
    OASconstants3 = {**OASconstants, **OASconstants2}
    
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
    
    # Create memory layer for OAS surfaces
    v_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, "OAS ILS CAT I", "memory")
    myField = QgsField('ILS_surface', QVariant.String)
    myField2 = QgsField('parameters', QVariant.String)
    v_layer.dataProvider().addAttributes([myField, myField2])
    v_layer.updateFields()
    
    # Calculate OAS points
    OASconstants4 = {}
    for m in OASconstants3.keys():
        val = OASconstants3[m]
        
        # Calculate offset angle and distance
        OffsetAngle = math.atan(abs(val[1]/val[0]))
        DistanceOAS = (math.sqrt(abs(val[0]**2+val[1]**2)))
        Z = val[2] + THR_elev
        
        # Calculate deltas based on quadrant
        if val[0] > 0 and val[1] > 0:
            delY = -math.cos(OffsetAngle + math.radians(angle0)) * DistanceOAS
            delX = -math.sin(OffsetAngle + math.radians(angle0)) * DistanceOAS
        elif val[0] > 0 and val[1] < 0:
            delY = -math.cos(-OffsetAngle + math.radians(angle0)) * DistanceOAS
            delX = -math.sin(-OffsetAngle + math.radians(angle0)) * DistanceOAS
        elif val[0] < 0 and val[1] > 0:
            delY = math.cos(OffsetAngle + math.radians(angle0)) * DistanceOAS
            delX = math.sin(OffsetAngle + math.radians(angle0)) * DistanceOAS
        elif val[0] < 0 and val[1] < 0:
            delY = math.cos(-OffsetAngle + math.radians(angle0)) * DistanceOAS
            delX = math.sin(-OffsetAngle + math.radians(angle0)) * DistanceOAS
        
        # Calculate point coordinates
        drawX, drawY = (new_geom[0] + delX, new_geom[1] + delY)
        line_start = QgsPoint(drawX, drawY, Z)
        OASconstants4[m] = line_start
    
    # Create provider for adding features
    pr = v_layer.dataProvider()
    
    # Add Y Surface Left
    line_start = [OASconstants4["Dmirror"], OASconstants4["Emirror"], OASconstants4["E'mirror"], OASconstants4["D'"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes(['Surface Y - Left', parameters_json])
    pr.addFeatures([seg])
    
    # Add Y Surface Right
    line_start = [OASconstants4["D"], OASconstants4["D'mirror"], OASconstants4["E'"], OASconstants4["E"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes(['Surface Y - Right', parameters_json])
    pr.addFeatures([seg])
    
    # Add X Surface Left
    line_start = [OASconstants4["C'"], OASconstants4["D'"], OASconstants4["Dmirror"], OASconstants4["C"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes(['Surface X - Left', parameters_json])
    pr.addFeatures([seg])
    
    # Add X Surface Right
    line_start = [OASconstants4["C'mirror"], OASconstants4["D'mirror"], OASconstants4["D"], OASconstants4["Cmirror"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes(['Surface X - Right', parameters_json])
    pr.addFeatures([seg])
    
    # Add W Surface
    line_start = [OASconstants4["C'"], OASconstants4["C'mirror"], OASconstants4["Cmirror"], OASconstants4["C"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes(['Surface W', parameters_json])
    pr.addFeatures([seg])
    
    # Add Z Surface
    line_start = [OASconstants4["E"], OASconstants4["Emirror"], OASconstants4["E'mirror"], OASconstants4["E'"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes(['Surface Z', parameters_json])
    pr.addFeatures([seg])
    
    # Add Ground
    line_start = [OASconstants4["Cmirror"], OASconstants4["C"], OASconstants4["Dmirror"], 
                 OASconstants4["Emirror"], OASconstants4["E"], OASconstants4["D"]]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes(['Ground', parameters_json])
    pr.addFeatures([seg])
    
    # Update layer extents
    v_layer.updateExtents()
    
    # Add layer to the project
    QgsProject.instance().addMapLayer(v_layer)
    
    # Zoom to layer
    v_layer.selectAll()
    canvas = iface.mapCanvas()
    canvas.zoomToSelected(v_layer)
    v_layer.removeSelection()
    
    # Adjust scale
    sc = canvas.scale()
    if sc < 20000:
        sc = 20000
    canvas.zoomScale(sc)
    
    # Apply style (note: this will need to be handled differently in the plugin)
    # v_layer.loadNamedStyle('path/to/style.qml')
    
    # Export to KML if requested
    result = {
        'oas_layer': v_layer
    }
    
    if export_kml:
        # Get current timestamp for unique filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define KML export path
        oas_export_path = os.path.join(output_dir, f'oas_ils_cat_i_{timestamp}.kml')
        
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
            result['oas_path'] = oas_export_path
    
    # Show success message
    iface.messageBar().pushMessage("QPANSOPY:", "Finished OAS CAT I", level=Qgis.Success)
    
    return result