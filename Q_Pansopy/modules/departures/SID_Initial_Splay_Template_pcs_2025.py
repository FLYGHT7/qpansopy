'''
SID Initial Splay template
'''

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

# DER elevation
#parameters
WPname='TNA/H'
adElev = 2548 #meters
DERelev= 2548 #meters
PDG = 7.8 #%
tempRef = 20 #meters
IAS = 205
altitude = 9276.46
extra = 000
bankAngle = 15
w = 30
tp = 11

def ISA_temperature (adElev,tempRef):
    tempISA = 15 -0.00198*adElev
    deltaISA = tempRef-tempISA
    return(adElev,tempRef,tempISA,deltaISA)

valueISA = ISA_temperature(adElev,tempRef)

DER_elev = DERelev

for layer in QgsProject.instance().mapLayers().values():
    if "test" in layer.name():
        layer = layer
        selection = layer.selectedFeatures()
    else:
        pass
        #iface.messageBar().pushMessage("No Runway Selected", level=Qgis.Critical)
        
for feat in selection:
    geom = feat.geometry().asPolyline()
    start_point = QgsPoint(geom[0])
    end_point = QgsPoint(geom[-1])
    angle0=start_point.azimuth(end_point)
    back_angle0 = angle0+180

#print ("angle:",angle0)
#initial true azimuth data
azimuth = angle0

''' 
TAS calculation 
'''

def tas_calculation (ias,altitude,var,bank_angle,wind):
    k = 171233*(((288+var)-0.00198*altitude)**0.5)/(288-0.00198*altitude)**2.628
    tas = k*ias
    rate_of_turn = (3431*tan(radians(bank_angle)))/(pi*tas)
    if rate_of_turn > 3:
        rate_of_turn = 3
    else:
        rate_of_turn = (3431*tan(radians(bank_angle)))/(pi*tas)
    radius_of_turn = tas/(20*pi*rate_of_turn)
    #w = (2*altitude/1000)+47 #hardcoded icao standard wind
    w = wind 
    return k,tas,rate_of_turn,radius_of_turn,w

#valuesTAS = tas_calculation(IAS,altitude,valueISA[3],bankAngle,w)
valuesTAS = tas_calculation(205,8900,21.551968603937008,15,30)
print ("ISA:",valueISA[3])
#print (values)

# pilot reaction time
pilotReactionTime = (tp/3600)*(valuesTAS[1]+w)
WindEffect = (90/valuesTAS[2])*(w/3600)

'''
Calculation of the TNA distance
'''
# distance to the Splay End default being 10 NM
# L is in NM
dz = (altitude*0.3048-DERelev-5)/(PDG/100)
#L = 2.54
o1=0 #right
o2=0  #left
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()


new_geom = end_point
# # Selected MAPt
# # Gets the active layer 
# layer = iface.activeLayer()
# #layer.selectByExpression("designator='24'")
# selection = layer.selectedFeatures()
# # Gets x,y
# for feat in selection:
#     #der_elev = (feat['elev_m'])
#     #der_elev = (feat['elevation'])
#     der_geom = feat.geometry().asPoint()
#     new_geom = der_geom
    
# routine 1 SID splay template end determination

''' 
Calculation of TNA Line
'''
# Calculation of SID Start 
TNA_start_left = new_geom.project(150+o1,azimuth-90)
TNA_start_right = new_geom.project(150+o1,azimuth+90)

# Calculation of TNA/H Reached 
TNA_dist = dz #Distance in NM
TNA_end = new_geom.project(TNA_dist,azimuth)
TNA_end_left = TNA_end.project(150+TNA_dist*tan(radians(15)),azimuth-90)
TNA_end_right = TNA_end.project(150+TNA_dist*tan(radians(15)),azimuth+90)

#Calculation of c
c_point = TNA_end.project(pilotReactionTime*1852,azimuth)
c_point_left =c_point.project(150+(TNA_dist+pilotReactionTime*1852)*tan(radians(15)),azimuth-90)
c_point_right = c_point.project(150+(TNA_dist+pilotReactionTime*1852)*tan(radians(15)),azimuth+90) 




#Create memory layer
x_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "SID Protection Areas", "memory")
myField = QgsField( 'Symbol', QVariant.String)
x_layer.dataProvider().addAttributes([myField])
x_layer.updateFields()

# # Change style of layer 
# v_layer.renderer().symbol().setColor(QColor("green"))
# v_layer.renderer().symbol().setWidth(0.7)
# v_layer.triggerRepaint()




'''
SID Area
'''
# Primary Area
SID_TIA = [new_geom,TNA_start_left,TNA_end_left,TNA_end_right,TNA_start_right]
pr = x_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SID_TIA), rings=[]))
seg.setAttributes(['Turn Initiation Area'])
pr.addFeatures( [ seg ] )

# Primary Area
SID_TIA = [TNA_end_left,c_point_left,c_point_right,TNA_end_right]
pr = x_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SID_TIA), rings=[]))
seg.setAttributes(['c Area'])
pr.addFeatures( [ seg ] )




'''
TNA LINE LAYER
'''

## add KK Line, SS Line, NN Line
#Create memory layer
l_layer = QgsVectorLayer("LineString?crs="+map_srid, "SID Construction Lines", "memory")
myField = QgsField( 'id ', QVariant.String)
l_layer.dataProvider().addAttributes([myField])
l_layer.updateFields()
pr = l_layer.dataProvider()

TNA_Line = QgsGeometry.fromPolyline([TNA_end_left,TNA_end,TNA_end_right])
seg = QgsFeature()
seg.setGeometry(TNA_Line)
seg.setAttributes(['TNA/H Reached'])
pr.addFeatures( [ seg ] )

SS_Line = QgsGeometry.fromPolyline([c_point_left,c_point,c_point_right])
seg = QgsFeature()
seg.setGeometry(SS_Line)
seg.setAttributes(['SS LINE'])
pr.addFeatures( [ seg ] )





QgsProject.instance().addMapLayers([l_layer])
QgsProject.instance().addMapLayers([x_layer])

#Set layer rendering
l_layer.renderer().symbol().setColor(QColor("purple"))
l_layer.renderer().symbol().setWidth(.5)
l_layer.renderer().symbol().setOpacity(.7)
l_layer.triggerRepaint()


# Change style of layer 
x_layer.renderer().symbol().setColor(QColor("green"))
x_layer.renderer().symbol().setOpacity(0.7)
#x_layer.renderer().symbol()
x_layer.triggerRepaint()



# # Zoom to layer
#v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(x_layer)
#v_layer.removeSelection()

#get canvas scale
sc = canvas.scale()
print (sc)
if sc < 200000:
   sc=200000
else:
    sc=sc
print (sc)

canvas.zoomScale(sc)



## Create text to clip
text_list=[]
text_list.append('Turn Construction Parameters\t'+''+'\n')
text_list.append('Type of Turn\t'+'TNA/H'+'\n')
text_list.append('Turn Altitude (ft)\t' +str(altitude)+'\n')
text_list.append('PDG (%)\t' +str(PDG)+'\n')
text_list.append('Distance to TNA/H in NM\t' +str(round(dz/1852,4))+'\n')
#text_list.append('Turn @ Waypoint\t'+WPname+'\n')
#text_list.append('XTT (NM)\t'+str(XTT)+'\n')
#text_list.append('ATT (NM)\t' +str(XTT*.8)+'\n')
text_list.append('IAS (KT)\t' +str(IAS)+'\n')
text_list.append('Protected Altitude (ft)\t' +str(altitude+extra)+'\n')
text_list.append('Conversion factor - k\t' +str(round(valuesTAS[0],4))+'\n')
text_list.append('TAS (KT)\t' +str(round(valuesTAS[1],4))+'\n')
#text_list.append('Turn Angle (°)\t'+ str(round(turnAngle,4))+'\n')
text_list.append('Bank Angle (°)\t' +str(bankAngle)+'\n')
text_list.append('Rate of Turn – R (°/s)\t' +str(round(valuesTAS[2],4))+'\n')
text_list.append('Radius of turn – r (NM)\t' +str(round(valuesTAS[3],4))+'\n')
text_list.append('Wind (KT)\t'+ str(w)+'\n')
text_list.append('c (NM)\t' +str(round(pilotReactionTime,4))+'\n')
#text_list.append('DTA (NM)\t' +str(round(DTA,4))+'\n')
#text_list.append('KK LINE (NM)\t' +str(round(KK_Line,4))+'\n')
#text_list.append('SS LINE (NM)\t' +str(round(SS_Line,4))+'\n')
text_list.append('E90 (NM)\t' +str(round(WindEffect,4))+'\n')



final_text ="".join(text_list)
print (final_text)
QApplication.clipboard().setText(final_text)