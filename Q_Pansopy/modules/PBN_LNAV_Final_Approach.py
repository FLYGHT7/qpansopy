'''
LNAV Final Approach (RNP APCH)
'''
from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

def run_final_approach(iface, routing_layer, primary_width=0.95, secondary_width=0.475):
    '''
    LNAV Final Approach (RNP APCH)
    Args:
        iface: QGIS interface
        routing_layer: The layer containing the routing segments
        primary_width: Width of primary area in NM (default 0.95)
        secondary_width: Width of secondary area in NM (default 0.475)
    '''
    iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV final (RNP APCH)", level=Qgis.Info)

    # Get Projected Coordinate System for the QGIS Project 
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

    if routing_layer is None:
        iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
        raise Exception("No Routing Selected")
    
    # Solo trabajar con elementos actualmente seleccionados
    selection = routing_layer.selectedFeatures()
    found_final = False

    if not selection:
        iface.messageBar().pushMessage("No segments selected", level=Qgis.Critical)
        raise Exception("No segments selected")

    # Buscar entre los seleccionados, si hay un segmento 'final'
    for feat in selection:
        if feat['segment'] == 'final':  # Verificar si hay un segmento de tipo 'final'
            found_final = True
            geom = feat.geometry().asPolyline()
            if len(geom) >= 2:
                start_point = QgsPoint(geom[0])
                end_point = QgsPoint(geom[1])
                azimuth = start_point.azimuth(end_point)
                back_azimuth = azimuth + 180
                length = feat.geometry().length()
                # Usar este segmento para el cálculo
                break
            else:
                iface.messageBar().pushMessage("Invalid geometry", level=Qgis.Warning)
                
    if not found_final:
        iface.messageBar().pushMessage("No 'final' segment found in selection", level=Qgis.Critical)
        raise Exception("Please select a segment with segment='final'")
    
    pts={}
    a=0

    # FAF determination
    pts["m"+str(a)]=end_point.project(length,back_azimuth)
    a+=1

    # MAPt determination 
    pts["m"+str(a)]=end_point
    a+=1

    # Calculating point at MAPt location 
    d = (0.475,0.95,-0.475,-0.95) #NM
    for i in d:
        line_start = end_point.project(i*1852,azimuth-90)
        pts["m"+str(a)]=line_start
        a+=1

    # Calculating point at end of corridor
    lengthm = (1.45-0.95)/tan(radians(30)) #NM
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

    #Create memory layer
    v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "LNAV Final APCH Segment", "memory")
    myField = QgsField('Symbol', QVariant.String)
    v_layer.dataProvider().addAttributes([myField])
    v_layer.updateFields()

    # Area Definition - exactamente como el original
    primary_area = ([pts["m2"],pts["m1"],pts["m4"],pts["mm8"],pts["m12"],pts["m10"],pts["mm6"]],'Primary Area')
    secondary_area_left = ([pts["m3"],pts["m2"],pts["mm6"],pts["m10"],pts["m11"],pts["mm7"]],'Secondary Area')
    secondary_area_right = ([pts["m5"],pts["m4"],pts["mm8"],pts["m12"],pts["m13"],pts["mm9"]],'Secondary Area')

    areas = (primary_area, secondary_area_left,secondary_area_right)

    # Creating areas - exactamente como el original
    for area in areas:
        pr = v_layer.dataProvider()
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(area[0]), rings=[]))
        seg.setAttributes([area[1]])
        pr.addFeatures([seg])

    v_layer.updateExtents()
    QgsProject.instance().addMapLayers([v_layer])

    iface.messageBar().pushMessage("QPANSOPY:", "Finished LNAV final (RNP APCH)", level=Qgis.Success)
    
    return v_layer