'''
CONV Initial Approach Segment Straight
'''

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *
import os

def run_conv_initial_approach(iface, routing_layer):
    """
    Generate CONV Initial Approach areas (primary and secondary) following the pattern of PBN modules
    """
    try:
        # Get Projected Coordinate System for the QGIS Project 
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
        
        # Verify routing layer is provided and has correct name
        if not routing_layer:
            iface.messageBar().pushMessage("No routing layer provided", level=Qgis.Critical)
            return False
            
        # Check if the layer name contains "routing" (like original script)
        if "routing" not in routing_layer.name().lower():
            iface.messageBar().pushMessage(f"Selected layer '{routing_layer.name()}' does not appear to be a routing layer", level=Qgis.Warning)
        
        # Check if there are selected features
        selection = routing_layer.selectedFeatures()
        if not selection:
            iface.messageBar().pushMessage("No features selected in routing layer", level=Qgis.Critical)
            return False
            
        iface.messageBar().pushMessage("QPANSOPY:", "Executing CONV Initial Approach Segment Straight", level=Qgis.Info)
        
        features_processed = 0
        for feat in selection:
            geom = feat.geometry().asPolyline()
            if len(geom) < 2:
                iface.messageBar().pushMessage("Invalid geometry - need at least 2 points", level=Qgis.Warning)
                continue
                
            # Note: Using the original logic with start_point as geom[-1] and end_point as geom[0]
            start_point = QgsPoint(geom[-1])
            end_point = QgsPoint(geom[0])
            angle0 = start_point.azimuth(end_point) + 180
            length0 = feat.geometry().length()
            
            # Debug information
            iface.messageBar().pushMessage("Debug:", f"Length: {length0/1852:.2f} NM, Azimuth: {angle0:.1f}°", level=Qgis.Info)
                
            azimuth = angle0
            
            pts = {}
            a = 0

            # routine 1 FAF determination
            bearing = azimuth
            angle = 90 - bearing
            bearing_rad = radians(bearing)
            angle_rad = radians(angle)
            dist_x, dist_y = (length0 * cos(angle_rad), length0 * sin(angle_rad))
            
            pts["m"+str(a)] = QgsPoint(end_point.x() + dist_x, end_point.y() + dist_y)
            a += 1
            
            pts["m"+str(a)] = QgsPoint(end_point.x(), end_point.y())
            a += 1

            # calculating bottom points
            d = (2.5, 5, -2.5, -5)  # NM

            for i in d:
                TNA_dist = i * 1852
                bearing = azimuth + 90
                angle = 90 - bearing
                bearing_rad = radians(bearing)
                angle_rad = radians(angle)
                dist_x, dist_y = (TNA_dist * cos(angle_rad), TNA_dist * sin(angle_rad))
                bx1, by2 = (start_point.x() + dist_x, start_point.y() + dist_y)

                line_start = QgsPoint(bx1, by2)
                pts["m"+str(a)] = line_start
                a += 1
                
            # calculating top points
            d = (2.5, 5, -2.5, -5)  # NM

            for i in d:
                TNA_dist = i * 1852
                bearing = azimuth + 90
                angle = 90 - bearing
                bearing_rad = radians(bearing)
                angle_rad = radians(angle)
                dist_x, dist_y = (TNA_dist * cos(angle_rad), TNA_dist * sin(angle_rad))
                bx1, by2 = (end_point.x() + dist_x, end_point.y() + dist_y)

                line_start = QgsPoint(bx1, by2)
                pts["m"+str(a)] = line_start
                a += 1

            # Debug: Check if we have all required points
            required_points = ["m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9"]
            missing_points = [p for p in required_points if p not in pts]
            if missing_points:
                iface.messageBar().pushMessage("Error:", f"Missing points: {missing_points}", level=Qgis.Critical)
                return False

            # Create memory layer
            v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "CONV Initial Approach Areas", "memory")
            myField = QgsField('Symbol', QVariant.String)
            v_layer.dataProvider().addAttributes([myField])
            v_layer.updateFields()

            # Define areas as polygons exactly as in the original code
            # Primary Area
            primary_area = ([pts["m2"], pts["m0"], pts["m4"], pts["m8"], pts["m1"], pts["m6"]], 'Primary Area')
            
            # Secondary Area Left
            secondary_area_left = ([pts["m3"], pts["m2"], pts["m6"], pts["m7"]], 'Secondary Area')
            
            # Secondary Area Right
            secondary_area_right = ([pts["m4"], pts["m5"], pts["m9"], pts["m8"]], 'Secondary Area')
            
            areas = (primary_area, secondary_area_left, secondary_area_right)

            # Create polygon features
            pr = v_layer.dataProvider()
            features_created = 0
            for area in areas:
                try:
                    seg = QgsFeature()
                    seg.setGeometry(QgsPolygon(QgsLineString(area[0]), rings=[]))
                    seg.setAttributes([area[1]])
                    pr.addFeatures([seg])
                    features_created += 1
                except Exception as area_error:
                    iface.messageBar().pushMessage("Error creating area:", str(area_error), level=Qgis.Warning)

            v_layer.updateExtents()
            QgsProject.instance().addMapLayers([v_layer])

            # Apply style
            style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'primary_secondary_areas.qml')
            if os.path.exists(style_path):
                v_layer.loadNamedStyle(style_path)
            else:
                iface.messageBar().pushMessage("Warning:", f"Style file not found at {style_path}", level=Qgis.Warning)

            # Zoom to layer
            v_layer.selectAll()
            canvas = iface.mapCanvas()
            canvas.zoomToSelected(v_layer)
            v_layer.removeSelection()

            iface.messageBar().pushMessage("QPANSOPY:", f"Finished CONV Initial Approach Segment - {features_created} areas created for {features_processed} features", level=Qgis.Success)
            features_processed += 1
            
        return True
        
    except Exception as e:
        iface.messageBar().pushMessage("Error creating CONV Initial Approach areas", str(e), level=Qgis.Critical)
        import traceback
        iface.messageBar().pushMessage("Traceback:", traceback.format_exc(), level=Qgis.Critical)
        return False
