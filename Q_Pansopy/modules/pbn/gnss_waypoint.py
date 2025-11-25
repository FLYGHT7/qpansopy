# -*- coding: utf-8 -*-
"""
GNSS Waypoint Tolerance Generator

Creates GNSS waypoint tolerance areas based on XTT (Cross Track Tolerance)
and ATT (Along Track Tolerance) values.
"""

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPointXY, QgsField, QgsRectangle, QgsPoint, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.utils import iface
from math import radians, cos, sin
import os


def run_gnss_waypoint(iface_param, waypoint_layer, routing_layer, params=None):
    """
    Generate GNSS waypoint tolerance area.
    
    The tolerance area is a rectangle centered on the waypoint with:
    - Width = 2 * XTT (Cross Track Tolerance)
    - Height = 2 * ATT (Along Track Tolerance), where ATT = 0.8 * XTT
    
    The rectangle is rotated to align with the flight direction from the routing layer.
    
    Parameters:
    - iface_param: QGIS interface
    - waypoint_layer: Point layer with the waypoint
    - routing_layer: Line layer with the routing (for azimuth calculation)
    - params: Dictionary with optional parameters:
        - xtt: Cross Track Tolerance in NM (default: 1.0)
    
    Returns:
    - Dictionary with results or None on error
    """
    try:
        params = params or {}
        
        # Get XTT value (default 1.0 NM)
        xtt = float(params.get('xtt', 1.0))
        att = 0.8 * xtt  # ATT is always 0.8 * XTT
        
        # Get map CRS
        map_srid = iface_param.mapCanvas().mapSettings().destinationCrs().authid()
        
        # Validate waypoint layer
        if not waypoint_layer:
            iface_param.messageBar().pushMessage("Error", "No waypoint layer provided", level=Qgis.Critical)
            return None
        
        # Get waypoint - either selected or single feature
        selection = waypoint_layer.selectedFeatures()
        if len(selection) == 0:
            # Try to use single feature if only one exists
            all_features = list(waypoint_layer.getFeatures())
            if len(all_features) == 1:
                waypoint_feature = all_features[0]
            else:
                iface_param.messageBar().pushMessage("Error", "Please select a waypoint", level=Qgis.Critical)
                return None
        elif len(selection) == 1:
            waypoint_feature = selection[0]
        else:
            iface_param.messageBar().pushMessage("Error", "Please select only one waypoint", level=Qgis.Critical)
            return None
        
        # Get waypoint geometry
        waypoint_geom = waypoint_feature.geometry().asPoint()
        
        # Calculate azimuth from routing layer
        azimuth = 0  # Default north
        
        if routing_layer:
            routing_selection = routing_layer.selectedFeatures()
            if routing_selection:
                geom = routing_selection[0].geometry().asPolyline()
                if len(geom) >= 2:
                    start_point = QgsPoint(geom[-1])
                    end_point = QgsPoint(geom[0])
                    azimuth = start_point.azimuth(end_point) + 180
        
        iface_param.messageBar().pushMessage("QPANSOPY:", f"GNSS Waypoint - XTT: {xtt} NM, Azimuth: {azimuth:.1f}°", level=Qgis.Info)
        
        # Create memory layer
        v_layer = QgsVectorLayer("Polygon?crs=" + map_srid, "GNSS Waypoint Tolerance", "memory")
        
        # Add fields
        fields = [
            QgsField('XTT', QVariant.String),
            QgsField('ATT', QVariant.String),
            QgsField('XTT_m', QVariant.Double),
            QgsField('ATT_m', QVariant.Double)
        ]
        v_layer.dataProvider().addAttributes(fields)
        v_layer.updateFields()
        
        # Calculate tolerance rectangle
        # Convert NM to meters (1 NM = 1852 m)
        xtt_m = xtt * 1852
        att_m = att * 1852
        
        # Create rectangle centered on waypoint
        rect = QgsRectangle.fromCenterAndSize(
            waypoint_geom,
            2 * xtt_m,  # Width (2 * XTT)
            2 * att_m   # Height (2 * ATT)
        )
        
        # Create polygon from rectangle
        polygon = QgsGeometry.fromRect(rect)
        
        # Rotate polygon to align with flight direction
        centroid = polygon.centroid().asPoint()
        polygon.rotate(azimuth, centroid)
        
        # Create feature
        feature = QgsFeature()
        feature.setGeometry(polygon)
        feature.setAttributes([
            f"{xtt} NM",
            f"{att} NM",
            xtt_m,
            att_m
        ])
        
        # Add feature to layer
        v_layer.dataProvider().addFeatures([feature])
        v_layer.updateExtents()
        
        # Apply style
        v_layer.renderer().symbol().setOpacity(0.3)
        v_layer.renderer().symbol().setColor(QColor("blue"))
        v_layer.renderer().symbol().symbolLayer(0).setStrokeColor(QColor("darkblue"))
        v_layer.renderer().symbol().symbolLayer(0).setStrokeWidth(0.5)
        
        # Add layer to project
        QgsProject.instance().addMapLayers([v_layer])
        
        # Zoom to layer
        v_layer.selectAll()
        canvas = iface_param.mapCanvas()
        canvas.zoomToSelected(v_layer)
        v_layer.removeSelection()
        
        iface_param.messageBar().pushMessage("QPANSOPY:", "GNSS Waypoint Tolerance created successfully", level=Qgis.Success)
        
        return {
            'layer': v_layer,
            'xtt': xtt,
            'att': att,
            'azimuth': azimuth
        }
        
    except Exception as e:
        iface_param.messageBar().pushMessage("Error", f"GNSS Waypoint error: {str(e)}", level=Qgis.Critical)
        import traceback
        iface_param.messageBar().pushMessage("Traceback:", traceback.format_exc(), level=Qgis.Critical)
        return None
