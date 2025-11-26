# -*- coding: utf-8 -*-
"""
/***************************************************************************
Omnidirectional SID Module
                            A QGIS plugin module
Procedure Analysis - Omnidirectional SID Departure Surface Calculation

This module calculates Omnidirectional Standard Instrument Departure (SID)
surfaces according to ICAO PANS-OPS criteria. It generates 3D protection
areas for departures where turns are permitted in any direction.

The module creates three distinct areas:
    - Area 1: From DER to 120m height (15° splay angle)
    - Area 2: From 120m to TNA/H (30° splay angle)  
    - Area 3: Circular buffer from start point to MSA

References:
    - ICAO Doc 8168 PANS-OPS Volume II
    - ICAO Doc 9368 Instrument Flight Procedures Construction Manual
                        -------------------
   begin                : 2025
   copyright            : (C) 2025 by FLYGHT7
***************************************************************************/

/***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************/
"""

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPoint, QgsPolygon, QgsLineString, QgsPointXY, QgsField, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from math import tan, radians


# =============================================================================
# CONSTANTS
# =============================================================================

# Initial height above DER (meters) per PANS-OPS
INITIAL_HEIGHT_ABOVE_DER = 5

# Height at which Area 1 ends (meters)
AREA_1_HEIGHT_LIMIT = 120

# Initial semi-width at DER (meters)
INITIAL_SEMI_WIDTH = 150

# Splay angles for area expansion (degrees)
AREA_1_SPLAY_ANGLE = 15
AREA_2_SPLAY_ANGLE = 30

# Distance before DER for turns-before-DER option (meters)
TAKEOFF_POINT_DISTANCE = 600

# Obstacle clearance margin subtracted from PDG (%)
OCS_MARGIN = 0.8

# Number of segments for circular buffer
BUFFER_SEGMENTS = 360


# =============================================================================
# UNIT CONVERSION FUNCTIONS
# =============================================================================

def meters_to_nautical_miles(meters):
    """
    Convert meters to nautical miles.
    
    Args:
        meters (float): Distance in meters.
        
    Returns:
        float: Distance in nautical miles.
    """
    return meters / 1852


def feet_to_meters(feet):
    """
    Convert feet to meters.
    
    Args:
        feet (float): Distance/altitude in feet.
        
    Returns:
        float: Distance/altitude in meters.
    """
    return feet * 0.3048


# =============================================================================
# AREA DISTANCE CALCULATION FUNCTIONS
# =============================================================================

def calculate_area_1_distance(pdg_percent):
    """
    Calculate the horizontal distance for Area 1.
    
    Area 1 extends from DER to where the aircraft reaches 120m height
    above the DER elevation using the specified PDG.
    
    Args:
        pdg_percent (float): Procedure Design Gradient in percent (e.g., 3.3).
        
    Returns:
        float: Horizontal distance in meters from DER to Area 1 limit.
        
    Formula:
        distance = (height_gain) / (pdg / 100)
        where height_gain = 120m - 5m (initial height above DER)
    """
    height_gain = AREA_1_HEIGHT_LIMIT - INITIAL_HEIGHT_ABOVE_DER
    distance_m = height_gain / (pdg_percent / 100)
    return distance_m


def calculate_area_2_distance(pdg_percent, der_elevation_m, tna_ft):
    """
    Calculate the horizontal distance for Area 2.
    
    Area 2 extends from the Area 1 limit to where the aircraft reaches
    the Turn/Altitude (TNA) before turning, using the specified PDG.
    
    Args:
        pdg_percent (float): Procedure Design Gradient in percent.
        der_elevation_m (float): DER elevation in meters.
        tna_ft (float): Turn Altitude in feet.
        
    Returns:
        float: Horizontal distance in meters for Area 2.
        
    Formula:
        distance = (TNA_m - 120m - DER_elev) / (pdg / 100)
    """
    tna_m = feet_to_meters(tna_ft)
    height_gain = tna_m - AREA_1_HEIGHT_LIMIT - der_elevation_m
    distance_m = height_gain / (pdg_percent / 100)
    return distance_m


def calculate_area_3_distance(pdg_percent, msa_ft, tna_ft, distance_area_1, distance_area_2):
    """
    Calculate the total distance for Area 3 buffer radius.
    
    Area 3 is a circular buffer that extends from the takeoff point
    to where the aircraft reaches MSA. The radius includes distances
    from Area 1 and Area 2.
    
    Args:
        pdg_percent (float): Procedure Design Gradient in percent.
        msa_ft (float): Minimum Sector Altitude in feet.
        tna_ft (float): Turn Altitude in feet.
        distance_area_1 (float): Distance of Area 1 in meters.
        distance_area_2 (float): Distance of Area 2 in meters.
        
    Returns:
        float: Total buffer radius in meters for Area 3.
    """
    msa_m = feet_to_meters(msa_ft)
    tna_m = feet_to_meters(tna_ft)
    distance_msa_segment = (msa_m - tna_m) / (pdg_percent / 100)
    total_distance = distance_msa_segment + distance_area_2 + distance_area_1
    return total_distance


# =============================================================================
# GEOMETRY HELPER FUNCTIONS
# =============================================================================

def create_projected_point(point_name, origin_point, distance, azimuth, elevation, points_dict):
    """
    Create a 3D point by projecting from an origin point.
    
    Projects a point at a specified distance and azimuth from the origin,
    and assigns it a Z value (elevation).
    
    Args:
        point_name (str): Identifier key for the point in the dictionary.
        origin_point (QgsPoint): Starting point for projection.
        distance (float): Distance to project in meters.
        azimuth (float): Azimuth angle in degrees (0=North, clockwise).
        elevation (float): Z value (elevation) for the point in meters.
        points_dict (dict): Dictionary to store the created point.
    """
    projected_point = origin_point.project(distance, azimuth)
    projected_point.addZValue(elevation)
    projected_point.setZ(elevation)
    points_dict[point_name] = projected_point


def create_polygon_surface(surface_name, vertices, layer, surfaces_dict):
    """
    Create a 3D polygon surface and add it to a layer.
    
    Creates a PolygonZ feature from a list of vertices and adds it
    to the specified layer. Also stores the geometry in a dictionary
    for later geometric operations (e.g., difference).
    
    Args:
        surface_name (str): Name/identifier for the surface area.
        vertices (list): List of QgsPoint vertices forming the polygon.
        layer (QgsVectorLayer): Layer to add the feature to.
        surfaces_dict (dict): Dictionary to store the geometry for later use.
    """
    provider = layer.dataProvider()
    feature = QgsFeature()
    polygon = QgsPolygon(QgsLineString(vertices), rings=[])
    feature.setGeometry(polygon)
    feature.setAttributes([surface_name])
    provider.addFeatures([feature])
    surfaces_dict[surface_name] = feature.geometry()


# =============================================================================
# MAIN CALCULATION FUNCTION
# =============================================================================

def run_omnidirectional_sid(iface, runway_layer, params, log_callback=None):
    """
    Execute the Omnidirectional SID surface calculation.
    
    This function calculates and creates 3D departure protection surfaces
    for an Omnidirectional SID procedure. It generates three distinct areas
    with different splay angles and creates them as PolygonZ features.
    
    The calculation follows ICAO PANS-OPS criteria for omnidirectional
    departures where turns are permitted in any direction after reaching
    the specified turn altitude.
    
    Args:
        iface: QGIS interface object for accessing the map canvas and message bar.
        runway_layer (QgsVectorLayer): Line layer containing the runway feature.
            Must have a selected feature representing the runway centerline.
            The line should be oriented from threshold to DER (Departure End of Runway).
        params (dict): Dictionary containing calculation parameters:
            - der_elevation_m (float): DER elevation above MSL in meters.
            - pdg (float): Procedure Design Gradient in percent (e.g., 3.3).
            - TNA_ft (float): Turn Altitude in feet.
            - msa_ft (float): Minimum Sector Altitude in feet.
            - cwy_distance_m (float): Clearway distance beyond DER in meters.
            - allow_turns_before_der (str): 'YES' or 'NO' - whether to include
                the area before DER for turns.
            - include_construction_points (str): 'YES' or 'NO' - whether to
                create a point layer with construction points.
        log_callback (callable, optional): Function to call for logging messages.
            Should accept a single string argument.
    
    Returns:
        dict: Dictionary containing results:
            - layer_name (str): Name of the created polygon layer.
            - areas (list): List of area names created.
            - distance_area_1 (float): Distance of Area 1 in meters.
            - distance_area_2 (float): Distance of Area 2 in meters.
            - distance_area_3 (float): Total distance for Area 3 in meters.
            - width_area_1 (float): Semi-width at Area 1 limit in meters.
            - width_area_2 (float): Semi-width at Area 2 limit in meters.
        Returns None if no runway feature is selected.
    
    Raises:
        No exceptions are raised; errors are logged via log_callback.
    
    Example:
        >>> params = {
        ...     'der_elevation_m': 52,
        ...     'pdg': 3.3,
        ...     'TNA_ft': 2000,
        ...     'msa_ft': 6300,
        ...     'cwy_distance_m': 150,
        ...     'allow_turns_before_der': 'NO',
        ...     'include_construction_points': 'NO'
        ... }
        >>> result = run_omnidirectional_sid(iface, runway_layer, params, print)
    """
    
    def log(message):
        """Internal logging helper."""
        if log_callback:
            log_callback(message)
    
    # Notify user via message bar
    iface.messageBar().pushMessage(
        "QPANSOPY:", 
        "Executing Omnidirectional SID Calculation", 
        level=Qgis.Info
    )
    log("Starting Omnidirectional SID calculation...")
    
    # -------------------------------------------------------------------------
    # Extract and validate parameters
    # -------------------------------------------------------------------------
    der_elevation_m = float(params.get('der_elevation_m', 0))
    pdg_percent = float(params.get('pdg', 3.3))
    tna_ft = float(params.get('TNA_ft', 2000))
    msa_ft = float(params.get('msa_ft', 6300))
    cwy_distance_m = float(params.get('cwy_distance_m', 0))
    allow_turns_before_der = params.get('allow_turns_before_der', 'NO')
    include_construction_points = params.get('include_construction_points', 'NO')
    
    log(f"Parameters: DER Elev={der_elevation_m}m, PDG={pdg_percent}%, "
        f"TNA={tna_ft}ft, MSA={msa_ft}ft")
    log(f"CWY Distance={cwy_distance_m}m, Turns before DER={allow_turns_before_der}")
    
    # -------------------------------------------------------------------------
    # Calculate area distances and elevations
    # -------------------------------------------------------------------------
    
    # Area 1: From DER to 120m height
    distance_area_1 = calculate_area_1_distance(pdg_percent)
    elevation_at_der = der_elevation_m + INITIAL_HEIGHT_ABOVE_DER
    elevation_area_1 = (der_elevation_m + INITIAL_HEIGHT_ABOVE_DER + 
                        distance_area_1 * ((pdg_percent - OCS_MARGIN) / 100))
    
    log(f"Area 1: Distance={distance_area_1:.2f}m, Elevation={elevation_area_1:.2f}m")
    
    # Area 2: From 120m to TNA
    distance_area_2 = calculate_area_2_distance(pdg_percent, der_elevation_m, tna_ft)
    elevation_area_2 = (elevation_area_1 + 
                        distance_area_2 * ((pdg_percent - OCS_MARGIN) / 100))
    
    log(f"Area 2: Distance={distance_area_2:.2f}m, Elevation={elevation_area_2:.2f}m")
    
    # Area 3: Circular buffer to MSA
    distance_area_3 = calculate_area_3_distance(
        pdg_percent, msa_ft, tna_ft, distance_area_1, distance_area_2
    )
    elevation_area_3 = feet_to_meters(msa_ft)
    
    log(f"Area 3: Distance={distance_area_3:.2f}m, Elevation={elevation_area_3:.2f}m")
    
    # -------------------------------------------------------------------------
    # Get map CRS and validate runway selection
    # -------------------------------------------------------------------------
    map_crs = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    selected_features = runway_layer.selectedFeatures()
    
    if not selected_features:
        log("ERROR: No features selected in runway layer. Please select a runway feature.")
        iface.messageBar().pushMessage(
            "QPANSOPY:", 
            "No features selected. Please select a runway.", 
            level=Qgis.Warning
        )
        return None
    
    # -------------------------------------------------------------------------
    # Extract runway geometry and calculate azimuth
    # -------------------------------------------------------------------------
    for feature in selected_features:
        runway_geometry = feature.geometry().asPolyline()
        threshold_point = QgsPoint(runway_geometry[0])
        der_point = QgsPoint(runway_geometry[1])
        runway_azimuth = threshold_point.azimuth(der_point)
    
    log(f"Runway azimuth: {runway_azimuth:.2f}°")
    
    # -------------------------------------------------------------------------
    # Calculate area widths based on splay angles
    # -------------------------------------------------------------------------
    width_area_1 = INITIAL_SEMI_WIDTH + distance_area_1 * tan(radians(AREA_1_SPLAY_ANGLE))
    width_area_2 = width_area_1 + distance_area_2 * tan(radians(AREA_2_SPLAY_ANGLE))
    
    log(f"Width Area 1: {width_area_1:.2f}m, Width Area 2: {width_area_2:.2f}m")
    
    # -------------------------------------------------------------------------
    # Create construction points
    # -------------------------------------------------------------------------
    construction_points = {}
    
    # Area 0 (at DER/CWY)
    create_projected_point(
        'point_0_center', der_point, cwy_distance_m, 
        runway_azimuth, elevation_at_der, construction_points
    )
    create_projected_point(
        'point_0_left', construction_points['point_0_center'], INITIAL_SEMI_WIDTH,
        runway_azimuth - 90, elevation_at_der, construction_points
    )
    create_projected_point(
        'point_0_right', construction_points['point_0_center'], INITIAL_SEMI_WIDTH,
        runway_azimuth + 90, elevation_at_der, construction_points
    )
    
    # Area 1 limit points
    create_projected_point(
        'point_1_center', construction_points['point_0_center'], distance_area_1,
        runway_azimuth, elevation_area_1, construction_points
    )
    create_projected_point(
        'point_1_left', construction_points['point_1_center'], width_area_1,
        runway_azimuth - 90, elevation_area_1, construction_points
    )
    create_projected_point(
        'point_1_right', construction_points['point_1_center'], width_area_1,
        runway_azimuth + 90, elevation_area_1, construction_points
    )
    
    # Area 2 limit points
    create_projected_point(
        'point_2_center', construction_points['point_1_center'], distance_area_2,
        runway_azimuth, elevation_area_2, construction_points
    )
    create_projected_point(
        'point_2_left', construction_points['point_2_center'], width_area_2,
        runway_azimuth - 90, elevation_area_2, construction_points
    )
    create_projected_point(
        'point_2_right', construction_points['point_2_center'], width_area_2,
        runway_azimuth + 90, elevation_area_2, construction_points
    )
    
    # Takeoff point (600m from threshold) for turns-before-DER option
    create_projected_point(
        'point_takeoff_center', threshold_point, TAKEOFF_POINT_DISTANCE,
        runway_azimuth, elevation_at_der, construction_points
    )
    create_projected_point(
        'point_takeoff_left', construction_points['point_takeoff_center'], INITIAL_SEMI_WIDTH,
        runway_azimuth - 90, elevation_at_der, construction_points
    )
    create_projected_point(
        'point_takeoff_right', construction_points['point_takeoff_center'], INITIAL_SEMI_WIDTH,
        runway_azimuth + 90, elevation_at_der, construction_points
    )
    
    # -------------------------------------------------------------------------
    # Create construction points layer (optional)
    # -------------------------------------------------------------------------
    construction_layer = QgsVectorLayer(
        f"PointZ?crs={map_crs}",
        f"OmniSID_Construction_Points_PDG_{pdg_percent}",
        "memory"
    )
    construction_layer.dataProvider().addAttributes([QgsField('id', QVariant.String)])
    construction_layer.updateFields()
    
    for point_name, point_geometry in construction_points.items():
        provider = construction_layer.dataProvider()
        feature = QgsFeature()
        feature.setGeometry(point_geometry)
        feature.setAttributes([point_name])
        provider.addFeatures([feature])
    
    if include_construction_points == 'YES':
        QgsProject.instance().addMapLayers([construction_layer])
        log("Construction points layer added")
    
    # -------------------------------------------------------------------------
    # Create polygon surfaces layer
    # -------------------------------------------------------------------------
    layer_name = f"OmniSID_3D_Area_PDG_{pdg_percent}%"
    surfaces_layer = QgsVectorLayer(
        f"PolygonZ?crs={map_crs}",
        layer_name,
        "memory"
    )
    surfaces_layer.dataProvider().addAttributes([QgsField('omni_area', QVariant.String)])
    surfaces_layer.updateFields()
    
    surfaces_geometries = {}
    
    # Create Area 1 polygon
    create_polygon_surface(
        'Area 1',
        [
            construction_points['point_1_left'],
            construction_points['point_0_left'],
            construction_points['point_0_center'],
            construction_points['point_0_right'],
            construction_points['point_1_right'],
            construction_points['point_1_center']
        ],
        surfaces_layer,
        surfaces_geometries
    )
    
    # Create Area 2 polygon
    create_polygon_surface(
        'Area 2',
        [
            construction_points['point_2_left'],
            construction_points['point_1_left'],
            construction_points['point_1_center'],
            construction_points['point_1_right'],
            construction_points['point_2_right'],
            construction_points['point_2_center']
        ],
        surfaces_layer,
        surfaces_geometries
    )
    
    # Create Before DER area if enabled
    if allow_turns_before_der == 'YES':
        create_polygon_surface(
            'Before DER',
            [
                construction_points['point_0_left'],
                construction_points['point_takeoff_left'],
                construction_points['point_takeoff_center'],
                construction_points['point_takeoff_right'],
                construction_points['point_0_right'],
                construction_points['point_0_center']
            ],
            surfaces_layer,
            surfaces_geometries
        )
    
    # -------------------------------------------------------------------------
    # Create Area 3 (circular buffer minus other areas)
    # -------------------------------------------------------------------------
    buffer_center = QgsPointXY(construction_points['point_takeoff_center'])
    area_3_buffer = QgsGeometry.fromPointXY(buffer_center).buffer(
        distance_area_3, BUFFER_SEGMENTS
    )
    
    # Subtract Area 1 and Area 2 from the buffer
    area_3_geometry = area_3_buffer.difference(surfaces_geometries['Area 2'])
    area_3_geometry = area_3_geometry.difference(surfaces_geometries['Area 1'])
    
    # Subtract Before DER area if it exists
    if allow_turns_before_der == 'YES':
        area_3_geometry = area_3_geometry.difference(surfaces_geometries['Before DER'])
    
    # Add Area 3 to layer
    provider = surfaces_layer.dataProvider()
    area_3_feature = QgsFeature()
    area_3_feature.setGeometry(area_3_geometry)
    area_3_feature.setAttributes(['Area 3'])
    provider.addFeatures([area_3_feature])
    
    surfaces_layer.updateExtents()
    
    # -------------------------------------------------------------------------
    # Apply default styling
    # -------------------------------------------------------------------------
    surfaces_layer.renderer().symbol().setOpacity(0.3)
    surfaces_layer.renderer().symbol().setColor(QColor("blue"))
    iface.layerTreeView().refreshLayerSymbology(iface.activeLayer().id())
    surfaces_layer.triggerRepaint()
    
    # Add layer to project
    QgsProject.instance().addMapLayers([surfaces_layer])
    
    # -------------------------------------------------------------------------
    # Log results summary
    # -------------------------------------------------------------------------
    log("=" * 50)
    log("RESULTS SUMMARY:")
    log(f"Layer created: {layer_name}")
    log(f"Area 1 distance: {distance_area_1:.2f}m "
        f"({meters_to_nautical_miles(distance_area_1):.2f}NM)")
    log(f"Area 2 distance: {distance_area_2:.2f}m "
        f"({meters_to_nautical_miles(distance_area_2):.2f}NM)")
    log(f"Area 3 distance: {distance_area_3:.2f}m "
        f"({meters_to_nautical_miles(distance_area_3):.2f}NM)")
    log("=" * 50)
    log("Omnidirectional SID calculation completed successfully!")
    
    return {
        'layer_name': layer_name,
        'areas': ['Area 1', 'Area 2', 'Area 3'],
        'distance_area_1': distance_area_1,
        'distance_area_2': distance_area_2,
        'distance_area_3': distance_area_3,
        'width_area_1': width_area_1,
        'width_area_2': width_area_2
    }
