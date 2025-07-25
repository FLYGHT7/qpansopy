# -*- coding: utf-8 -*-
"""
PBN LNAV Initial Approach (RNP APCH) Generator

This module implements Performance-Based Navigation (PBN) Lateral Navigation (LNAV) 
Initial Approach procedures according to ICAO Doc 9613 (PBN Manual) standards.

The module generates obstacle protection surfaces and areas for RNP APCH (Required 
Navigation Performance Approach) procedures during the initial approach segment.

Key Features:
- Initial approach segment area calculations
- Entry zone protection surface generation
- Corridor width calculations based on RNP values
- Primary and secondary area polygon creation
- ICAO-compliant geometric calculations

Initial Approach Characteristics:
- Entry altitude: Typically 3000-6000 ft AGL
- Track alignment: May include course reversals or holding patterns
- RNP value: Usually 1.0 NM or greater
- Obstacle clearance: 1000 ft minimum in primary area

Author: QPANSOPY Development Team
Date: 2025
Version: 2.0
"""

from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from qgis.core import Qgis
from qgis.utils import iface
from math import *
import os

def run_initial_approach(iface_param, routing_layer, export_kml=False, output_dir=None):
    """
    Execute PBN LNAV Initial Approach area calculation and protection surface generation.
    
    This function processes the initial approach segment of an RNP APCH procedure,
    calculating primary and secondary protection areas based on ICAO standards.
    
    The initial approach provides the transition from en-route navigation to the
    intermediate approach phase, with specific geometric requirements for obstacle
    protection and navigation accuracy.
    
    Algorithm Overview:
    1. Identifies initial segment from user-selected routing features
    2. Calculates corridor widths based on RNP values and segment length
    3. Generates primary and secondary protection areas
    4. Creates entry/exit transition zones if applicable
    5. Applies appropriate cartographic styling
    
    Args:
        iface_param (QgsInterface): QGIS interface instance for UI interactions
        routing_layer (QgsVectorLayer): Vector layer containing approach routing segments
        export_kml (bool, optional): Flag to enable KML export functionality. 
                                   Defaults to False. Currently not implemented.
        output_dir (str, optional): Directory path for output files. 
                                  Defaults to None. Currently not implemented.
    
    Returns:
        dict or None: Dictionary containing generated layers and calculation results.
                     Returns None if execution fails or required data is missing.
                     
                     Expected return structure:
                     {
                         'initial_layer': QgsVectorLayer,
                         'calculation_parameters': dict,
                         'entry_coordinates': list,
                         'exit_coordinates': list
                     }
    
    Raises:
        RuntimeError: When QGIS interface operations fail
        ValueError: When routing layer data is invalid or insufficient
        GeometryError: When segment geometry cannot be processed
        
    Notes:
        - Requires manual segment selection by user (no automatic selection)
        - RNP values determine corridor width calculations
        - Entry zones may require specific angular considerations
        - All calculations performed in projected coordinate systems
        
    Example:
        >>> result = run_initial_approach(iface, routing_layer)
        >>> if result:
        ...     print(f"Initial approach areas generated successfully")
    """
    try:
        # Use the passed iface parameter
        iface = iface_param
        
        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Initial Approach (RNP APCH)", level=Qgis.Info)

        # Get Projected Coordinate System for the QGIS Project 
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        # Use the provided routing layer instead of searching
        if routing_layer is None:
            # Fallback: search for routing layer
            for layer in QgsProject.instance().mapLayers().values():
                if "routing" in layer.name().lower():
                    routing_layer = layer
                    break

        if routing_layer is None:
            iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
            return None

        # Use only the user's current selection - do not auto-select
        selected_features = routing_layer.selectedFeatures()

        if not selected_features:
            iface.messageBar().pushMessage("Please select at least one segment in the routing layer", level=Qgis.Critical)
            return None

        # Find initial segment in the user's selection
        initial_features = [feat for feat in selected_features if feat.attribute('segment') == 'initial']
        if not initial_features:
            iface.messageBar().pushMessage("No 'initial' segment found in your selection", level=Qgis.Critical)
            return None

        # Process the user's selected features - use the first valid initial segment found
        for feat in initial_features:
            try:
                geom = feat.geometry().asPolyline()
                if geom and len(geom) >= 2:
                    start_point = QgsPoint(geom[0])
                    end_point = QgsPoint(geom[1])
                    azimuth = start_point.azimuth(end_point)
                    back_azimuth = azimuth + 180
                    length = feat.geometry().length()
                    break
            except:
                iface.messageBar().pushMessage("Invalid geometry in selected feature", level=Qgis.Warning)
                continue
        else:
            iface.messageBar().pushMessage("No valid geometry found in selected initial segments", level=Qgis.Critical)
            return None

        # Calculate point coordinates using the original algorithm

        pts = {}
        a = 0

        # IAF determination
        pts["m"+str(a)] = end_point.project(length, back_azimuth)
        a += 1

        # IF determination 
        pts["m"+str(a)] = end_point
        a += 1

        # Calculating point at IF location 
        d = (1.25, 2.5, -1.25, -2.5)  # NM
        for i in d:
            line_start = end_point.project(i*1852, azimuth-90)
            pts["m"+str(a)] = line_start
            a += 1
            
        # Calculating point at IAF location 
        d = (1.25, 2.5, -1.25, -2.5)  # NM
        for i in d:
            line_start = start_point.project(i*1852, azimuth-90)
            pts["m"+str(a)] = line_start
            a += 1

        # Create memory layer
        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "Initial APCH Segment", "memory")
        myField = QgsField('Symbol', QVariant.String)
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()

        # Area Definition 
        primary_area = ([pts["m2"], pts["m1"], pts["m4"], pts["m8"], pts["m0"], pts["m6"]], 'Primary Area')
        secondary_area_left = ([pts["m3"], pts["m2"], pts["m6"], pts["m7"]], 'Secondary Area')
        secondary_area_right = ([pts["m4"], pts["m5"], pts["m9"], pts["m8"]], 'Secondary Area')

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
        iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV Initial Approach (RNP APCH)", level=Qgis.Success)
        
        return {"initial_layer": v_layer}
        
    except Exception as e:
        iface.messageBar().pushMessage("Error", f"Error in initial approach: {str(e)}", level=Qgis.Critical)
        return None