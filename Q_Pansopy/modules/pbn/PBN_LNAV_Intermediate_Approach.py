# -*- coding: utf-8 -*-
"""
PBN LNAV Intermediate Approach (RNP APCH) Generator
"""
from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from qgis.core import Qgis
from qgis.utils import iface
from math import *
import os

def run_intermediate_approach(iface_param, routing_layer, export_kml=False, output_dir=None):
    """
    Run LNAV Intermediate Approach calculation
    
    :param iface_param: QGIS interface
    :param routing_layer: Routing layer 
    :param export_kml: Whether to export KML (not implemented)
    :param output_dir: Output directory (not implemented)
    :return: Result dictionary or None
    """
    try:
        # Use the passed iface parameter
        iface = iface_param
        
        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Intermediate Approach (RNP APCH)", level=Qgis.Info)

        # Get Projected Coordinate System for the QGIS Project 
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        # Use the provided routing layer instead of searching
        if routing_layer is None:
            # Fallback: search for routing layer
            for layer in QgsProject.instance().mapLayers().values():
                if "routing" in layer.name().lower():
                    routing_layer = layer
                    break

        if routing_layer is None:
            iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
            return None

        # Use only the user's current selection - do not auto-select
        selected_features = routing_layer.selectedFeatures()

        if not selected_features:
            iface.messageBar().pushMessage("Please select at least one segment in the routing layer", level=Qgis.Critical)
            return None

        # Find intermediate segment in the user's selection
        intermediate_features = [feat for feat in selected_features if feat.attribute('segment') == 'intermediate']
        if not intermediate_features:
            iface.messageBar().pushMessage("No 'intermediate' segment found in your selection", level=Qgis.Critical)
            return None

        # Process the user's selected features - use the first valid intermediate segment found
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
