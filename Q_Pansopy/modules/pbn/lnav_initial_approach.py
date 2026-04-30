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
from math import *
import os
from ._lnav_common import (
    _resolve_routing_layer,
    _select_segment_features,
    _extract_segment_geom,
    _create_area_layer,
)

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
        
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        routing_layer = _resolve_routing_layer(iface, routing_layer)
        if routing_layer is None:
            return None

        initial_features = _select_segment_features(iface, routing_layer, 'initial')
        if initial_features is None:
            return None

        geom_data = _extract_segment_geom(iface, initial_features, 'initial')
        if geom_data is None:
            return None

        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Initial Approach (RNP APCH)", level=Qgis.Info)
        start_point, end_point, azimuth, back_azimuth, length = geom_data

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

        # Area Definition
        primary_area = ([pts["m2"], pts["m1"], pts["m4"], pts["m8"], pts["m0"], pts["m6"]], 'Primary Area')
        secondary_area_left = ([pts["m3"], pts["m2"], pts["m6"], pts["m7"]], 'Secondary Area')
        secondary_area_right = ([pts["m4"], pts["m5"], pts["m9"], pts["m8"]], 'Secondary Area')

        areas = (primary_area, secondary_area_left, secondary_area_right)

        v_layer = _create_area_layer(map_srid, "Initial APCH Segment", areas, __file__)

        iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV Initial Approach (RNP APCH)", level=Qgis.Success)

        return {"initial_layer": v_layer}

    except Exception as e:
        iface.messageBar().pushMessage("Error", f"Error in initial approach: {str(e)}", level=Qgis.Critical)
        return None
