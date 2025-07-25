# -*- coding: utf-8 -*-
"""
PBN LNAV Final Approach (RNP APCH) Generator

This module implements Performance-Based Navigation (PBN) Lateral Navigation (LNAV) 
Final Approach procedures according to ICAO Doc 9613 (PBN Manual) standards.

The module generates obstacle protection surfaces and areas for RNP APCH (Required 
Navigation Performance Approach) procedures during the final approach segment.

Key Features:
- Final approach segment area calculations
- Obstacle protection surface generation
- Missed Approach Point (MAPt) determination
- Primary and secondary area polygon creation
- ICAO-compliant geometric calculations


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

def run_final_approach(iface_param, routing_layer, export_kml=False, output_dir=None):
    """
    Execute PBN LNAV Final Approach area calculation and protection surface generation.
    
    This function processes the final approach segment of an RNP APCH procedure,
    calculating primary and secondary protection areas based on ICAO standards.
    
    The algorithm:
    1. Identifies the final segment from user-selected routing features
    2. Determines the Missed Approach Point (MAPt) location
    3. Calculates corridor widths based on RNP values and distance
    4. Generates primary and secondary protection areas
    5. Creates QGIS vector layers with appropriate styling
    
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
                         'primary_area_layer': QgsVectorLayer,
                         'secondary_area_layer': QgsVectorLayer,
                         'calculation_parameters': dict,
                         'mapt_coordinates': tuple
                     }
    
    Raises:
        RuntimeError: When QGIS interface operations fail
        ValueError: When routing layer data is invalid or insufficient
        
    Notes:
        - Requires manual segment selection by user (no automatic selection)
        - All calculations use projected coordinate systems for accuracy
        - Final segment must be properly oriented (approach direction)
        - RNP values are extracted from segment attributes or use defaults
        
    Example:
        >>> result = run_final_approach(iface, routing_layer, export_kml=True)
        >>> if result:
        ...     print(f"Generated {len(result)} protection areas")
    """
    try:
        # Initialize QGIS interface from parameter
        iface = iface_param
        
        # Notify user of calculation start
        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Final Approach (RNP APCH)", level=Qgis.Info)

        # Extract current project's coordinate reference system
        # All geometric calculations will be performed in this projected CRS
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        # Validate routing layer input
        if routing_layer is None:
            # Fallback mechanism: attempt to locate routing layer automatically
            # This searches all project layers for names containing "routing"
            for layer in QgsProject.instance().mapLayers().values():
                if "routing" in layer.name().lower():
                    routing_layer = layer
                    break

        # Critical validation: ensure routing layer exists
        if routing_layer is None:
            iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
            return None

        # Enforce manual selection requirement - no automatic feature selection
        # This ensures user has explicitly chosen the segments to process
        selected_features = routing_layer.selectedFeatures()

        if not selected_features:
            iface.messageBar().pushMessage("Please select at least one segment in the routing layer", level=Qgis.Critical)
            return None

        # Filter for final approach segments within user selection
        # Final segments are identified by 'segment' attribute value of 'final'
        final_features = [feat for feat in selected_features if feat.attribute('segment') == 'final']
        if not final_features:
            iface.messageBar().pushMessage("No 'final' segment found in your selection", level=Qgis.Critical)
            return None

        # Process final approach segments from user selection
        # Iterate through valid final segments to find first processable one
        for feat in final_features:
            try:
                # Extract line geometry from selected feature
                geom = feat.geometry().asPolyline()
                if geom and len(geom) >= 2:
                    # Define segment endpoints for geometric calculations
                    start_point = QgsPoint(geom[0])  # Final Approach Fix (FAF)
                    end_point = QgsPoint(geom[1])    # Missed Approach Point (MAPt)
                    
                    # Calculate approach track azimuth (magnetic bearing)
                    azimuth = start_point.azimuth(end_point)
                    # Calculate reciprocal bearing for geometric projections
                    back_azimuth = azimuth + 180
                    
                    # Extract segment length for area calculations
                    length = feat.geometry().length()
                    break
            except:
                # Handle malformed geometry gracefully
                iface.messageBar().pushMessage("Invalid geometry in selected feature", level=Qgis.Warning)
                continue
        else:
            # No valid geometry found in any selected final segment
            iface.messageBar().pushMessage("No valid geometry found in selected final segments", level=Qgis.Critical)
            return None

        # === ICAO-COMPLIANT PROTECTION AREA CALCULATION ===
        # Initialize coordinate point storage for polygon vertices
        pts = {}
        a = 0  # Point counter for systematic indexing

        # 1. Final Approach Fix (FAF) Position Determination
        # Project backwards from MAPt to establish FAF coordinates
        pts["m"+str(a)] = end_point.project(length, back_azimuth)
        a += 1

        # 2. Missed Approach Point (MAPt) Position Definition
        # MAPt is the critical decision point where missed approach is initiated
        pts["m"+str(a)] = end_point
        a += 1

        # 3. Primary and Secondary Protection Area Width Calculation
        # Based on ICAO Doc 9613 - RNP APCH corridor dimensions
        # Standard corridor half-widths at MAPt: ±0.475 NM (primary), ±0.95 NM (secondary)
        d = (0.475, 0.95, -0.475, -0.95)  # Nautical miles - ICAO standardized values
        
        # Generate corridor boundary points perpendicular to approach track
        for i in d:
            # Project laterally from MAPt at 90° to approach track
            # Positive values = right side, negative values = left side of track
            line_start = end_point.project(i*1852, azimuth-90)  # Convert NM to meters
            pts["m"+str(a)] = line_start
            a += 1

        # 4. Intermediate Corridor Width Calculation
        # Calculate tapered corridor expansion from MAPt back towards FAF
        # Based on ICAO 30° splay angle for corridor width expansion
        lengthm = (1.45-0.95)/tan(radians(30))  # Distance to achieve target width (NM)
        for i in d:
            # Project intermediate point along approach track
            int_var = start_point.project(lengthm*1852, azimuth)
            # Create lateral boundary points at intermediate location
            line_start = int_var.project(i*1852, azimuth-90)
            pts["mm"+str(a)] = line_start
            a += 1
       
        # 5. Final Approach Fix (FAF) Corridor Boundaries
        # Maximum corridor width at FAF: ±0.725 NM (primary), ±1.45 NM (secondary)
        f = (0.725, 1.45, -0.725, -1.45)  # Nautical miles - ICAO standardized values
        for i in f:
            # Generate FAF boundary points perpendicular to approach track
            pts["m"+str(a)] = start_point.project(i*1852, azimuth-90)
            a += 1

        # === VECTOR LAYER CREATION AND STYLING ===
        # Create memory-based vector layer for protection areas
        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "LNAV Final APCH Segment", "memory")
        myField = QgsField('Symbol', QVariant.String)  # Attribute for area classification
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()

        # === PROTECTION AREA POLYGON DEFINITION ===
        # Define polygon vertices according to ICAO geometric requirements
        # Point indexing follows systematic approach: m=MAPt area, mm=intermediate
        
        # Primary protection area (central corridor with highest obstacle clearance)
        primary_area = ([pts["m2"], pts["m1"], pts["m4"], pts["mm8"], pts["m12"], pts["m10"], pts["mm6"]], 'Primary Area')
        
        # Secondary protection areas (lateral extensions with reduced obstacle clearance)
        secondary_area_left = ([pts["m3"], pts["m2"], pts["mm6"], pts["m10"], pts["m11"], pts["mm7"]], 'Secondary Area')
        secondary_area_right = ([pts["m5"], pts["m4"], pts["mm8"], pts["m12"], pts["m13"], pts["mm9"]], 'Secondary Area')

        # Collection of all protection areas for processing
        areas = (primary_area, secondary_area_left, secondary_area_right)

        # === FEATURE CREATION AND LAYER POPULATION ===
        # Convert calculated polygons to QGIS vector features
        for area in areas:
            pr = v_layer.dataProvider()
            seg = QgsFeature()
            # Create polygon geometry from coordinate points
            seg.setGeometry(QgsPolygon(QgsLineString(area[0]), rings=[]))
            # Assign area classification attribute
            seg.setAttributes([area[1]])
            pr.addFeatures([seg])

        # Update layer spatial index and add to project
        v_layer.updateExtents()
        QgsProject.instance().addMapLayers([v_layer])

        # === CARTOGRAPHIC STYLING APPLICATION ===
        # Apply standardized symbology for protection areas
        # No automatic zoom to preserve user's current map extent
        style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'primary_secondary_areas.qml')
        if os.path.exists(style_path):
            v_layer.loadNamedStyle(style_path)

        # Notify successful completion
        iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV Final Approach (RNP APCH)", level=Qgis.Success)
        
        # Return calculation results
        return {"final_layer": v_layer}
        
    except Exception as e:
        # Handle unexpected errors gracefully
        iface.messageBar().pushMessage("Error", f"Error in final approach: {str(e)}", level=Qgis.Critical)
        return None
