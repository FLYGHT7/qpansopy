# -*- coding: utf-8 -*-
"""
/***************************************************************************
SID Initial Climb Module
                            A QGIS plugin module
Procedure Analysis - SID Initial Climb Protection Areas Calculation

This module calculates SID Initial Climb protection areas including:
    - Turn Initiation Area (TIA): From DER to TNA/H
    - c Area: Pilot reaction time buffer after TNA/H
    - Construction lines for TNA/H reached and SS line

The calculation includes ISA temperature deviation and TAS computation
for accurate turn radius and rate of turn calculations.

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
    QgsPoint, QgsPolygon, QgsLineString, QgsField, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from PyQt5.QtWidgets import QApplication
from math import tan, radians, pi


# =============================================================================
# CONSTANTS
# =============================================================================

# Initial semi-width at DER (meters)
INITIAL_SEMI_WIDTH = 150

# Splay angle for departure area (degrees)
SPLAY_ANGLE = 15

# Maximum rate of turn per ICAO (degrees/second)
MAX_RATE_OF_TURN = 3


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def point_with_z(point, z=0.0):
    """
    Ensure a QgsPoint has a valid Z value.
    
    Args:
        point (QgsPoint): Input point (may have nan Z).
        z (float): Z value to set (default 0.0).
        
    Returns:
        QgsPoint: Point with valid Z coordinate.
    """
    return QgsPoint(point.x(), point.y(), z)


# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================

def calculate_isa_temperature(aerodrome_elevation_m, reference_temperature_c):
    """
    Calculate ISA temperature deviation.
    
    Args:
        aerodrome_elevation_m (float): Aerodrome elevation in meters.
        reference_temperature_c (float): Reference/actual temperature in Celsius.
        
    Returns:
        dict: Dictionary containing:
            - elevation (float): Input elevation
            - temp_ref (float): Reference temperature
            - temp_isa (float): ISA temperature at elevation
            - delta_isa (float): Temperature deviation from ISA
    """
    temp_isa = 15 - 0.00198 * aerodrome_elevation_m
    delta_isa = reference_temperature_c - temp_isa
    
    return {
        'elevation': aerodrome_elevation_m,
        'temp_ref': reference_temperature_c,
        'temp_isa': temp_isa,
        'delta_isa': delta_isa
    }


def calculate_tas_and_turn_parameters(ias_kt, altitude_ft, delta_isa, bank_angle_deg, wind_kt):
    """
    Calculate True Airspeed and turn parameters.
    
    Args:
        ias_kt (float): Indicated Airspeed in knots.
        altitude_ft (float): Altitude in feet.
        delta_isa (float): ISA temperature deviation in Celsius.
        bank_angle_deg (float): Bank angle in degrees.
        wind_kt (float): Wind speed in knots.
        
    Returns:
        dict: Dictionary containing:
            - k_factor (float): Conversion factor
            - tas_kt (float): True Airspeed in knots
            - rate_of_turn (float): Rate of turn in degrees/second
            - radius_of_turn_nm (float): Radius of turn in nautical miles
            - wind_kt (float): Wind speed used
    """
    # Conversion factor calculation
    k_factor = 171233 * (((288 + delta_isa) - 0.00198 * altitude_ft) ** 0.5) / \
               ((288 - 0.00198 * altitude_ft) ** 2.628)
    
    # True Airspeed
    tas_kt = k_factor * ias_kt
    
    # Rate of turn (limited to 3°/s maximum)
    rate_of_turn = (3431 * tan(radians(bank_angle_deg))) / (pi * tas_kt)
    if rate_of_turn > MAX_RATE_OF_TURN:
        rate_of_turn = MAX_RATE_OF_TURN
    
    # Radius of turn
    radius_of_turn_nm = tas_kt / (20 * pi * rate_of_turn)
    
    return {
        'k_factor': k_factor,
        'tas_kt': tas_kt,
        'rate_of_turn': rate_of_turn,
        'radius_of_turn_nm': radius_of_turn_nm,
        'wind_kt': wind_kt
    }


def calculate_pilot_reaction_distance(pilot_time_s, tas_kt, wind_kt):
    """
    Calculate pilot reaction distance.
    
    Args:
        pilot_time_s (float): Pilot reaction time in seconds.
        tas_kt (float): True Airspeed in knots.
        wind_kt (float): Wind speed in knots.
        
    Returns:
        float: Pilot reaction distance in meters.
    """
    # Convert to hours and calculate distance
    time_hours = pilot_time_s / 3600
    distance_nm = time_hours * (tas_kt + wind_kt)
    distance_m = distance_nm * 1852
    return distance_m


def calculate_wind_effect(rate_of_turn, wind_kt):
    """
    Calculate wind effect (E90).
    
    Args:
        rate_of_turn (float): Rate of turn in degrees/second.
        wind_kt (float): Wind speed in knots.
        
    Returns:
        float: Wind effect in nautical miles.
    """
    return (90 / rate_of_turn) * (wind_kt / 3600)


def run_sid_initial_climb(iface, runway_layer, params, log_callback=None):
    """
    Execute the SID Initial Climb protection areas calculation.
    
    This function calculates and creates protection areas for SID initial
    climb procedures, including the Turn Initiation Area and pilot reaction
    buffer zone.
    
    Args:
        iface: QGIS interface object.
        runway_layer (QgsVectorLayer): Line layer with runway feature selected.
        params (dict): Dictionary containing:
            - aerodrome_elevation_m (float): Aerodrome elevation in meters
            - der_elevation_m (float): DER elevation in meters
            - pdg_percent (float): Procedure Design Gradient in percent
            - reference_temp_c (float): Reference temperature in Celsius
            - ias_kt (float): Indicated Airspeed in knots
            - altitude_ft (float): Turn altitude in feet
            - bank_angle_deg (float): Bank angle in degrees
            - wind_kt (float): Wind speed in knots
            - pilot_time_s (float): Pilot reaction time in seconds
            - reverse_direction (str): 'YES' or 'NO'
        log_callback (callable, optional): Logging function.
        
    Returns:
        dict: Results dictionary with calculation parameters and layer names.
    """
    
    def log(message):
        """Internal logging helper."""
        if log_callback:
            log_callback(message)
    
    iface.messageBar().pushMessage(
        "QPANSOPY:", 
        "Executing SID Initial Climb Calculation", 
        level=Qgis.Info
    )
    log("Starting SID Initial Climb calculation...")
    
    # -------------------------------------------------------------------------
    # Extract parameters
    # -------------------------------------------------------------------------
    aerodrome_elevation_m = float(params.get('aerodrome_elevation_m', 0))
    der_elevation_m = float(params.get('der_elevation_m', 0))
    pdg_percent = float(params.get('pdg_percent', 3.3))
    reference_temp_c = float(params.get('reference_temp_c', 15))
    ias_kt = float(params.get('ias_kt', 205))
    altitude_ft = float(params.get('altitude_ft', 5000))
    bank_angle_deg = float(params.get('bank_angle_deg', 15))
    wind_kt = float(params.get('wind_kt', 30))
    pilot_time_s = float(params.get('pilot_time_s', 11))
    reverse_direction = params.get('reverse_direction', 'NO')
    
    log(f"Parameters: AD Elev={aerodrome_elevation_m}m, DER Elev={der_elevation_m}m")
    log(f"PDG={pdg_percent}%, IAS={ias_kt}kt, Altitude={altitude_ft}ft")
    log(f"Bank={bank_angle_deg}°, Wind={wind_kt}kt, Pilot Time={pilot_time_s}s")
    
    # -------------------------------------------------------------------------
    # ISA and TAS calculations
    # -------------------------------------------------------------------------
    isa_values = calculate_isa_temperature(aerodrome_elevation_m, reference_temp_c)
    log(f"ISA deviation: {isa_values['delta_isa']:.2f}°C")
    
    tas_values = calculate_tas_and_turn_parameters(
        ias_kt, altitude_ft, isa_values['delta_isa'], bank_angle_deg, wind_kt
    )
    log(f"TAS: {tas_values['tas_kt']:.2f}kt, Rate of Turn: {tas_values['rate_of_turn']:.2f}°/s")
    log(f"Radius of Turn: {tas_values['radius_of_turn_nm']:.2f}NM")
    
    # Pilot reaction distance
    pilot_reaction_m = calculate_pilot_reaction_distance(
        pilot_time_s, tas_values['tas_kt'], wind_kt
    )
    pilot_reaction_nm = pilot_reaction_m / 1852
    log(f"Pilot Reaction Distance (c): {pilot_reaction_nm:.4f}NM")
    
    # Wind effect
    wind_effect_nm = calculate_wind_effect(tas_values['rate_of_turn'], wind_kt)
    log(f"Wind Effect (E90): {wind_effect_nm:.4f}NM")
    
    # -------------------------------------------------------------------------
    # Calculate TNA/H distance
    # -------------------------------------------------------------------------
    # Distance from DER to TNA/H in meters
    altitude_m = altitude_ft * 0.3048
    tna_distance_m = (altitude_m - der_elevation_m - 5) / (pdg_percent / 100)
    tna_distance_nm = tna_distance_m / 1852
    log(f"Distance to TNA/H: {tna_distance_nm:.4f}NM ({tna_distance_m:.2f}m)")
    
    # -------------------------------------------------------------------------
    # Get map CRS and validate selection
    # -------------------------------------------------------------------------
    map_crs = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    selected_features = runway_layer.selectedFeatures()
    if not selected_features:
        log("ERROR: No features selected. Please select a runway feature.")
        iface.messageBar().pushMessage(
            "QPANSOPY:", 
            "No features selected. Please select a runway.", 
            level=Qgis.Warning
        )
        return None
    
    # -------------------------------------------------------------------------
    # Extract runway geometry
    # -------------------------------------------------------------------------
    for feature in selected_features:
        runway_geometry = feature.geometry().asPolyline()
        
        if reverse_direction == 'YES':
            start_point = QgsPoint(runway_geometry[-1])
            end_point = QgsPoint(runway_geometry[0])
        else:
            start_point = QgsPoint(runway_geometry[0])
            end_point = QgsPoint(runway_geometry[-1])
        
        azimuth = start_point.azimuth(end_point)
    
    log(f"Runway azimuth: {azimuth:.2f}°")
    log(f"Direction: {'End → Start' if reverse_direction == 'YES' else 'Start → End'}")
    
    # -------------------------------------------------------------------------
    # Calculate construction points (all with Z=0)
    # -------------------------------------------------------------------------
    # Ensure end_point has Z=0
    end_point = point_with_z(end_point, 0.0)
    
    # TNA Start points (at DER)
    tna_start_left = point_with_z(end_point.project(INITIAL_SEMI_WIDTH, azimuth - 90), 0.0)
    tna_start_right = point_with_z(end_point.project(INITIAL_SEMI_WIDTH, azimuth + 90), 0.0)
    
    # TNA End points (at TNA/H reached)
    tna_end_center = point_with_z(end_point.project(tna_distance_m, azimuth), 0.0)
    width_at_tna = INITIAL_SEMI_WIDTH + tna_distance_m * tan(radians(SPLAY_ANGLE))
    tna_end_left = point_with_z(tna_end_center.project(width_at_tna, azimuth - 90), 0.0)
    tna_end_right = point_with_z(tna_end_center.project(width_at_tna, azimuth + 90), 0.0)
    
    # c Point (pilot reaction distance beyond TNA)
    c_point_center = point_with_z(tna_end_center.project(pilot_reaction_m, azimuth), 0.0)
    width_at_c = INITIAL_SEMI_WIDTH + (tna_distance_m + pilot_reaction_m) * tan(radians(SPLAY_ANGLE))
    c_point_left = point_with_z(c_point_center.project(width_at_c, azimuth - 90), 0.0)
    c_point_right = point_with_z(c_point_center.project(width_at_c, azimuth + 90), 0.0)
    
    # -------------------------------------------------------------------------
    # Create protection areas layer
    # -------------------------------------------------------------------------
    areas_layer = QgsVectorLayer(
        f"PolygonZ?crs={map_crs}",
        "SID Protection Areas",
        "memory"
    )
    areas_layer.dataProvider().addAttributes([QgsField('Symbol', QVariant.String)])
    areas_layer.updateFields()
    
    provider = areas_layer.dataProvider()
    
    # Turn Initiation Area (TIA)
    tia_vertices = [end_point, tna_start_left, tna_end_left, tna_end_right, tna_start_right]
    tia_feature = QgsFeature()
    tia_feature.setGeometry(QgsPolygon(QgsLineString(tia_vertices), rings=[]))
    tia_feature.setAttributes(['Turn Initiation Area'])
    provider.addFeatures([tia_feature])
    
    # c Area (pilot reaction buffer)
    c_area_vertices = [tna_end_left, c_point_left, c_point_right, tna_end_right]
    c_area_feature = QgsFeature()
    c_area_feature.setGeometry(QgsPolygon(QgsLineString(c_area_vertices), rings=[]))
    c_area_feature.setAttributes(['c Area'])
    provider.addFeatures([c_area_feature])
    
    areas_layer.updateExtents()
    
    # Style the layer
    areas_layer.renderer().symbol().setColor(QColor("green"))
    areas_layer.renderer().symbol().setOpacity(0.7)
    areas_layer.triggerRepaint()
    
    QgsProject.instance().addMapLayers([areas_layer])
    
    # -------------------------------------------------------------------------
    # Create construction lines layer
    # -------------------------------------------------------------------------
    lines_layer = QgsVectorLayer(
        f"LineString?crs={map_crs}",
        "SID Construction Lines",
        "memory"
    )
    lines_layer.dataProvider().addAttributes([QgsField('id', QVariant.String)])
    lines_layer.updateFields()
    
    lines_provider = lines_layer.dataProvider()
    
    # TNA/H Reached line
    tna_line = QgsGeometry.fromPolyline([tna_end_left, tna_end_center, tna_end_right])
    tna_line_feature = QgsFeature()
    tna_line_feature.setGeometry(tna_line)
    tna_line_feature.setAttributes(['TNA/H Reached'])
    lines_provider.addFeatures([tna_line_feature])
    
    # SS Line (c point line)
    ss_line = QgsGeometry.fromPolyline([c_point_left, c_point_center, c_point_right])
    ss_line_feature = QgsFeature()
    ss_line_feature.setGeometry(ss_line)
    ss_line_feature.setAttributes(['SS LINE'])
    lines_provider.addFeatures([ss_line_feature])
    
    lines_layer.updateExtents()
    
    # Style the lines layer
    lines_layer.renderer().symbol().setColor(QColor("purple"))
    lines_layer.renderer().symbol().setWidth(0.5)
    lines_layer.triggerRepaint()
    
    QgsProject.instance().addMapLayers([lines_layer])
    
    # -------------------------------------------------------------------------
    # Zoom to result
    # -------------------------------------------------------------------------
    canvas = iface.mapCanvas()
    canvas.zoomToFeatureExtent(areas_layer.extent())
    
    scale = canvas.scale()
    if scale < 200000:
        canvas.zoomScale(200000)
    
    # -------------------------------------------------------------------------
    # Generate results text for clipboard
    # -------------------------------------------------------------------------
    results_text = generate_results_text(
        altitude_ft, pdg_percent, tna_distance_nm, ias_kt,
        tas_values, bank_angle_deg, wind_kt, pilot_reaction_nm, wind_effect_nm
    )
    
    QApplication.clipboard().setText(results_text)
    log("Results copied to clipboard")
    
    # -------------------------------------------------------------------------
    # Log summary
    # -------------------------------------------------------------------------
    log("=" * 50)
    log("RESULTS SUMMARY:")
    log(f"Turn Initiation Area created")
    log(f"c Area created")
    log(f"Construction lines created")
    log(f"Distance to TNA/H: {tna_distance_nm:.4f}NM")
    log(f"TAS: {tas_values['tas_kt']:.2f}kt")
    log(f"Rate of Turn: {tas_values['rate_of_turn']:.2f}°/s")
    log(f"Radius of Turn: {tas_values['radius_of_turn_nm']:.2f}NM")
    log("=" * 50)
    log("SID Initial Climb calculation completed successfully!")
    
    return {
        'areas_layer': 'SID Protection Areas',
        'lines_layer': 'SID Construction Lines',
        'tna_distance_nm': tna_distance_nm,
        'tas_kt': tas_values['tas_kt'],
        'rate_of_turn': tas_values['rate_of_turn'],
        'radius_of_turn_nm': tas_values['radius_of_turn_nm'],
        'pilot_reaction_nm': pilot_reaction_nm,
        'wind_effect_nm': wind_effect_nm
    }


def generate_results_text(altitude_ft, pdg_percent, tna_distance_nm, ias_kt,
                          tas_values, bank_angle_deg, wind_kt, 
                          pilot_reaction_nm, wind_effect_nm):
    """
    Generate formatted results text for clipboard (tab-separated for Excel/Word paste).
    
    Args:
        Various calculation results.
        
    Returns:
        str: Tab-separated text string for easy paste into spreadsheets.
    """
    lines = [
        'Turn Construction Parameters\t\n',
        'Type of Turn\tTNA/H\n',
        f'Turn Altitude (ft)\t{altitude_ft}\n',
        f'PDG (%)\t{pdg_percent}\n',
        f'Distance to TNA/H (NM)\t{round(tna_distance_nm, 4)}\n',
        f'IAS (kt)\t{ias_kt}\n',
        f'Conversion factor - k\t{round(tas_values["k_factor"], 4)}\n',
        f'TAS (kt)\t{round(tas_values["tas_kt"], 4)}\n',
        f'Bank Angle (°)\t{bank_angle_deg}\n',
        f'Rate of Turn – R (°/s)\t{round(tas_values["rate_of_turn"], 4)}\n',
        f'Radius of turn – r (NM)\t{round(tas_values["radius_of_turn_nm"], 4)}\n',
        f'Wind (kt)\t{wind_kt}\n',
        f'c (NM)\t{round(pilot_reaction_nm, 4)}\n',
        f'E90 (NM)\t{round(wind_effect_nm, 4)}\n'
    ]
    
    return ''.join(lines)
