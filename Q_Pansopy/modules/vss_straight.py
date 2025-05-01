# -*- coding: utf-8 -*-
"""
/***************************************************************************
 VSS Straight In NPA Module
                              -------------------
        begin                : 2023-04-29
        copyright            : (C) 2023 by Your Name
        email                : your.email@example.com
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

import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPoint, 
    QgsLineString, QgsPolygon, QgsField, QgsCoordinateReferenceSystem,
    QgsVectorFileWriter, Qgis
)
from qgis.PyQt.QtCore import QVariant
from PyQt5.QtGui import QColor
from math import *

def calculate_vss_straight(iface, point_layer, runway_layer, params):
    """
    Calculate VSS Straight In NPA
    
    :param iface: QGIS interface
    :param point_layer: Threshold point layer
    :param runway_layer: Runway line layer
    :param params: Dictionary of parameters
    :return: Dictionary with results
    """
    
    # Extract parameters
    rwy_width = params.get('rwy_width', 45.0)
    thr_elev = params.get('thr_elev', 22.0)
    strip_width = params.get('strip_width', 280.0)
    och = params.get('OCH', 140.21)
    rdh = params.get('RDH', 15.0)
    vpa = params.get('VPA', 3.0)
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', None)
    output_vss = params.get('output_vss', None)
    output_ocs = params.get('output_ocs', None)
    
    # Get the map CRS
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Get the threshold point
    if point_layer.selectedFeatureCount() > 0:
        for feat in point_layer.selectedFeatures():
            thr_geom = feat.geometry().asPoint()
            break
    else:
        # If no feature is selected, use the first feature
        for feat in point_layer.getFeatures():
            thr_geom = feat.geometry().asPoint()
            break
    
    # Get the runway line
    if runway_layer.selectedFeatureCount() > 0:
        for feat in runway_layer.selectedFeatures():
            geom = feat.geometry().asPolyline()
            start_point = QgsPoint(geom[0])
            end_point = QgsPoint(geom[1])
            angle0 = start_point.azimuth(end_point)
            break
    else:
        # If no feature is selected, use the first feature
        for feat in runway_layer.getFeatures():
            geom = feat.geometry().asPolyline()
            start_point = QgsPoint(geom[0])
            end_point = QgsPoint(geom[1])
            angle0 = start_point.azimuth(end_point)
            break
    
    # Set azimuth and back azimuth
    azimuth = angle0
    back_azimuth = azimuth - 180
    
    # Function to convert from PointXY and add Z value
    def pz(point, z):
        cPoint = QgsPoint(point)
        cPoint.addZValue()
        cPoint.setZ(z)
        return cPoint
    
    # Calculate VSS parameters
    vss_length = 1.12 * (och - rdh) / tan(radians(vpa))
    vss_inner_width = rwy_width
    vss_outer_width = vss_inner_width + 2 * vss_length * 0.15
    
    # Calculate VSS points
    vss_center_start = thr_geom
    vss_center_end = vss_center_start.project(vss_length, azimuth)
    
    vss_left_start = vss_center_start.project(vss_inner_width/2, azimuth-90)
    vss_right_start = vss_center_start.project(vss_inner_width/2, azimuth+90)
    
    vss_left_end = vss_center_end.project(vss_outer_width/2, azimuth-90)
    vss_right_end = vss_center_end.project(vss_outer_width/2, azimuth+90)
    
    # Calculate OCS parameters
    ocs_inner_width = strip_width
    ocs_outer_width = ocs_inner_width + 2 * vss_length * 0.15
    
    # Calculate OCS points
    ocs_left_start = vss_center_start.project(ocs_inner_width/2, azimuth-90)
    ocs_right_start = vss_center_start.project(ocs_inner_width/2, azimuth+90)
    
    ocs_left_end = vss_center_end.project(ocs_outer_width/2, azimuth-90)
    ocs_right_end = vss_center_end.project(ocs_outer_width/2, azimuth+90)
    
    # Create VSS layer
    vss_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "VSS_Straight_In_NPA", "memory")
    vss_pr = vss_layer.dataProvider()
    vss_pr.addAttributes([QgsField('name', QVariant.String)])
    vss_layer.updateFields()
    
    # Add VSS feature
    vss_feat = QgsFeature()
    vss_exterior_ring = [
        pz(vss_left_start, thr_elev),
        pz(vss_left_end, thr_elev + och),
        pz(vss_right_end, thr_elev + och),
        pz(vss_right_start, thr_elev)
    ]
    vss_feat.setGeometry(QgsPolygon(QgsLineString(vss_exterior_ring), rings=[]))
    vss_feat.setAttributes(['VSS'])
    vss_pr.addFeatures([vss_feat])
    
    # Create OCS layer
    ocs_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "OCS_Straight_In_NPA", "memory")
    ocs_pr = ocs_layer.dataProvider()
    ocs_pr.addAttributes([QgsField('name', QVariant.String)])
    ocs_layer.updateFields()
    
    # Add OCS feature
    ocs_feat = QgsFeature()
    ocs_exterior_ring = [
        pz(ocs_left_start, thr_elev),
        pz(ocs_left_end, thr_elev + och),
        pz(vss_left_end, thr_elev + och),
        pz(vss_left_start, thr_elev),
        pz(vss_right_start, thr_elev),
        pz(vss_right_end, thr_elev + och),
        pz(ocs_right_end, thr_elev + och),
        pz(ocs_right_start, thr_elev)
    ]
    ocs_feat.setGeometry(QgsPolygon(QgsLineString(ocs_exterior_ring), rings=[]))
    ocs_feat.setAttributes(['OCS'])
    ocs_pr.addFeatures([ocs_feat])
    
    # Update layers and add to project
    vss_layer.updateExtents()
    ocs_layer.updateExtents()
    QgsProject.instance().addMapLayers([vss_layer, ocs_layer])
    
    # Export to KML if requested
    vss_path = None
    ocs_path = None
    if export_kml and output_dir:
        # Define file paths
        vss_path = os.path.join(output_dir, 'vss_straight_layer.kml')
        ocs_path = os.path.join(output_dir, 'ocs_straight_layer.kml')
        
        # Export to KML
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        vss_error = QgsVectorFileWriter.writeAsVectorFormat(
            vss_layer,
            vss_path,
            'utf-8',
            crs,
            'KML',
            layerOptions=['MODE=2']  # Ensure Z values are included
        )
        
        ocs_error = QgsVectorFileWriter.writeAsVectorFormat(
            ocs_layer,
            ocs_path,
            'utf-8',
            crs,
            'KML',
            layerOptions=['MODE=2']  # Ensure Z values are included
        )
        
        # Check for errors
        if vss_error[0] != QgsVectorFileWriter.NoError:
            iface.messageBar().pushMessage(
                "Error", 
                f"Error exporting VSS layer: {vss_error[1]}", 
                level=Qgis.Critical
            )
        
        if ocs_error[0] != QgsVectorFileWriter.NoError:
            iface.messageBar().pushMessage(
                "Error", 
                f"Error exporting OCS layer: {ocs_error[1]}", 
                level=Qgis.Critical
            )
    
    # Return results
    return {
        'vss_layer': vss_layer,
        'ocs_layer': ocs_layer,
        'vss_path': vss_path,
        'ocs_path': ocs_path
    }