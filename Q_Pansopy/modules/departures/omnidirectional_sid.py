# -*- coding: utf-8 -*-
"""
/***************************************************************************
Omnidirectional SID Module
                            A QGIS plugin module
Procedure Analysis - Omnidirectional SID Departure Surface Calculation
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


def convert_m_nm(val):
    """Convert meters to nautical miles"""
    nm_value = val / 1852
    return nm_value


def convert_ft_m(val):
    """Convert feet to meters"""
    m_value = val * 0.3048
    return m_value


def calculate_area1_limit(pdg):
    """
    Area 1 is where the aircraft reaches 120 m height
    with the provided PDG
    """
    distance_area1_m = (120 - 5) / (pdg / 100)
    return distance_area1_m


def calculate_area2_limit(pdg, der_elevation, TNA_ft):
    """
    Area 2 is where the aircraft reaches TNA/H before turning
    with the provided PDG
    """
    distance_area2_m = (convert_ft_m(TNA_ft) - 120 - der_elevation) / (pdg / 100)
    return distance_area2_m


def calculate_area3_limit(pdg, msa_ft, TNA_ft, distance_area1, distance_area2):
    """
    Area 3 is where the aircraft reaches MSA
    with the provided PDG
    """
    distance_area3_m = (convert_ft_m(msa_ft) - convert_ft_m(TNA_ft)) / (pdg / 100) + distance_area2 + distance_area1
    return distance_area3_m


def calculate_points(point_name, initial_point, distance, angle, Z, point_list):
    """Calculate limiting points for areas"""
    calculated_point = initial_point.project(distance, angle)
    calculated_point.addZValue(Z)
    calculated_point.setZ(Z)
    point_list[point_name] = calculated_point


def add_surface(surface_name, points, v_layer, surface_list):
    """Add a surface polygon to the layer"""
    line_start = points
    pr = v_layer.dataProvider()
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes([surface_name])
    pr.addFeatures([seg])
    surface_list[surface_name] = seg.geometry()


def run_omnidirectional_sid(iface, runway_layer, params, log_callback=None):
    """
    Run the Omnidirectional SID calculation.
    
    :param iface: QGIS interface
    :param runway_layer: Vector layer with runway line feature (must have selection)
    :param params: Dictionary with calculation parameters:
        - der_elevation_m: DER elevation in meters
        - pdg: Procedure Design Gradient (%)
        - TNA_ft: Turning Altitude in feet
        - msa_ft: Minimum Safe Altitude in feet
        - cwy_distance_m: Clearway distance in meters
        - allow_turns_before_der: 'YES' or 'NO'
        - include_construction_points: 'YES' or 'NO'
    :param log_callback: Optional callback function for logging
    :return: Dictionary with result information
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
    
    iface.messageBar().pushMessage("QPANSOPY:", "Executing Omnidirectional SID Calculation", level=Qgis.Info)
    log("Starting Omnidirectional SID calculation...")
    
    # Extract parameters
    der_elevation_m = float(params.get('der_elevation_m', 0))
    pdg = float(params.get('pdg', 3.3))
    TNA_ft = float(params.get('TNA_ft', 2000))
    msa_ft = float(params.get('msa_ft', 6300))
    cwy_distance_m = float(params.get('cwy_distance_m', 0))
    allow_turns_before_der = params.get('allow_turns_before_der', 'NO')
    include_construction_points = params.get('include_construction_points', 'NO')
    
    log(f"Parameters: DER Elev={der_elevation_m}m, PDG={pdg}%, TNA={TNA_ft}ft, MSA={msa_ft}ft")
    log(f"CWY Distance={cwy_distance_m}m, Turns before DER={allow_turns_before_der}")
    
    # Area 1 Calculation
    distance_area1 = calculate_area1_limit(pdg)
    elevation_area0 = der_elevation_m + 5
    elevation_area1 = der_elevation_m + 5 + distance_area1 * ((pdg - 0.8) / 100)
    
    log(f"Area 1: Distance={distance_area1:.2f}m, Elevation={elevation_area1:.2f}m")
    
    # Area 2 Calculation
    distance_area2 = calculate_area2_limit(pdg, der_elevation_m, TNA_ft)
    elevation_area2 = elevation_area1 + distance_area2 * ((pdg - 0.8) / 100)
    
    log(f"Area 2: Distance={distance_area2:.2f}m, Elevation={elevation_area2:.2f}m")
    
    # Area 3 Calculation
    distance_area3 = calculate_area3_limit(pdg, msa_ft, TNA_ft, distance_area1, distance_area2)
    elevation_area3 = convert_ft_m(msa_ft)
    
    log(f"Area 3: Distance={distance_area3:.2f}m, Elevation={elevation_area3:.2f}m")
    
    # Map SRID
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Get selected features from runway layer
    selection = runway_layer.selectedFeatures()
    
    if not selection:
        log("ERROR: No features selected in runway layer. Please select a runway feature.")
        iface.messageBar().pushMessage("QPANSOPY:", "No features selected. Please select a runway.", level=Qgis.Warning)
        return None
    
    # Process selected runway
    for feat in selection:
        geom = feat.geometry().asPolyline()
        start_point = QgsPoint(geom[0])
        end_point = QgsPoint(geom[1])
        front_angle = start_point.azimuth(end_point)
        back_angle = front_angle + 180
    
    log(f"Runway azimuth: {front_angle:.2f}°")
    
    # Calculate limiting points for areas
    point_list = {}
    
    # Calculation of Omnidirectional SID points
    width_area_1 = 150 + distance_area1 * tan(radians(15))
    width_area_2 = width_area_1 + distance_area2 * tan(radians(30))
    
    log(f"Width Area 1: {width_area_1:.2f}m, Width Area 2: {width_area_2:.2f}m")
    
    calculate_points('point_0_center', end_point, cwy_distance_m, front_angle, elevation_area0, point_list)
    calculate_points('point_0_left', point_list['point_0_center'], 150, front_angle - 90, elevation_area0, point_list)
    calculate_points('point_0_right', point_list['point_0_center'], 150, front_angle + 90, elevation_area0, point_list)
    calculate_points('point_1_center', point_list['point_0_center'], distance_area1, front_angle, elevation_area1, point_list)
    calculate_points('point_1_left', point_list['point_1_center'], width_area_1, front_angle - 90, elevation_area1, point_list)
    calculate_points('point_1_right', point_list['point_1_center'], width_area_1, front_angle + 90, elevation_area1, point_list)
    calculate_points('point_2_center', point_list['point_1_center'], distance_area2, front_angle, elevation_area2, point_list)
    calculate_points('point_2_left', point_list['point_2_center'], width_area_2, front_angle - 90, elevation_area2, point_list)
    calculate_points('point_2_right', point_list['point_2_center'], width_area_2, front_angle + 90, elevation_area2, point_list)
    calculate_points('point_600m_takeoff_center', start_point, 600, front_angle, elevation_area0, point_list)
    calculate_points('point_600m_takeoff_left', point_list['point_600m_takeoff_center'], 150, front_angle - 90, elevation_area0, point_list)
    calculate_points('point_600m_takeoff_right', point_list['point_600m_takeoff_center'], 150, front_angle + 90, elevation_area0, point_list)
    
    # Create construction points layer
    x_layer = QgsVectorLayer("PointZ?crs=" + map_srid, "Omnidirectional SID construction points_" + str(pdg), "memory")
    myField = QgsField('id', QVariant.String)
    x_layer.dataProvider().addAttributes([myField])
    x_layer.updateFields()
    
    for point in point_list:
        pr = x_layer.dataProvider()
        seg = QgsFeature()
        seg.setGeometry(point_list[point])
        seg.setAttributes([point])
        pr.addFeatures([seg])
    
    if include_construction_points == 'YES':
        QgsProject.instance().addMapLayers([x_layer])
        log("Construction points layer added")
    
    # Create polygon layer
    v_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, "OmniSID 3D Area_PDG_" + str(pdg) + '%', "memory")
    myField = QgsField('omni_area', QVariant.String)
    v_layer.dataProvider().addAttributes([myField])
    v_layer.updateFields()
    
    surface_list = {}
    
    # Add Area 1
    add_surface('Area 1', [
        point_list['point_1_left'],
        point_list['point_0_left'],
        point_list['point_0_center'],
        point_list['point_0_right'],
        point_list['point_1_right'],
        point_list['point_1_center']
    ], v_layer, surface_list)
    
    # Add Area 2
    add_surface('Area 2', [
        point_list['point_2_left'],
        point_list['point_1_left'],
        point_list['point_1_center'],
        point_list['point_1_right'],
        point_list['point_2_right'],
        point_list['point_2_center']
    ], v_layer, surface_list)
    
    # Add Before DER area if allowed
    if allow_turns_before_der == 'YES':
        add_surface('Before DER', [
            point_list['point_0_left'],
            point_list['point_600m_takeoff_left'],
            point_list['point_600m_takeoff_center'],
            point_list['point_600m_takeoff_right'],
            point_list['point_0_right'],
            point_list['point_0_center']
        ], v_layer, surface_list)
    
    # Create Area 3 as a buffer minus other areas
    area3o = QgsGeometry.fromPointXY(QgsPointXY(point_list['point_600m_takeoff_center'])).buffer(distance_area3, 360)
    area3a = area3o.difference(surface_list['Area 2'])
    area3a = area3a.difference(surface_list['Area 1'])
    
    if allow_turns_before_der == 'YES':
        area3a = area3a.difference(surface_list['Before DER'])
    
    pr = v_layer.dataProvider()
    seg = QgsFeature()
    seg.setGeometry(area3a)
    seg.setAttributes(['Area 3'])
    pr.addFeatures([seg])
    
    v_layer.updateExtents()
    
    # Change style of layer
    v_layer.renderer().symbol().setOpacity(0.3)
    v_layer.renderer().symbol().setColor(QColor("blue"))
    iface.layerTreeView().refreshLayerSymbology(iface.activeLayer().id())
    v_layer.triggerRepaint()
    
    # Add layer to project
    QgsProject.instance().addMapLayers([v_layer])
    
    log("=" * 50)
    log("RESULTS SUMMARY:")
    log(f"Layer created: OmniSID 3D Area_PDG_{pdg}%")
    log(f"Area 1 distance: {distance_area1:.2f}m ({convert_m_nm(distance_area1):.2f}NM)")
    log(f"Area 2 distance: {distance_area2:.2f}m ({convert_m_nm(distance_area2):.2f}NM)")
    log(f"Area 3 distance: {distance_area3:.2f}m ({convert_m_nm(distance_area3):.2f}NM)")
    log("=" * 50)
    log("Omnidirectional SID calculation completed successfully!")
    
    return {
        'layer_name': f"OmniSID 3D Area_PDG_{pdg}%",
        'areas': ['Area 1', 'Area 2', 'Area 3'],
        'distance_area1': distance_area1,
        'distance_area2': distance_area2,
        'distance_area3': distance_area3,
        'width_area_1': width_area_1,
        'width_area_2': width_area_2
    }
