'''
GNSS Waypoint
'''

myglobals = set(globals().keys())

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *


from qgis.core import Qgis
iface.messageBar().pushMessage("QPANSOPY:", "GNSS Waypoint", level=Qgis.Info)

XTT = 1.0 # XTT siempre mas que ATT 

# map_srid
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
print (map_srid)

# Selects Waypoint
layer = iface.activeLayer()
selection = layer.selectedFeatures()
# Gets x,y
for feat in selection:
    p_geom = feat.geometry().asPoint()
    #print (p_geom)



for layer in QgsProject.instance().mapLayers().values():
    if "routing" in layer.name():
        layer = layer
        selection = layer.selectedFeatures()
        geom=selection[0].geometry().asPolyline()
        #print (geom)
        start_point = QgsPoint(geom[-1])
        end_point = QgsPoint(geom[0])
        angle0=start_point.azimuth(end_point)+180
        length0=selection[0].geometry().length()
        back_angle0 = angle0+180
        print ("angle:",angle0,length0/1852)

#initial true azimuth data
azimuth =angle0


#Create memory layer
v_layer = QgsVectorLayer("Polygon?crs="+map_srid, "Tolerances", "memory")
XTTn = QgsField( 'XTT', QVariant.String)
ATTn = QgsField( 'ATT', QVariant.String)
v_layer.dataProvider().addAttributes([XTTn])
v_layer.dataProvider().addAttributes([ATTn])
v_layer.updateFields()
pr = v_layer.dataProvider()

# create a new feature
#rect = QgsRectangle(p_geom,QgsPointXY(276024,1726660))
#print (rect)
rect = QgsRectangle.fromCenterAndSize(p_geom,2*XTT*1852,2*0.8*XTT*1852)
#print (rect)


polygon = QgsGeometry.fromRect(rect)


#print (polygon)
centroid = polygon.centroid().asPoint()
polygon.rotate(azimuth, centroid)
#print (polygon)
seg = QgsFeature()
seg.setGeometry(polygon)
seg.setAttributes( [str(XTT)+' NM',str(0.8*XTT)+' NM'] )
pr.addFeatures( [ seg ] )
print (seg)

## update extent of the layer (not necessary)
v_layer.updateExtents()


# Change style of layer 
v_layer.renderer().symbol().setOpacity(.3)
v_layer.renderer().symbol().setColor(QColor("blue"))
#v_layer.renderer().symbol().setWidth(0.5)
iface.layerTreeView().refreshLayerSymbology( iface.activeLayer().id() )
v_layer.triggerRepaint()


# show the line  
QgsProject.instance().addMapLayers([v_layer])





iface.messageBar().pushMessage("QPANSOPY:", "GNSS Waypoint Finished", level=Qgis.Success)

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]