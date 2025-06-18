'''
Conventional NDB template
'''

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

for layer in QgsProject.instance().mapLayers().values():
    if "navaid_track" in layer.name():
        layer = layer
        selection = layer.selectedFeatures()
        for feat in selection:
            geom = feat.geometry().asPolyline()
            start_point = QgsPoint(geom[0])
            end_point = QgsPoint(geom[1])
            azimuth = start_point.azimuth(end_point)
            length = feat.geometry().length()
    else:
        pass
        iface.messageBar().pushMessage("No Route Selected", level=Qgis.Critical)
        
# Template Max Length is 15 NM 
if length/1852 > 15:
    L = 15
else:
    L = length/1852

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
new_geom = start_point
    
# Calculate End of Template 
pro_coords = start_point.project(L*1852,azimuth)

# Calculate Start of Template 
width = 1.25
pro_coords2 = start_point.project(width*1852,azimuth-90)

# routine 3 at MAPt
width = 1.25
pro_coords3 = start_point.project(width*1852,azimuth+90)

# routine 4 at VOR splay -90 
width = L*tan(radians(10.3))+1.25
print (width)
pro_coords5 = pro_coords.project(width*1852, azimuth-90)
print (pro_coords5)

# routine 4 at VOR splay -90 
width = L*tan(radians(10.3))+1.25
pro_coords6 = pro_coords.project(width*1852, azimuth+90)

der_geom = new_geom

#Create memory layer

line_start = der_geom
line_end = pro_coords
line = QgsGeometry.fromPolyline([line_start,line_end])
v_layer = QgsVectorLayer("LineString?crs="+map_srid, "NDB template", "memory")
pr = v_layer.dataProvider()

seg = QgsFeature()
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line_end]))
pr.addFeatures( [ seg ] )


# Add 90 deg start
line_start = der_geom
line2_end = pro_coords2
line = QgsGeometry.fromPolyline([line_start,line_end])
seg = QgsFeature()
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line2_end]))
pr.addFeatures( [ seg ] )


# Add 90 deg start
line_start = der_geom
line2_end = pro_coords3
line = QgsGeometry.fromPolyline([line_start,line_end])
seg = QgsFeature()
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line2_end]))
pr.addFeatures( [ seg ] )


# Add -90 deg at 20NM VOR Splay
line_start = pro_coords
line2_end = pro_coords5
line = QgsGeometry.fromPolyline([line_start,line_end])
seg = QgsFeature()
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line2_end]))
pr.addFeatures( [ seg ] )

# Add +90 deg at 20NM VOR Splay
line_start = pro_coords
line2_end = pro_coords6
line = QgsGeometry.fromPolyline([line_start,line_end])
seg = QgsFeature()
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line2_end]))
pr.addFeatures( [ seg ] )

# Join inner VOR splay 
line_start = pro_coords5
line2_end = pro_coords2
line = QgsGeometry.fromPolyline([line_start,line_end])
seg = QgsFeature()
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line2_end]))
pr.addFeatures( [ seg ] )

# Join outer VOR splay 
line_start = pro_coords6
line2_end = pro_coords3
line = QgsGeometry.fromPolyline([line_start,line_end])
seg = QgsFeature()
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line2_end]))
pr.addFeatures( [ seg ] )


v_layer.updateExtents()
QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("orange"))
v_layer.renderer().symbol().setWidth(0.7)
v_layer.triggerRepaint()

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()

#get canvas scale
sc = canvas.scale()
if sc < 200000:
   sc=200000
else:
    sc=sc

canvas.zoomScale(sc)