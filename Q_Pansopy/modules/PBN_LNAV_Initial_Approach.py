from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsPoint, QgsPolygon, QgsLineString, Qgis
)
from PyQt5.QtCore import QVariant
from math import *

def run_initial_approach(iface, routing_layer, primary_width=2.5, secondary_width=1.25):
    """
    LNAV Initial Approach (RNP APCH)
    Args:
        iface: QGIS interface
        routing_layer: The layer containing the routing segments
        primary_width: Width of primary area in NM (default 2.5)
        secondary_width: Width of secondary area in NM (default 1.25)
    """
    # No globals inside function
    iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Initial Approach (RNP APCH)", level=Qgis.Info)

    # Get Projected Coordinate System for the QGIS Project 
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

    if routing_layer is None:
        iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
        raise Exception("No Routing Selected")

    # Select features
    selection = routing_layer.selectedFeatures()
    found_initial = False

    if not selection:
        iface.messageBar().pushMessage("No 'initial' segment selected", level=Qgis.Critical)
        raise Exception("No 'initial' segment selected")

    for feat in selection:
        if feat['segment'] != 'initial':
            continue  # skip non-initial segments

        found_initial = True
        
        geom = feat.geometry().asPolyline()
        if len(geom) >= 2:
            start_point = QgsPoint(geom[0])
            end_point = QgsPoint(geom[1])
            azimuth = start_point.azimuth(end_point)
            back_azimuth = azimuth + 180
            length = feat.geometry().length()
        else:
            iface.messageBar().pushMessage("Invalid geometry", level=Qgis.Warning)
    if not found_initial:
        iface.messageBar().pushMessage("No feature with segment = 'initial'", level=Qgis.Critical)
        raise Exception("Missing required 'initial' segment")

    pts={}
    a=0

    # IAF determination
    pts["m"+str(a)]=end_point.project(length,back_azimuth)
    a+=1

    # IF determination 
    pts["m"+str(a)]=end_point
    a+=1

    # Calculating point at IF location 
    d = (secondary_width, primary_width, -secondary_width, -primary_width) #NM
    for i in d:
        line_start = end_point.project(i*1852,azimuth-90)
        pts["m"+str(a)]=line_start
        a+=1
        
    # Calculating point at IAF location 
    d = (secondary_width, primary_width, -secondary_width, -primary_width) #NM
    for i in d:
        line_start = start_point.project(i*1852,azimuth-90)
        pts["m"+str(a)]=line_start
        a+=1

    # Define areas with the calculated points
    areas = []
    
    # Primary Area - Connect the points in a logical order
    # This needs to be updated based on the actual points generated
    if len(pts) >= 8:  # Make sure we have enough points
        primary_points = [
            pts["m1"],  # IF
            pts["m3"],  # Right edge of IF
            pts["m7"],  # Right edge of IAF
            pts["m0"],  # IAF
            pts["m5"],  # Left edge of IAF
            pts["m2"],  # Left edge of IF
            pts["m1"]   # Close the polygon
        ]
        areas.append((primary_points, "primary"))
    
    # Secondary Area - similar approach with other points
    # ...add code for secondary areas if needed...
    
    # Create memory layer
    v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "Initial APCH Segment", "memory")
    myField = QgsField('Symbol', QVariant.String)
    v_layer.dataProvider().addAttributes([myField])
    v_layer.updateFields()

    # Create areas
    for area in areas:
        pr = v_layer.dataProvider()
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(area[0]), rings=[]))
        seg.setAttributes([area[1]])
        pr.addFeatures([seg])

    v_layer.updateExtents()
    QgsProject.instance().addMapLayers([v_layer])

    iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV Initial Approach (RNP APCH)", level=Qgis.Success)
    
    # Return a result instead of using globals
    return {
        "layer": v_layer,
        "points": pts,
        "areas": areas
    }