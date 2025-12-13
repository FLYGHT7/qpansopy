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

#THR_elev = 985.11
#delta = 14.9352
delta = 0

#OASconstants = {
#                "C":(316,51,0),
#                "D":(-286,143,0),
#                "E":(-900,213,0),
#                "C'":(10842,109,300),
#                "D'":(5438,929,300),
#                "E'":(-12900,3019,300),
#                }
#
#OASconstants2 ={}
##OASconstants2 = OASconstants
#
#for m in OASconstants.keys():
#    #if m == 'E':
#    val = OASconstants[m]
#    lst1 = list(val)
#    lst1[1] = -val[1]
#        #print ("listaa",lst1)
#    OASconstants2[m+"mirror"]=lst1
#
#OASconstants3 = OASconstants | OASconstants2
#
##print (OASconstants3)
#
#
#
##
##from PyQt5.QtWidgets import QInputDialog
##def getTextInput(title, message):
##    answer = QInputDialog.getText(None, title, message)
##    if answer[1]:
##        print(answer[0])
##        return answer[0]
##    else:
##        return None
##answer = QInputDialog().getText(None, "Input", "Your input:")
##
###for m in OASconstants.keys():
###    #if m == 'C':
###        val = OASconstants[m]
###        print ("hola",m,val)
##
###OASconstants += OASconstants
##
from qgis.core import Qgis
iface.messageBar().pushMessage("QPANSOPY:", "Executing CONV Initial Approach Segment Straight", level=Qgis.Info)
##
##
###        for n in val:
###            print (n)
##
##s use 0 for start, -1 for end
#s = 0
#
#if s == -1:
#    s2 = 0
#else:
#    s2= 180
#
#
##print (s2)
#
##
##from qgis.PyQt.QtWidgets import QDockWidget
##consoleWidget = iface.mainWindow().findChild( QDockWidget, 'PythonConsole' )
##consoleWidget.console.shellOut.clearConsole()
##

# Select line
layer = iface.activeLayer()
selection = layer.selectedFeatures()
# # Gets the runway layer 
# for layer in QgsProject.instance().mapLayers().values():
#     if "xouting" in layer.name():
#         layer = layer
#         # selection = layer.selectAll()
#         # layer.selectByExpression("segment='missed4'")
#         #print (layer.name())
#         selection = layer.selectedFeatures()
#     else:
#         pass
#         #iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
        
for feat in selection:
    geom = feat.geometry().asPolyline()
    start_point = QgsPoint(geom[-1])
    end_point = QgsPoint(geom[0])
    angle0=start_point.azimuth(end_point)+180
    length0=feat.geometry().length()
    back_angle0 = angle0+180
    
    

#print ("angle:",angle0,length0)

#initial true azimuth data
azimuth =angle0


#map_srid
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
#print (map_srid)

#Create memory layer
#v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "Initial Approach Area", "memory")
#myField = QgsField( 'Initial', QVariant.String)
#v_layer.dataProvider().addAttributes([myField])
#v_layer.updateFields()

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

d = (1.00,2.0,-1.0,-2.0) #NM


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

d = (1.00,2.0,-1.0,-2.0) #NM


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
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "PBN RNAV 1/2", "memory")
myField = QgsField( 'Symbol', QVariant.String)
v_layer.dataProvider().addAttributes([myField])
v_layer.updateFields()


#calculating bottom points
d = (1.25,2.5) #NM

        

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
##
#
#
## Change style of layer 
#v_layer.renderer().symbol().setColor(QColor("magenta"))
#v_layer.renderer().symbol().setWidth(0.7)
#v_layer.triggerRepaint()

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()

#
##get canvas scale
#sc = canvas.scale()
##print (sc)
#if sc < 20000:
#   sc=20000
#else:
#    sc=sc
##print (sc)
#
#canvas.zoomScale(sc)

#for layer in QgsProject.instance().mapLayers().values():
#    if "Initial Approach Area" in layer.name():
#        layer.loadNamedStyle('c:/Users/Antonio/Documents/GitHub/qpansopy/styles/primary_secondary_areas.qml')
#    else:
#            pass
            
v_layer.loadNamedStyle('c:/Users/anton/Documents/GitHub/qpansopy_og/styles/primary_secondary_areas.qml')


iface.messageBar().pushMessage("QPANSOPY:", "Finished RNAV1/2 <30NM", level=Qgis.Success)

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]