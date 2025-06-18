'''
CONV Initial Approach Segment Straight
'''

myglobals = set(globals().keys())

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

'''
Constants 
-> They need to be taken from OAS software 
'''

delta = 0

from qgis.core import Qgis
iface.messageBar().pushMessage("QPANSOPY:", "Executing CONV Initial Approach Segment Straight", level=Qgis.Info)

# Select line
# Gets the runway layer 
for layer in QgsProject.instance().mapLayers().values():
    if "routing" in layer.name():
        layer = layer
        #selection = layer.selectAll()
        #layer.selectByExpression("segment='initial'")
        #print (layer.name())
        selection = layer.selectedFeatures()
    else:
        pass
        iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
        
for feat in selection:
    geom = feat.geometry().asPolyline()
    start_point = QgsPoint(geom[-1])
    end_point = QgsPoint(geom[0])
    angle0=start_point.azimuth(end_point)+180
    length0=feat.geometry().length()
    back_angle0 = angle0+180
    
azimuth =angle0


#map_srid
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
#print (map_srid)


pts={}
a=0

# routine 1 FAF determination

bearing =  azimuth
angle =     90 - bearing
bearing = math.radians(bearing)
angle =   math.radians(angle)
dist_x, dist_y = \
    (length0 * math.cos(angle), length0 * math.sin(angle))
#print (dist_x, dist_y)
#print (start_point)
#xfinal, yfinal = (start_point.x() + dist_x, start_point.y() + dist_y)
#print (xfinal, yfinal)
#line_start = QgsPoint(xfinal,yfinal)
pts["m"+str(a)]=QgsPoint(end_point.x() + dist_x, end_point.y() + dist_y)
a+=1

pts["m"+str(a)]=QgsPoint(end_point.x(), end_point.y())
a+=1


#calculating bottom points

d = (2.5,5,-2.5,-5) #NM


for i in d:
    
    #print (i)
    
    TNA_dist = i * 1852
    #print (TNA_dist)
    bearing =  azimuth+90
    angle =     90 - bearing
    bearing = math.radians(bearing)
    angle =   math.radians(angle)
    dist_x, dist_y = \
        (TNA_dist * math.cos(angle), TNA_dist * math.sin(angle))
    #print (dist_x, dist_y)
    bx1, by2 = (start_point.x()  + dist_x, start_point.y()  + dist_y)
    #print (bx1, by2)

    line_start = QgsPoint(bx1,by2)
    pts["m"+str(a)]=line_start
    a+=1
    
#calculating top points

d = (2.5,5,-2.5,-5) #NM


for i in d:
    
    #print (i)
    
    TNA_dist = i * 1852
    #print (TNA_dist)
    bearing =  azimuth+90
    angle =     90 - bearing
    bearing = math.radians(bearing)
    angle =   math.radians(angle)
    dist_x, dist_y = \
        (TNA_dist * math.cos(angle), TNA_dist * math.sin(angle))
    #print (dist_x, dist_y)
    bx1, by2 = (end_point.x()  + dist_x, end_point.y()  + dist_y)
    #print (bx1, by2)

    line_start = QgsPoint(bx1,by2)
    pts["m"+str(a)]=line_start
    a+=1
    
print (pts)

#Create memory layer
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "Initial Approach Area", "memory")
myField = QgsField( 'Symbol', QVariant.String)
v_layer.dataProvider().addAttributes([myField])
v_layer.updateFields()


#calculating bottom points
d = (2.5,5) #NM

        

# Primary Area
line_start = [pts["m2"],pts["m0"],pts["m4"],pts["m8"],pts["m1"],pts["m6"]]
#print (line_start)
pr = v_layer.dataProvider()
# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
#seg.setGeometry(QgsGeometry.fromPolygonXY([line_start]))
seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
seg.setAttributes(['Primary Area'])
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )

# Secondary Area Left
line_start = [pts["m3"],pts["m2"],pts["m6"],pts["m7"]]
#print (line_start)
pr = v_layer.dataProvider()
# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
#seg.setGeometry(QgsGeometry.fromPolygonXY([line_start]))
seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
seg.setAttributes(['Secondary Area'])
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )

# Secondary Area Right
# Secondary Area Left
line_start = [pts["m4"],pts["m5"],pts["m9"],pts["m8"]]
#print (line_start)
pr = v_layer.dataProvider()
# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
#seg.setGeometry(QgsGeometry.fromPolygonXY([line_start]))
seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
seg.setAttributes(['Secondary Area'])
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )


v_layer.updateExtents()

QgsProject.instance().addMapLayers([v_layer])

v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()

            
v_layer.loadNamedStyle('c:/Users/anton/Documents/GitHub/qpansopy_og/styles/primary_secondary_areas.qml')


iface.messageBar().pushMessage("QPANSOPY:", "Finished Initial Approach Segment", level=Qgis.Success)

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]