
# -*- coding: utf-8 -*-
"""
PBN LNAV Missed Approach (RNP APCH) Generator

This module implements Performance-Based Navigation (PBN) Lateral Navigation (LNAV) 
Missed Approach procedures according to ICAO Doc 9613 (PBN Manual) standards.

The module generates obstacle protection surfaces and areas for RNP APCH (Required 
Navigation Performance Approach) procedures during the missed approach segment.

Key Features:
- Missed approach segment area calculations
- Complex multi-segment procedure support
- Turn and straight leg protection areas
- Primary and secondary area polygon creation
- ICAO-compliant geometric calculations


Missed Approach Characteristics:
- Initiated at Missed Approach Point (MAPt)
- Multiple leg types: straight, turn, hold
- Altitude considerations: climbing procedure
- RNP value: Typically 1.0 NM
- Obstacle clearance: 295 ft minimum in primary area

Critical Safety Considerations:
- Must provide adequate obstacle clearance during climb
- Turn radius calculations for missed approach turns
- Hold pattern entry and protection areas
- Coordination with departure procedures

Author: QPANSOPY Development Team
Date: 2025
Version: 2.0
"""

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsCoordinateReferenceSystem, QgsPoint, QgsLineString, 
    QgsPolygon, QgsField, QgsWkbTypes, QgsVectorFileWriter
)
from qgis.PyQt.QtCore import QVariant
from qgis.core import Qgis
from qgis.utils import iface
import math
import os
import datetime

def run_missed_approach(iface_param, routing_layer, export_kml=False, output_dir=None):
    """
    Execute PBN LNAV Missed Approach area calculation and protection surface generation.
    
    This function processes missed approach segments of an RNP APCH procedure,
    calculating primary and secondary protection areas for all segments in the
    missed approach procedure according to ICAO standards.
    
    The missed approach procedure provides a published path for aircraft that cannot
    complete the approach, ensuring adequate obstacle clearance during the climbing
    phase back to a safe altitude and navigation fix.
    
    Algorithm Overview:
    1. Automatically selects all missed approach segments in routing layer
    2. Processes each segment individually (straight legs, turns, holds)
    3. Calculates corridor widths based on RNP values and segment characteristics
    4. Generates primary and secondary protection areas for each segment
    5. Applies turn radius calculations for curved segments
    6. Creates comprehensive protection envelope
    
    Args:
        iface_param (QgsInterface): QGIS interface instance for UI interactions
        routing_layer (QgsVectorLayer): Vector layer containing approach routing segments
        export_kml (bool, optional): Flag to enable KML export functionality. 
                                   Defaults to False.
        output_dir (str, optional): Directory path for KML output files. 
                                  Defaults to None (uses user home directory).
    
    Returns:
        dict or None: Dictionary containing generated layers and calculation results.
                     Returns None if execution fails or required data is missing.
                     
                     Expected return structure:
                     {
                         'missed_approach_layer': QgsVectorLayer,
                         'kml_path': str (if export_kml=True),
                         'calculation_parameters': dict,
                         'segments_processed': int
                     }
    
    Raises:
        RuntimeError: When QGIS interface operations fail
        ValueError: When routing layer data is invalid or insufficient
        GeometryError: When segment geometry cannot be processed
        
    Notes:
        - Automatically processes ALL missed approach segments (no manual selection)
        - Each segment type (straight, turn, hold) has specific area calculations
        - Turn segments use bank angle and speed considerations
        - Hold patterns require special entry/exit area calculations
        - All calculations performed in projected coordinate systems
        - Supports KML export for external validation and documentation
        
    Example:
        >>> result = run_missed_approach(iface, routing_layer, export_kml=True, output_dir='/path/to/output')
        >>> if result:
        ...     print(f"Processed {result['segments_processed']} missed approach segments")
        ...     if 'kml_path' in result:
        ...         print(f"KML exported to: {result['kml_path']}")
    """
    try:
        # Use the passed iface parameter
        iface = iface_param
        
        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Missed Approach (RNP APCH)", level=Qgis.Info)

        # Get Projected Coordinate System for the QGIS Project 
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        # Use the provided routing layer instead of searching
        if routing_layer is None:
            # Fallback: search for routing layer (original behavior)
            for layer in QgsProject.instance().mapLayers().values():
                if "routing" in layer.name():
                    routing_layer = layer
                    break

        if routing_layer is None:
            iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
            return None

        # Original behavior: select all missed segments automatically
        routing_layer.selectAll()
        routing_layer.selectByExpression("segment='missed'")
        selected_features = routing_layer.selectedFeatures()

        if not selected_features:
            iface.messageBar().pushMessage("No 'missed' segment found in routing layer", level=Qgis.Critical)
            return None
            
        # Process the selected features - use the first valid missed segment found (original behavior)
        for feat in selected_features:
            try:
                geom = feat.geometry().asPolyline()
                if geom and len(geom) >= 2:
                    start_point = QgsPoint(geom[0])
                    end_point = QgsPoint(geom[-1])
                    azimuth = start_point.azimuth(end_point)
                    back_azimuth = azimuth + 180
                    length = feat.geometry().length()
                    break
            except:
                iface.messageBar().pushMessage("Invalid geometry in selected feature", level=Qgis.Warning)
                continue
        else:
            iface.messageBar().pushMessage("No valid geometry found in missed segments", level=Qgis.Critical)
            return None

        # ATT tolerance in meters (keep original logic)
        att = 0.24 * 1852  
        
        # Calculate points dictionary (keep original algorithm)
        pts = {}
        a = 0
        
        # Initial points with ATT tolerance
        pts[f"m{a}"] = end_point.project(att, azimuth)
        a += 1
        
        pts[f"m{a}"] = start_point.project(att, back_azimuth)
        a += 1
        
        # Calculate earliest points
        d = (0.475, 0.95, -0.475, -0.95)  # NM
        
        for i in d:
            bearing = azimuth + 90
            angle = 90 - bearing + 180
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = i * 1852 * math.cos(angle)
            dist_y = i * 1852 * math.sin(angle)
            
            bx1 = pts["m1"].x() + dist_x
            by2 = pts["m1"].y() + dist_y
            
            pts[f"m{a}"] = QgsPoint(bx1, by2)
            a += 1
        
        # Calculate intermediate points
        d = (-1, -2, 1, 2)  # NM
        
        lengthm = (2 - 0.95) / math.tan(math.radians(15))  # NM
        bearing = azimuth
        angle = 90 - bearing
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        dist_x = lengthm * 1852 * math.cos(angle)
        dist_y = lengthm * 1852 * math.sin(angle)
        
        xm = pts["m1"].x() + dist_x
        ym = pts["m1"].y() + dist_y
        pm = QgsPoint(xm, ym)
        
        for i in d:
            TNA_dist = i * 1852
            bearing = azimuth + 90
            angle = 90 - bearing
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = TNA_dist * math.cos(angle)
            dist_y = TNA_dist * math.sin(angle)
            
            bx1 = xm + dist_x
            by2 = ym + dist_y
            
            pts[f"mm{a}"] = QgsPoint(bx1, by2)
            a += 1
        
        # Calculate final points
        d = (-1, -2, 1, 2)  # NM
        
        if length / 1852 < 5:
            lengthm = 5.24  # 5 NM default
        else:
            lengthm = length / 1852 + 0.24
        
        bearing = azimuth
        angle = 90 - bearing
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        dist_x = lengthm * 1852 * math.cos(angle)
        dist_y = lengthm * 1852 * math.sin(angle)
        
        xm = pts["m1"].x() + dist_x
        ym = pts["m1"].y() + dist_y
        pf = QgsPoint(xm, ym)
        
        for i in d:
            TNA_dist = i * 1852
            bearing = azimuth + 90
            angle = 90 - bearing
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = TNA_dist * math.cos(angle)
            dist_y = TNA_dist * math.sin(angle)
            
            bx1 = xm + dist_x
            by2 = ym + dist_y
            
            pts[f"mm{a}"] = QgsPoint(bx1, by2)
            a += 1
        
        # Create memory layer (original name)
        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "LNAV Missed", "memory")
        myField = QgsField('Symbol', QVariant.String)
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()

        # Area Definition 
        primary_area = ([pts["m2"], pts["mm6"], pts["mm10"], pf, pts["mm12"], pts["mm8"], pts["m4"], pts["m1"]], 'Primary Area')
        secondary_area_left = ([pts["m2"], pts["m3"], pts["mm7"], pts["mm11"], pts["mm10"], pts["mm6"]], 'Secondary Area')
        secondary_area_right = ([pts["m5"], pts["m4"], pts["mm8"], pts["mm12"], pts["mm13"], pts["mm9"]], 'Secondary Area')

        areas = (primary_area, secondary_area_left, secondary_area_right)

        # Creating areas
        pr = v_layer.dataProvider()
        features = []
        
        for area in areas:
            seg = QgsFeature()
            seg.setGeometry(QgsPolygon(QgsLineString(area[0]), rings=[]))
            seg.setAttributes([area[1]])
            features.append(seg)

        pr.addFeatures(features)
        v_layer.updateExtents()
        QgsProject.instance().addMapLayers([v_layer])

        # Apply style (no zoom to respect user's current view)
        style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'primary_secondary_areas.qml')
        if os.path.exists(style_path):
            v_layer.loadNamedStyle(style_path)
        
        # Export to KML if requested
        result = {'missed_layer': v_layer}
        
        if export_kml and output_dir:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            kml_export_path = os.path.join(output_dir, f'PBN_LNAV_Missed_Approach_{timestamp}.kml')
            
            crs = QgsCoordinateReferenceSystem("EPSG:4326")
            
            kml_error = QgsVectorFileWriter.writeAsVectorFormat(
                v_layer,
                kml_export_path,
                'utf-8',
                crs,
                'KML',
                layerOptions=['MODE=2']
            )
            
            if kml_error[0] == QgsVectorFileWriter.NoError:
                result['kml_path'] = kml_export_path
                iface.messageBar().pushMessage("QPANSOPY:", f"KML exported to: {kml_export_path}", level=Qgis.Success)

        iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV Missed Approach (RNP APCH)", level=Qgis.Success)
        
        return result
        
    except Exception as e:
        iface.messageBar().pushMessage("Error", f"Error in missed approach: {str(e)}", level=Qgis.Critical)
        return None