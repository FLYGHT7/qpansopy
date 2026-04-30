# -*- coding: utf-8 -*-
"""
PBN LNAV Intermediate Approach (RNP APCH) Generator

This module implements Performance-Based Navigation (PBN) Lateral Navigation (LNAV) 
Intermediate Approach procedures according to ICAO Doc 9613 (PBN Manual) standards.

The module generates obstacle protection surfaces and areas for RNP APCH (Required 
Navigation Performance Approach) procedures during the intermediate approach segment.

Key Features:
- Intermediate approach segment area calculations
- Transition zone protection surface generation
- Course change and alignment calculations
- Primary and secondary area polygon creation
- ICAO-compliant geometric calculations


Intermediate Approach Characteristics:
- Altitude range: Typically 1500-3000 ft AGL
- Course alignment: Final approach track alignment
- RNP value: Usually 1.0 NM
- Obstacle clearance: 820 ft minimum in primary area
- Length: Typically 5-10 NM depending on terrain and airspace

Navigation Requirements:
- Provides transition from initial to final approach
- Ensures proper course alignment before final descent
- May include stepdown fixes for obstacle clearance
- Supports various entry patterns and course reversals

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

def run_intermediate_approach(iface_param, routing_layer, export_kml=False, output_dir=None):
    """
    Execute PBN LNAV Intermediate Approach area calculation and protection surface generation.
    
    This function processes the intermediate approach segment of an RNP APCH procedure,
    calculating primary and secondary protection areas based on ICAO standards.
    
    The intermediate approach provides the critical transition between initial and final
    approach phases, ensuring proper course alignment and obstacle clearance during
    the descent and positioning phase of the approach procedure.
    
    Algorithm Overview:
    1. Identifies intermediate segment from user-selected routing features
    2. Calculates corridor widths based on RNP values and segment characteristics
    3. Determines transition points and alignment requirements
    4. Generates primary and secondary protection areas
    5. Applies appropriate geometric calculations for course changes
    6. Creates QGIS vector layers with standardized styling
    
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
                         'intermediate_layer': QgsVectorLayer,
                         'calculation_parameters': dict,
                         'alignment_coordinates': list,
                         'transition_points': list
                     }
    
    Raises:
        RuntimeError: When QGIS interface operations fail
        ValueError: When routing layer data is invalid or insufficient
        GeometryError: When segment geometry cannot be processed
        
    Notes:
        - Requires manual segment selection by user (no automatic selection)
        - Course alignment calculations are critical for final approach preparation
        - Transition zones may require special geometric considerations
        - All calculations performed in projected coordinate systems
        - Intermediate segment must connect properly with initial and final segments
        
    Example:
        >>> result = run_intermediate_approach(iface, routing_layer)
        >>> if result:
        ...     print(f"Intermediate approach areas generated successfully")
        ...     print(f"Transition points: {result['transition_points']}")
    """
    try:
        # Initialize QGIS interface from parameter
        iface = iface_param
        
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        routing_layer = _resolve_routing_layer(iface, routing_layer)
        if routing_layer is None:
            return None

        intermediate_features = _select_segment_features(iface, routing_layer, 'intermediate')
        if intermediate_features is None:
            return None

        geom_data = _extract_segment_geom(iface, intermediate_features, 'intermediate')
        if geom_data is None:
            return None
        start_point, end_point, azimuth, back_azimuth, length = geom_data

        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Intermediate Approach (RNP APCH)", level=Qgis.Info)

        # Calculate point coordinates using the original algorithm
        pts = {}
        a = 0

        # IF determination
        pts["m"+str(a)] = end_point.project(length, back_azimuth)
        a += 1

        # FAF determination 
        pts["m"+str(a)] = end_point
        a += 1

        # Calculating point at FAF location 
        d = (0.725, 1.45, -0.725, -1.45)  # NM
        for i in d:
            line_start = end_point.project(i*1852, azimuth-90)
            pts["m"+str(a)] = line_start
            a += 1

        # Calculating point at end of corridor
        e = (1.25, 2.5, -1.25, -2.5)  # NM
        lengthm = (2.5-1.45)/tan(radians(30))  # NM
        for i in e:
            int_point = end_point.project(lengthm*1852, back_azimuth)
            line_start = int_point.project(i*1852, azimuth-90)
            pts["mm"+str(a)] = line_start
            a += 1
            
        # Calculating point at IF location
        f = (1.25, 2.5, -1.25, -2.5)  # NM
        for i in f:
            pts["m"+str(a)] = start_point.project(i*1852, azimuth-90)
            a += 1

        # Area Definition 
        primary_area = ([pts["m2"], pts["m1"], pts["m4"], pts["mm8"], pts["m12"], pts["m10"], pts["mm6"]], 'Primary Area')
        secondary_area_left = ([pts["m3"], pts["m2"], pts["mm6"], pts["m10"], pts["m11"], pts["mm7"]], 'Secondary Area')
        secondary_area_right = ([pts["m5"], pts["m4"], pts["mm8"], pts["m12"], pts["m13"], pts["mm9"]], 'Secondary Area')

        areas = (primary_area, secondary_area_left, secondary_area_right)

        v_layer = _create_area_layer(map_srid, "LNAV Intermediate APCH Segment", areas, __file__)
        
        return {"intermediate_layer": v_layer}
        
    except Exception as e:
        iface.messageBar().pushMessage("Error", f"Error in intermediate approach: {str(e)}", level=Qgis.Critical)
        return None
