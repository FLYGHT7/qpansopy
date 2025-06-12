'''
LNAV Final Approach (RNP APCH)
'''
myglobals = set(globals().keys())

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsPoint, QgsPolygon, QgsLineString, Qgis
)
from PyQt5.QtCore import QVariant
from math import *

def run_final_approach(iface, routing_layer, primary_width=0.95, secondary_width=0.475):
    """LNAV Final Approach (RNP APCH)"""
    # Log must be inside function
    iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV final (RNP APCH)", level=Qgis.Info)

    # Get Projected Coordinate System for the QGIS Project 
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

    if routing_layer is None:
        iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
        raise Exception("No Routing Selected")

    # Select features
    routing_layer.selectByExpression("segment='final'")
    selection = routing_layer.selectedFeatures()

    if not selection:
        iface.messageBar().pushMessage("No 'final' segment selected", level=Qgis.Critical)
        raise Exception("No 'final' segment selected")

    for feat in selection:
        geom = feat.geometry().asPolyline()
        if len(geom) >= 2:
            start_point = QgsPoint(geom[0])
            end_point = QgsPoint(geom[1])
            azimuth = start_point.azimuth(end_point)
            back_azimuth = azimuth + 180
            length = feat.geometry().length()
        else:
            iface.messageBar().pushMessage("Invalid geometry", level=Qgis.Warning)

    pts={}
    a=0

    # FAF determination
    pts["m"+str(a)]=end_point.project(length,back_azimuth)
    a+=1

    # MAPt determination 
    pts["m"+str(a)]=end_point
    a+=1

    # Calculating point at MAPt location 
    d = (secondary_width, primary_width, -secondary_width, -primary_width) #NM
    for i in d:
        line_start = end_point.project(i*1852,azimuth-90)
        pts["m"+str(a)]=line_start
        a+=1

    # Calculating point at end of corridor
    transition_angle = 30  # degrees
    total_width = primary_width + secondary_width  # 1.425 NM total
    
    # Longitud de la zona de transición corregida
    lengthm = (total_width - primary_width) / tan(radians(transition_angle))

    # Ancho final validación
    if abs(secondary_width - (primary_width/2)) > 0.001:
        iface.messageBar().pushMessage("Warning", "Secondary width should be half of primary width", level=Qgis.Warning)
        secondary_width = primary_width/2

    for i in d:
        int = start_point.project(lengthm*1852,azimuth)
        line_start = int.project(i*1852,azimuth-90)
        pts["mm"+str(a)]=line_start
        a+=1
   
    #calculating point at FAF location
    f = (0.725,1.45,-0.725,-1.45) #NM
    for i in f:
        pts["m"+str(a)]= start_point.project(i*1852,azimuth-90)
        a+=1

    # Define areas before using them
    areas = []
    # Add points to areas (normally this would come from your calculation)
    # For example: areas.append(([pts["m0"], pts["m1"], pts["m2"], pts["m3"], pts["m0"]], "primary"))

    #Create memory layer
    v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "LNAV Final APCH Segment", "memory")
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

    iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV final (RNP APCH)", level=Qgis.Success)
    
    # Return a result
    return {
        "layer": v_layer,
        "points": pts
    }

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]