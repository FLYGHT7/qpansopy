'''
Conventional NDB Approach Areas
'''

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *
import os

def run_ndb_approach(iface, routing_layer):
    """
    Generate NDB approach areas (primary and secondary) following the pattern of PBN modules
    """
    try:
        # Get Projected Coordinate System for the QGIS Project 
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
        
        # Check if there are selected features
        selection = routing_layer.selectedFeatures()
        if not selection:
            iface.messageBar().pushMessage("No features selected", level=Qgis.Critical)
            return False
            
        for feat in selection:
            geom = feat.geometry().asPolyline()
            if len(geom) >= 2:
                start_point = QgsPoint(geom[0])
                end_point = QgsPoint(geom[1])
                azimuth = start_point.azimuth(end_point)
                length = feat.geometry().length()
            else:
                iface.messageBar().pushMessage("Invalid geometry", level=Qgis.Warning)
                continue
                
            # Template Max Length is 15 NM 
            if length/1852 > 15:
                L = 15
            else:
                L = length/1852
            
            # Calculate key points for NDB template
            pts = {}
            
            # End point of template
            end_template = start_point.project(L*1852, azimuth)
            
            # Primary area width at start: ±0.625 NM
            primary_width_start = 0.625
            pts['p1'] = start_point.project(primary_width_start*1852, azimuth-90)  # Left side start
            pts['p2'] = start_point.project(primary_width_start*1852, azimuth+90)  # Right side start
            
            # Secondary width at end: ±(L*tan(10.3°) + 1.25) NM
            secondary_width_end = L*tan(radians(10.3)) + 1.25
            pts['s3'] = end_template.project(secondary_width_end*1852, azimuth-90)  # Left secondary end
            pts['s4'] = end_template.project(secondary_width_end*1852, azimuth+90)  # Right secondary end
            
            # Secondary width at start: ±1.25 NM
            secondary_width_start = 1.25
            pts['s1'] = start_point.project(secondary_width_start*1852, azimuth-90)  # Left secondary start
            pts['s2'] = start_point.project(secondary_width_start*1852, azimuth+90)  # Right secondary start

            # Primary area width at end: requires to calculate half of secondary
            secondary_end_line = QgsGeometry.fromPolylineXY([QgsPointXY(end_template), QgsPointXY(pts['s4'])])
            primary_width_end = (secondary_end_line.length()/1852)*0.5
            pts['p3'] = end_template.project(primary_width_end*1852, azimuth-90)  # Left side end
            pts['p4'] = end_template.project(primary_width_end*1852, azimuth+90)  # Right side end
            
            # Create memory layer for polygons
            v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "NDB Approach Areas", "memory")
            myField = QgsField('Symbol', QVariant.String)
            v_layer.dataProvider().addAttributes([myField])
            v_layer.updateFields()
            
            # Define areas as polygons
            # Primary area (central trapezoid)
            primary_area = ([pts['p1'], pts['p2'], pts['p4'], pts['p3']], 'Primary Area')
            
            # Secondary areas (left and right trapezoids)
            secondary_area_left = ([pts['s1'], pts['p1'], pts['p3'], pts['s3']], 'Secondary Area')
            secondary_area_right = ([pts['p2'], pts['s2'], pts['s4'], pts['p4']], 'Secondary Area')
            
            areas = (primary_area, secondary_area_left, secondary_area_right)
            
            # Create polygon features
            pr = v_layer.dataProvider()
            for area in areas:
                seg = QgsFeature()
                seg.setGeometry(QgsPolygon(QgsLineString(area[0]), rings=[]))
                seg.setAttributes([area[1]])
                pr.addFeatures([seg])
            
            v_layer.updateExtents()
            QgsProject.instance().addMapLayers([v_layer])
            
            # Apply style
            style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'primary_secondary_areas.qml')
            if os.path.exists(style_path):
                v_layer.loadNamedStyle(style_path)
            
            # Zoom to layer
            v_layer.selectAll()
            canvas = iface.mapCanvas()
            canvas.zoomToSelected(v_layer)
            v_layer.removeSelection()
            
            # Set appropriate scale
            sc = canvas.scale()
            if sc < 200000:
                sc = 200000
            canvas.zoomScale(sc)
            
            iface.messageBar().pushMessage("QPANSOPY:", "NDB Approach Areas created successfully", level=Qgis.Success)
            
        return True
        
    except Exception as e:
        iface.messageBar().pushMessage("Error creating NDB areas", str(e), level=Qgis.Critical)
        return False
