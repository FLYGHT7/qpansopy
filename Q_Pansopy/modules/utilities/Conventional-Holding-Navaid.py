'''
Holding/Racetrack
'''

myglobals = set(globals().keys())

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

#side = 90 LEFT
#side = -90 RIGHT

#sides= QInputDialog.getText(None, "Turn Direction" ,"L or R")


#if sides[0] =="L":
#    side = 90
#    d = (30,60,90,120,150,180,210,240,270) #NM
#elif sides[0] =="R":
#    side=-90
#    d = (-30,-60,-90,-120,-150,-180,-210,-240,-270) #NM
#else:
#    side ='X'

side = -90

#print (side)


#IAS = QInputDialog.getText(None, 'Turn Parameters', 'IAS')



'''
Aviation Calculations for Wind Spiral
'''

def holding_basic_area (ias,altitude,vh,var,bank_angle,time):
    k = 171233*(((288+var)-0.00198*altitude)**0.5)/(288-0.00198*altitude)**2.628
    tas = k*ias
    v = tas / 3600
    rate_of_turn = (3431*tan(radians(bank_angle)))/(pi*tas)
    radius_of_turn = tas/(20*pi*rate_of_turn)
    h = (altitude - vh)/1000
    w = (2*altitude/1000)+47 #hardcoded icao standard wind
    wp= w/3600
    E45 = (45*wp)/rate_of_turn
    t = time*60
    L = v*t
    L12=5*v
    L13=11*v
    L14=(t-5)*v
    L15=(t+21)*v
    L16= 5*wp
    L17= 11*wp
    L18=L17+E45
    L19=L17+2*E45
    L20=L17+3*E45
    L21=L17+4*E45
    L22=L16+4*E45
    L23=L16+5*E45
    L24=L16+6*E45
    L25=(t+6)*wp+4*E45
    L26=L25+14*wp
    L27=L26+E45
    L28=L26+2*E45
    L29=L26+3*E45
    L30=L25+4*E45
    L31=L26+4*E45
    L32=2*radius_of_turn+(t+15)*v+(t+26+195/rate_of_turn)*wp
    L33=11*v*cos(radians(20))+radius_of_turn*(1+sin(radians(20)))+(t+15)*v*tan(radians(5))+(t+26+125/rate_of_turn)*wp
    
    
    return k,tas,v,rate_of_turn,radius_of_turn,h,w,wp,E45,t,L,L12,L13,L14,L15,L16,L17,L18,L19,L20,L21,L22,L23,L24,L25,L26,L27,L28,L29,L30,L31,L32,L33

#print (tas_calculation(240,8000,15,25))

values = holding_basic_area(195,10000,0,15,25,1)

#ct=1
#for n in values:
#    print ("line"+str(ct),n)
#    ct+=1

print (values[11-1])

from qgis.core import Qgis
iface.messageBar().pushMessage("QPANSOPY:", "Holding/Racetrack Basic Area", level=Qgis.Info)

# Select line
# Gets the routing layer 

pts={}

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
        #print ("angle:",angle0,length0/1852)
        pts["start"]=start_point    
        
#initial true azimuth data
azimuth =angle0
ct=0


#map_srid
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
#print (map_srid)

#Create memory layer
v_layer = QgsVectorLayer("Linestring?crs="+map_srid, "HLDG/RACETRACK "+str(int(values[2-1]/values[1-1]))+"KTS", "memory")
myField = QgsField( 'segment', QVariant.String)
v_layer.dataProvider().addAttributes([myField])
v_layer.updateFields()


#def nominal track
# outbound
angle =     90-azimuth-180#left/right
#print (angle)
bearing = math.radians(azimuth)
angle =   math.radians(angle)
dist_x, dist_y = (values[11-1]*1852 * math.cos(angle), values[11-1]*1852 * math.sin(angle))
#print (dist_x, dist_y)
xc, yc = (pts["start"].x() + dist_x, pts["start"].y() + dist_y)
pr = v_layer.dataProvider()
pts["outbound"]=QgsPoint(xc,yc)



pts2={} 
for i in pts:
    #print (i,pts[i])
    # outbound
    angle =     90-azimuth-side#left/right
    #print (angle)
    bearing = math.radians(azimuth)
    angle =   math.radians(angle)
    dist_x, dist_y = (values[11-1]*1852 * math.cos(angle), values[11-1]*1852 * math.sin(angle))
    #print (dist_x, dist_y)
    xc, yc = (pts[i].x() + dist_x, pts[i].y() + dist_y)
    pts2["nominal"+str(ct)]= QgsPoint(xc,yc)
    pr = v_layer.dataProvider()
    ct+=1
    
    dist_x, dist_y = (values[11-1]/2*1852 * math.cos(angle), values[11-1]/2*1852 * math.sin(angle))
    #print (dist_x, dist_y)
    xc, yc = (pts[i].x() + dist_x, pts[i].y() + dist_y)
#    pts2["nominal"+str(ct)]= QgsPointXY(xc,yc)
#    pr = v_layer.dataProvider()
#    ct+=1
    
    if i == "start":
        angle =     90-azimuth#left/right
        angle =   math.radians(angle)
        dist_x, dist_y = (values[11-1]/2*1852 * math.cos(angle), values[11-1]/2*1852 * math.sin(angle))
        #print (dist_x, dist_y)
        xc, yc = (xc + dist_x, yc + dist_y)
        pts2["nominal"+str(ct)]= QgsPoint(xc,yc)
        pr = v_layer.dataProvider()
        ct+=1
    else:
        angle =     90-azimuth+180#left/right
        angle =   math.radians(angle)
        dist_x, dist_y = (values[11-1]/2*1852 * math.cos(angle), values[11-1]/2*1852 * math.sin(angle))
        #print (dist_x, dist_y)
        xc, yc = (xc + dist_x, yc + dist_y)
        pts2["nominal"+str(ct)]= QgsPoint(xc,yc)
        pr = v_layer.dataProvider()
        ct+=1



pts3 = pts | pts2


pts = pts3

#print (pts)

#for i in pts:
#    #create a new feature
#    seg = QgsFeature()
#    seg.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(pts[i].x(),pts[i].y())))
#    seg.setAttributes(['nominal'])
#    pr.addFeatures( [ seg ] )
#

# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(QgsGeometry.fromPolyline([pts["outbound"], pts["start"]]))
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )


# Circular String top
pr = v_layer.dataProvider()
cString = QgsCircularString()
cString.setPoints([pts["start"],pts["nominal1"],pts["nominal0"]])
# create a new feature
geom_cString=QgsGeometry(cString)
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(geom_cString)
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )

# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(QgsGeometry.fromPolyline([pts["nominal0"], pts["nominal2"]]))
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )


# Circular String bottom
cString = QgsCircularString()
cString.setPoints([pts["nominal2"],pts["nominal3"],pts["outbound"]])
# create a new feature
geom_cString=QgsGeometry(cString)
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(geom_cString)
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )


v_layer.updateExtents()

QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("magenta"))
v_layer.renderer().symbol().setWidth(0.7)
v_layer.triggerRepaint()
###
### Zoom to layer
##v_layer.selectAll()
##canvas = iface.mapCanvas()
##canvas.zoomToSelected(v_layer)
##v_layer.removeSelection()
###
####
#####get canvas scale
####sc = canvas.scale()
#####print (sc)
####if sc < 20000:
####   sc=20000
###else:
###    sc=sc
####print (sc)
###
##canvas.zoomScale(150000)
##
###for layer in QgsProject.instance().mapLayers().values():
###    if "Initial Approach Area" in layer.name():
###        layer.loadNamedStyle('c:/Users/Antonio/Documents/GitHub/qpansopy/styles/primary_secondary_areas.qml')
###    else:
###            pass
##            
##v_layer.loadNamedStyle('c:/Users/Antonio/Documents/GitHub/qpansopy/styles/primary_secondary_areas.qml')
##

iface.messageBar().pushMessage("QPANSOPY:", "Finished Holding/Racetrack", level=Qgis.Success)

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]