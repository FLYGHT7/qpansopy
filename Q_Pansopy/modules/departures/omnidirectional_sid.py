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

import math
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPoint, QgsPolygon, QgsLineString, QgsWkbTypes, QgsField
)
from qgis.PyQt.QtCore import QVariant


def convert_m_nm(value_m):
    """Convert meters to nautical miles"""
    return value_m / 1852


def convert_ft_m(value_ft):
    """Convert feet to meters"""
    return value_ft * 0.3048


def calculate_area1_limit(der_elevation_m, pdg, TNA_ft):
    """
    Calculate the limit of Area 1 in meters.
    Area 1 ends where the surface reaches TNA.
    
    :param der_elevation_m: DER elevation in meters
    :param pdg: Procedure Design Gradient (%)
    :param TNA_ft: Turning Altitude in feet
    :return: Distance from DER to Area 1 limit in meters
    """
    TNA_m = convert_ft_m(TNA_ft)
    height_gain = TNA_m - (der_elevation_m + 5)  # 5m is the starting height at DER
    distance_m = (height_gain / pdg) * 100
    return distance_m


def calculate_area2_limit(msa_ft, TNA_ft, pdg):
    """
    Calculate the limit of Area 2 in meters.
    Area 2 extends from TNA to where surface reaches MSA.
    
    :param msa_ft: Minimum Safe Altitude in feet
    :param TNA_ft: Turning Altitude in feet
    :param pdg: Procedure Design Gradient (%)
    :return: Distance from Area 1 limit to Area 2 limit in meters
    """
    height_gain = convert_ft_m(msa_ft - TNA_ft)
    distance_m = (height_gain / pdg) * 100
    return distance_m


def calculate_area3_limit(msa_ft, TNA_ft, pdg):
    """
    Calculate the limit of Area 3 in meters.
    Area 3 continues from Area 2 with a 2.5% gradient.
    
    :param msa_ft: Minimum Safe Altitude in feet
    :param TNA_ft: Turning Altitude in feet
    :param pdg: Procedure Design Gradient (%)
    :return: Distance from Area 2 limit to Area 3 limit in meters
    """
    # Area 3 uses 2.5% gradient (standard departure gradient)
    gradient_area3 = 2.5
    height_gain = convert_ft_m(msa_ft - TNA_ft)
    distance_m = (height_gain / gradient_area3) * 100
    return distance_m


def calculate_points(start_x, start_y, start_z, distances, widths, heights, azimuth_deg, 
                     allow_turns_before_der, cwy_distance_m):
    """
    Calculate the polygon points for each area.
    
    :param start_x: Starting X coordinate (DER position)
    :param start_y: Starting Y coordinate (DER position)
    :param start_z: Starting Z coordinate (DER elevation)
    :param distances: List of distances for each area [d1, d2, d3]
    :param widths: List of widths at each distance [w0, w1, w2, w3]
    :param heights: List of heights at each distance [h0, h1, h2, h3]
    :param azimuth_deg: Runway azimuth in degrees
    :param allow_turns_before_der: Whether turns are allowed before DER ('YES'/'NO')
    :param cwy_distance_m: Clearway distance in meters
    :return: Dictionary with left and right polygon vertices for each area
    """
    azimuth_rad = math.radians(azimuth_deg)
    perpendicular_rad = azimuth_rad + math.pi / 2
    
    # Calculate start offset based on turns before DER setting
    if allow_turns_before_der == 'YES':
        start_offset = -600  # Start 600m before DER if turns allowed
    else:
        start_offset = cwy_distance_m  # Start at clearway distance from DER
    
    # Calculate cumulative distances
    cumulative_distances = [start_offset]
    running_total = start_offset
    for d in distances:
        running_total += d
        cumulative_distances.append(running_total)
    
    points = {
        'area1': {'left': [], 'right': [], 'heights': []},
        'area2': {'left': [], 'right': [], 'heights': []},
        'area3': {'left': [], 'right': [], 'heights': []}
    }
    
    # Calculate points for each position
    for i, dist in enumerate(cumulative_distances):
        # Calculate center point at this distance
        center_x = start_x + dist * math.sin(azimuth_rad)
        center_y = start_y + dist * math.cos(azimuth_rad)
        center_z = start_z + heights[i]
        
        # Calculate left and right points at this distance
        width_half = widths[i] / 2
        left_x = center_x - width_half * math.sin(perpendicular_rad)
        left_y = center_y - width_half * math.cos(perpendicular_rad)
        right_x = center_x + width_half * math.sin(perpendicular_rad)
        right_y = center_y + width_half * math.cos(perpendicular_rad)
        
        # Assign to appropriate areas
        if i <= 1:  # Start and end of Area 1
            points['area1']['left'].append((left_x, left_y, center_z))
            points['area1']['right'].append((right_x, right_y, center_z))
            points['area1']['heights'].append(center_z)
        if i >= 1 and i <= 2:  # Start and end of Area 2
            points['area2']['left'].append((left_x, left_y, center_z))
            points['area2']['right'].append((right_x, right_y, center_z))
            points['area2']['heights'].append(center_z)
        if i >= 2:  # Start and end of Area 3
            points['area3']['left'].append((left_x, left_y, center_z))
            points['area3']['right'].append((right_x, right_y, center_z))
            points['area3']['heights'].append(center_z)
    
    return points


def add_surface(layer, area_name, left_points, right_points, pdg):
    """
    Add a 3D polygon surface to the layer.
    
    :param layer: QgsVectorLayer to add feature to
    :param area_name: Name of the area (Area 1, Area 2, Area 3)
    :param left_points: List of (x, y, z) tuples for left edge
    :param right_points: List of (x, y, z) tuples for right edge
    :param pdg: Procedure Design Gradient (%)
    """
    # Create polygon ring: left points forward, right points backward
    ring_points = []
    for pt in left_points:
        ring_points.append(QgsPoint(pt[0], pt[1], pt[2]))
    for pt in reversed(right_points):
        ring_points.append(QgsPoint(pt[0], pt[1], pt[2]))
    # Close the ring
    ring_points.append(QgsPoint(left_points[0][0], left_points[0][1], left_points[0][2]))
    
    line_string = QgsLineString(ring_points)
    polygon = QgsPolygon()
    polygon.setExteriorRing(line_string)
    
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry(polygon))
    feature.setAttribute('Area', area_name)
    feature.setAttribute('PDG', f"{pdg}%")
    
    layer.dataProvider().addFeature(feature)


def run_omnidirectional_sid(iface, runway_layer, params, log_callback=None):
    """
    Run the Omnidirectional SID calculation.
    
    :param iface: QGIS interface
    :param runway_layer: Vector layer with runway line feature
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
    
    # Get CRS from runway layer
    crs = runway_layer.crs()
    
    # Get runway geometry to calculate azimuth and DER position
    features = list(runway_layer.getFeatures())
    if not features:
        log("ERROR: No features found in runway layer")
        return None
    
    runway_geom = features[0].geometry()
    if runway_geom.isMultipart():
        line = runway_geom.asMultiPolyline()[0]
    else:
        line = runway_geom.asPolyline()
    
    if len(line) < 2:
        log("ERROR: Runway line must have at least 2 points")
        return None
    
    # DER is typically at the end of the runway (second point)
    der_point = line[-1]  # Assuming DER is at the end of the line
    start_point = line[0]
    
    # Calculate runway azimuth
    dx = der_point.x() - start_point.x()
    dy = der_point.y() - start_point.y()
    azimuth_deg = math.degrees(math.atan2(dx, dy))
    if azimuth_deg < 0:
        azimuth_deg += 360
    
    log(f"DER Position: ({der_point.x():.2f}, {der_point.y():.2f})")
    log(f"Runway Azimuth: {azimuth_deg:.2f}°")
    
    # Calculate distances
    dist_area1 = calculate_area1_limit(der_elevation_m, pdg, TNA_ft)
    dist_area2 = calculate_area2_limit(msa_ft, TNA_ft, pdg)
    dist_area3 = calculate_area3_limit(msa_ft, TNA_ft, pdg)
    
    log(f"Distance to Area 1 limit: {dist_area1:.2f}m ({convert_m_nm(dist_area1):.2f}NM)")
    log(f"Distance to Area 2 limit: {dist_area2:.2f}m ({convert_m_nm(dist_area2):.2f}NM)")
    log(f"Distance to Area 3 limit: {dist_area3:.2f}m ({convert_m_nm(dist_area3):.2f}NM)")
    
    # Calculate heights at each point
    TNA_m = convert_ft_m(TNA_ft)
    MSA_m = convert_ft_m(msa_ft)
    height_at_der = 5  # Starting height at DER is 5m
    height_at_area1_end = TNA_m - der_elevation_m
    height_at_area2_end = MSA_m - der_elevation_m
    height_at_area3_end = MSA_m - der_elevation_m + (dist_area3 * 0.025)  # 2.5% gradient
    
    heights = [height_at_der, height_at_area1_end, height_at_area2_end, height_at_area3_end]
    
    # Calculate widths at each point based on 15° and 30° splay
    # Area 1: 15° splay from inner width to TNA width
    # Area 2: 30° splay continues from Area 1
    # Area 3: Same width as Area 2 end (no additional splay)
    
    if allow_turns_before_der == 'YES':
        # Inner width at DER start (300m each side = 600m total)
        width_at_start = 600
    else:
        # Inner width based on clearway
        width_at_start = 300  # Starting width at clearway
    
    # 15° splay for Area 1
    splay_15 = 2 * dist_area1 * math.tan(math.radians(15))
    width_at_area1_end = width_at_start + splay_15
    
    # 30° splay for Area 2
    splay_30 = 2 * dist_area2 * math.tan(math.radians(30))
    width_at_area2_end = width_at_area1_end + splay_30
    
    # Area 3 maintains width
    width_at_area3_end = width_at_area2_end
    
    widths = [width_at_start, width_at_area1_end, width_at_area2_end, width_at_area3_end]
    distances = [dist_area1, dist_area2, dist_area3]
    
    log(f"Widths: Start={width_at_start:.2f}m, A1 End={width_at_area1_end:.2f}m, A2 End={width_at_area2_end:.2f}m")
    
    # Calculate polygon points
    points = calculate_points(
        der_point.x(), der_point.y(), der_elevation_m,
        distances, widths, heights, azimuth_deg,
        allow_turns_before_der, cwy_distance_m
    )
    
    # Create output layer
    layer_name = f"OmniSID_3D_Area_PDG_{pdg}%"
    
    # Create 3D polygon layer
    layer = QgsVectorLayer(f"PolygonZ?crs={crs.authid()}", layer_name, "memory")
    provider = layer.dataProvider()
    
    # Add fields
    provider.addAttributes([
        QgsField("Area", QVariant.String),
        QgsField("PDG", QVariant.String)
    ])
    layer.updateFields()
    
    # Add surfaces for each area
    add_surface(layer, "Area 1", points['area1']['left'], points['area1']['right'], pdg)
    add_surface(layer, "Area 2", points['area2']['left'], points['area2']['right'], pdg)
    add_surface(layer, "Area 3", points['area3']['left'], points['area3']['right'], pdg)
    
    layer.updateExtents()
    QgsProject.instance().addMapLayer(layer)
    log(f"Created layer: {layer_name}")
    
    # Optionally add construction points
    if include_construction_points == 'YES':
        points_layer_name = f"OmniSID_Construction_Points_PDG_{pdg}%"
        points_layer = QgsVectorLayer(f"PointZ?crs={crs.authid()}", points_layer_name, "memory")
        points_provider = points_layer.dataProvider()
        
        points_provider.addAttributes([
            QgsField("Position", QVariant.String),
            QgsField("X", QVariant.Double),
            QgsField("Y", QVariant.Double),
            QgsField("Z", QVariant.Double),
            QgsField("Distance_m", QVariant.Double),
            QgsField("Width_m", QVariant.Double)
        ])
        points_layer.updateFields()
        
        # Add construction points
        point_labels = ["DER/Start", "Area1_End", "Area2_End", "Area3_End"]
        cumulative_dist = 0
        for i, label in enumerate(point_labels):
            for side, side_name in [('left', 'Left'), ('right', 'Right')]:
                area_key = 'area1' if i <= 1 else ('area2' if i == 2 else 'area3')
                area_idx = 0 if i == 0 else (1 if i <= 2 else min(i - 1, len(points[area_key][side]) - 1))
                
                if area_idx < len(points[area_key][side]):
                    pt = points[area_key][side][area_idx]
                    feat = QgsFeature(points_layer.fields())
                    feat.setGeometry(QgsGeometry(QgsPoint(pt[0], pt[1], pt[2])))
                    feat.setAttribute("Position", f"{label}_{side_name}")
                    feat.setAttribute("X", pt[0])
                    feat.setAttribute("Y", pt[1])
                    feat.setAttribute("Z", pt[2])
                    feat.setAttribute("Distance_m", cumulative_dist)
                    feat.setAttribute("Width_m", widths[i])
                    points_provider.addFeature(feat)
            
            if i < len(distances):
                cumulative_dist += distances[i]
        
        points_layer.updateExtents()
        QgsProject.instance().addMapLayer(points_layer)
        log(f"Created construction points layer: {points_layer_name}")
    
    log("Omnidirectional SID calculation completed successfully!")
    
    return {
        'layer_name': layer_name,
        'areas': ['Area 1', 'Area 2', 'Area 3'],
        'distances': distances,
        'widths': widths,
        'heights': heights
    }
