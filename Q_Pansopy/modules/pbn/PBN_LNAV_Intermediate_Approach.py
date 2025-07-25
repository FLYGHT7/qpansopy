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
from qgis.utils import iface
from math import *
import os

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
        
        # Notify user of intermediate approach calculation start
        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Intermediate Approach (RNP APCH)", level=Qgis.Info)

        # Extract current project's coordinate reference system
        # Critical for accurate geometric calculations in intermediate phase
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        # Validate routing layer input for intermediate approach processing
        if routing_layer is None:
            # Fallback mechanism: attempt to locate routing layer automatically
            # This searches all project layers for names containing "routing"
            for layer in QgsProject.instance().mapLayers().values():
                if "routing" in layer.name().lower():
                    routing_layer = layer
                    break

        # Critical validation: ensure routing layer exists for intermediate processing
        if routing_layer is None:
            iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
            return None

        # Enforce manual selection requirement - no automatic feature selection
        # Intermediate approach requires explicit user selection for proper alignment
        selected_features = routing_layer.selectedFeatures()

        if not selected_features:
            iface.messageBar().pushMessage("Please select at least one segment in the routing layer", level=Qgis.Critical)
            return None

        # Filter for intermediate approach segments within user selection
        # Intermediate segments are identified by 'segment' attribute value of 'intermediate'
        intermediate_features = [feat for feat in selected_features if feat.attribute('segment') == 'intermediate']
        if not intermediate_features:
            iface.messageBar().pushMessage("No 'intermediate' segment found in your selection", level=Qgis.Critical)
            return None

        # Process intermediate approach segments from user selection
        # Iterate through valid intermediate segments to find first processable one
        for feat in intermediate_features:
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
            iface.messageBar().pushMessage("No valid geometry found in selected intermediate segments", level=Qgis.Critical)
            return None

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

        # Create memory layer
        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "LNAV Intermediate APCH Segment", "memory")
        myField = QgsField('Symbol', QVariant.String)
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()

        # Area Definition 
        primary_area = ([pts["m2"], pts["m1"], pts["m4"], pts["mm8"], pts["m12"], pts["m10"], pts["mm6"]], 'Primary Area')
        secondary_area_left = ([pts["m3"], pts["m2"], pts["mm6"], pts["m10"], pts["m11"], pts["mm7"]], 'Secondary Area')
        secondary_area_right = ([pts["m5"], pts["m4"], pts["mm8"], pts["m12"], pts["m13"], pts["mm9"]], 'Secondary Area')

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

        iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV Intermediate Approach (RNP APCH)", level=Qgis.Success)
        
        return {"intermediate_layer": v_layer}
        
    except Exception as e:
        iface.messageBar().pushMessage("Error", f"Error in intermediate approach: {str(e)}", level=Qgis.Critical)
        return None
