##
from qgis.core import Qgis
iface.messageBar().pushMessage("QPANSOPY:", "Executing Omnidirectional SID Calculation", level=Qgis.Info)

# Import libraries
from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *
from qgis.core import QgsGeometryUtils as util

# Initial Data
der_elevation_m = 52
pdg =3.3
TNA_ft = 2000
msa_ft = 6300
cwy_distance_m = 150
allow_turns_before_der = 'NO'
include_construction_points = 'NO'

# conversions
def convert_m_nm (val):
    nm_value = val/1852
    return nm_value

def convert_ft_m(val):
    m_value = val*0.3048
    return m_value

# Area 1 Calculation
# Area 1 is where the aircraft reaches 120 m height
# with the provided PDG

def calculate_area1_limit(pdg):
    distance_area1_m = (120-5)/(pdg/100)
    return distance_area1_m

distance_area1 = calculate_area1_limit(pdg)
elevation_area0 = der_elevation_m+5
elevation_area1 = der_elevation_m+5+distance_area1*((pdg-.8)/100)
# Area 2 Calculation
# Area 2 is where the aircraft reaches TNA/H before turning
# with the provided PDG

def calculate_area2_limit(pdg, der_elevation):
    distance_area2_m = (convert_ft_m(TNA_ft)- 120-der_elevation)/(pdg/100)
    return distance_area2_m

distance_area2 = calculate_area2_limit(pdg,der_elevation_m)
elevation_area2 = elevation_area1 + distance_area2*((pdg-0.8)/100)

# Area 3 Calculation
# Area 3 is where the aircraft reaches MSA
# with the provided PDG

def calculate_area3_limit(pdg,msa):
    distance_area3_m = (convert_ft_m(msa)-convert_ft_m(TNA_ft))/(pdg/100)+distance_area2+distance_area1 
    return distance_area3_m

distance_area3 = calculate_area3_limit(pdg,msa_ft)
elevation_area3 = convert_ft_m(msa_ft)

#map_srid
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
#print (map_srid)

# Runway selection based on active layer
layer = iface.activeLayer()
selection = layer.selectedFeatures()

for feat in selection:
    geom = feat.geometry().asPolyline()
    start_point = QgsPoint(geom[0])
    end_point = QgsPoint(geom[1])
    front_angle = start_point.azimuth(end_point)
    back_angle = front_angle +180
# print (front_angle)

# Calculate limiting points for areas 

point_list ={}

def calculate_points (point_name,initial_point,distance,angle,Z):
    calculated_point = initial_point.project(distance,angle)
    calculated_point.addZValue(Z)
    calculated_point.setZ(Z)
    point_list[point_name] = calculated_point
    

# Calculation of Omnidirectional SID points 
width_area_1 = 150 + distance_area1*tan(radians(15))
width_area_2 = width_area_1 + distance_area2*tan(radians(30))

calculate_points ('point_0_center',end_point,cwy_distance_m,front_angle,elevation_area0)
calculate_points ('point_0_left',point_list['point_0_center'],150,front_angle-90,elevation_area0)
calculate_points ('point_0_right',point_list['point_0_center'],150,front_angle+90,elevation_area0)
calculate_points ('point_1_center',point_list['point_0_center'],distance_area1,front_angle,elevation_area1)
calculate_points ('point_1_left',point_list['point_1_center'],width_area_1,front_angle-90,elevation_area1)
calculate_points ('point_1_right',point_list['point_1_center'],width_area_1,front_angle+90,elevation_area1)
calculate_points ('point_2_center',point_list['point_1_center'],distance_area2,front_angle,elevation_area2)
calculate_points ('point_2_left',point_list['point_2_center'],width_area_2,front_angle-90,elevation_area2)
calculate_points ('point_2_right',point_list['point_2_center'],width_area_2,front_angle+90,elevation_area2)
calculate_points ('point_600m_takeoff_center',start_point,600,front_angle,elevation_area0)
calculate_points ('point_600m_takeoff_left',point_list['point_600m_takeoff_center'],150,front_angle-90,elevation_area0)
calculate_points ('point_600m_takeoff_right',point_list['point_600m_takeoff_center'],150,front_angle+90,elevation_area0)
 
#Create memory layer
x_layer = QgsVectorLayer("PointZ?crs="+map_srid, "Omnidirectional SID construction points_"+str(pdg), "memory")
myField = QgsField( 'id', QVariant.String)
x_layer.dataProvider().addAttributes([myField])
x_layer.updateFields()

for point in point_list:
    pr = x_layer.dataProvider()
    seg = QgsFeature()
    seg.setGeometry(point_list[point])
    seg.setAttributes([point])
    pr.addFeatures( [ seg ] )


if include_construction_points == 'YES':
    QgsProject.instance().addMapLayers([x_layer])

#Create memory layer
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "OmniSID 3D Area_PDG_"+str(pdg)+'%', "memory")
myField = QgsField( 'omni_area', QVariant.String)
v_layer.dataProvider().addAttributes([myField])
v_layer.updateFields()

surface_list = {}

def add_surface (surface_name,points):
    line_start = points
    pr = v_layer.dataProvider()
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(line_start), rings=[]))
    seg.setAttributes([surface_name])
    pr.addFeatures( [ seg ] )
    surface_list[surface_name] = seg.geometry()



add_surface('Area 1',[point_list['point_1_left'],point_list['point_0_left'],point_list['point_0_center'],point_list['point_0_right'],point_list['point_1_right'],point_list['point_1_center']])
add_surface('Area 2',[point_list['point_2_left'],point_list['point_1_left'],point_list['point_1_center'],point_list['point_1_right'],point_list['point_2_right'],point_list['point_2_center']])

if allow_turns_before_der == 'YES':
    add_surface('Before DER',[point_list['point_0_left'],point_list['point_600m_takeoff_left'],point_list['point_600m_takeoff_center'],point_list['point_600m_takeoff_right'],point_list['point_0_right'],point_list['point_0_center']])   

#print (surface_list)

area3o = QgsGeometry.fromPointXY((QgsPointXY(point_list['point_600m_takeoff_center']))).buffer(distance_area3,360)
area3a = area3o.difference(surface_list['Area 2'])
area3a = area3a.difference(surface_list['Area 1'])

if allow_turns_before_der == 'YES':
    area3a = area3a.difference(surface_list['Before DER'])


pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(area3a)
seg.setAttributes(['Area 3'])
pr.addFeatures( [ seg ] )


v_layer.updateExtents()
# show the line  

    # Change style of layer 
v_layer.renderer().symbol().setOpacity(0.3)
v_layer.renderer().symbol().setColor(QColor("blue"))
#v_layer.renderer().symbol().setWidth(0.5)
iface.layerTreeView().refreshLayerSymbology( iface.activeLayer().id() )
v_layer.triggerRepaint()
#
#
# show the line  

QgsProject.instance().addMapLayers([v_layer])
#
