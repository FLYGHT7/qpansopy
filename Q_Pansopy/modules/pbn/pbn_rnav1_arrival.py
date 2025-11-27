# -*- coding: utf-8 -*-
"""
PBN RNAV 1 Arrival Segment Generator

This module implements Performance-Based Navigation (PBN) RNAV 1 Arrival
procedures according to ICAO Doc 9613 (PBN Manual) standards.

The module generates protection areas for RNAV 1 arrival segments
with less than 30 NM from the navigation aid.

Key Features:
- Arrival segment area calculations for RNAV 1/2
- Primary and secondary area polygon creation
- Corridor width: 2.5 NM total (1.25 NM each side for primary)
- Secondary areas: Additional 1.25 NM each side
- ICAO-compliant geometric calculations

Author: QPANSOPY Development Team
Date: 2025
Version: 1.0
"""

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsField,
    QgsPoint, QgsPolygon, QgsLineString, Qgis
)
from qgis.PyQt.QtCore import QVariant
import os
import math


def run_rnav1_arrival(iface, routing_layer, params=None):
    """
    Execute PBN RNAV 1 Arrival area calculation and protection surface generation.
    
    This function processes the arrival segment of an RNAV 1 procedure,
    calculating primary and secondary protection areas based on ICAO standards.
    
    Args:
        iface (QgsInterface): QGIS interface instance
        routing_layer (QgsVectorLayer): Vector layer containing routing segments
        params (dict, optional): Additional parameters:
            - export_kml (bool): Enable KML export
            - output_dir (str): Directory for output files
    
    Returns:
        dict or None: Dictionary with generated layer or None if failed
    """
    if params is None:
        params = {}
    
    export_kml = params.get('export_kml', False)
    output_dir = params.get('output_dir', None)
    
    try:
        iface.messageBar().pushMessage(
            "QPANSOPY:", 
            "Executing RNAV 1 Arrival Segment", 
            level=Qgis.Info
        )

        # Get Projected Coordinate System
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        if routing_layer is None:
            iface.messageBar().pushMessage(
                "Error", 
                "No routing layer provided", 
                level=Qgis.Critical
            )
            return None

        # Get user's current selection
        selected_features = routing_layer.selectedFeatures()

        if not selected_features:
            iface.messageBar().pushMessage(
                "Error", 
                "Please select at least one segment in the routing layer", 
                level=Qgis.Critical
            )
            return None

        # Try to find arrival segment, but don't fail if attribute doesn't exist
        arrival_features = []
        try:
            arrival_features = [
                feat for feat in selected_features 
                if feat.attribute('segment') == 'arrival'
            ]
        except:
            pass  # Attribute doesn't exist, use all selected
        
        if not arrival_features:
            # Use all selected features if no 'arrival' attribute found
            arrival_features = selected_features

        # Process the first valid feature
        start_point = None
        end_point = None
        azimuth = None
        length = None
        
        for feat in arrival_features:
            try:
                geom = feat.geometry().asPolyline()
                if geom and len(geom) >= 2:
                    # For arrival: end point is the destination (e.g., airport)
                    start_point = QgsPoint(geom[-1])
                    end_point = QgsPoint(geom[0])
                    azimuth = start_point.azimuth(end_point) + 180
                    length = feat.geometry().length()
                    break
            except Exception:
                continue
        
        if start_point is None:
            iface.messageBar().pushMessage(
                "Error", 
                "No valid geometry found in selected segments", 
                level=Qgis.Critical
            )
            return None

        # Calculate protection area points
        pts = {}
        a = 0

        # Calculate end of segment point
        bearing = azimuth
        angle = 90 - bearing
        angle_rad = math.radians(angle)
        dist_x = length * math.cos(angle_rad)
        dist_y = length * math.sin(angle_rad)
        
        pts["m" + str(a)] = QgsPoint(end_point.x() + dist_x, end_point.y() + dist_y)
        a += 1

        pts["m" + str(a)] = QgsPoint(end_point.x(), end_point.y())
        a += 1

        # Corridor widths (NM)
        # Primary: ±1.25 NM, Secondary: additional ±1.25 NM (total ±2.5 NM)
        distances = (1.25, 2.5, -1.25, -2.5)

        # Calculate bottom points (at start_point)
        for d in distances:
            dist_nm = d * 1852  # Convert NM to meters
            bearing_perp = azimuth + 90
            angle_perp = 90 - bearing_perp
            angle_perp_rad = math.radians(angle_perp)
            dx = dist_nm * math.cos(angle_perp_rad)
            dy = dist_nm * math.sin(angle_perp_rad)
            pts["m" + str(a)] = QgsPoint(start_point.x() + dx, start_point.y() + dy)
            a += 1

        # Calculate top points (at end_point)
        for d in distances:
            dist_nm = d * 1852
            bearing_perp = azimuth + 90
            angle_perp = 90 - bearing_perp
            angle_perp_rad = math.radians(angle_perp)
            dx = dist_nm * math.cos(angle_perp_rad)
            dy = dist_nm * math.sin(angle_perp_rad)
            pts["m" + str(a)] = QgsPoint(end_point.x() + dx, end_point.y() + dy)
            a += 1

        # Create memory layer
        v_layer = QgsVectorLayer(
            f"PolygonZ?crs={map_srid}", 
            "PBN RNAV 1/2 Arrival", 
            "memory"
        )
        v_layer.dataProvider().addAttributes([QgsField('Symbol', QVariant.String)])
        v_layer.updateFields()

        # Define areas
        # Primary Area
        primary_coords = [
            pts["m2"], pts["m0"], pts["m4"], 
            pts["m8"], pts["m1"], pts["m6"]
        ]
        
        # Secondary Area Left
        secondary_left_coords = [
            pts["m3"], pts["m2"], pts["m6"], pts["m7"]
        ]
        
        # Secondary Area Right
        secondary_right_coords = [
            pts["m4"], pts["m5"], pts["m9"], pts["m8"]
        ]

        areas = [
            (primary_coords, 'Primary Area'),
            (secondary_left_coords, 'Secondary Area'),
            (secondary_right_coords, 'Secondary Area')
        ]

        # Create features
        pr = v_layer.dataProvider()
        features = []
        
        for coords, symbol in areas:
            seg = QgsFeature()
            seg.setGeometry(QgsPolygon(QgsLineString(coords), rings=[]))
            seg.setAttributes([symbol])
            features.append(seg)

        pr.addFeatures(features)
        v_layer.updateExtents()
        QgsProject.instance().addMapLayers([v_layer])

        # Apply style
        style_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 'styles', 
            'primary_secondary_areas.qml'
        )
        if os.path.exists(style_path):
            v_layer.loadNamedStyle(style_path)
            v_layer.triggerRepaint()

        # Zoom to layer
        v_layer.selectAll()
        canvas = iface.mapCanvas()
        canvas.zoomToSelected(v_layer)
        v_layer.removeSelection()

        iface.messageBar().pushMessage(
            "QPANSOPY:", 
            "Finished RNAV 1/2 Arrival (<30NM)", 
            level=Qgis.Success
        )

        # KML Export if requested
        result = {"arrival_layer": v_layer}
        
        if export_kml and output_dir:
            try:
                from ..utilities.kml_export import export_layer_to_kml
                kml_path = os.path.join(output_dir, "rnav1_arrival.kml")
                export_layer_to_kml(v_layer, kml_path)
                result['kml_path'] = kml_path
            except ImportError:
                pass  # KML export not available

        return result

    except Exception as e:
        iface.messageBar().pushMessage(
            "Error", 
            f"Error in RNAV 1 Arrival: {str(e)}", 
            level=Qgis.Critical
        )
        return None
