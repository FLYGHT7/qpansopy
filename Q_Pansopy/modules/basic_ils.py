# -*- coding: utf-8 -*-
"""
Basic ILS Surface Generator
"""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsPointXY, QgsWkbTypes, QgsField, QgsFields, QgsPoint,
    QgsLineString, QgsPolygon, QgsVectorFileWriter
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import Qgis
from qgis.utils import iface
import math
import os
import datetime

def calculate_basic_ils(iface, point_layer, runway_layer, params):
    """
    Create Basic ILS Surfaces
    
    :param iface: QGIS interface
    :param point_layer: Point layer with the reference point (WGS84)
    :param runway_layer: Runway layer (projected CRS)
    :param params: Dictionary with calculation parameters
    :return: Dictionary with results
    """
    # Extract parameters
    thr_elev = params.get('thr_elev', 0)
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', os.path.expanduser('~'))
    
    # Check if layers exist
    if not point_layer or not runway_layer:
        iface.messageBar().pushMessage("Error", "Point or runway layer not provided", level=Qgis.Critical)
        return None
    
    # Check if layers have features
    if point_layer.featureCount() == 0:
        iface.messageBar().pushMessage("Error", "Point layer has no features", level=Qgis.Critical)
        return None
    
    if runway_layer.featureCount() == 0:
        iface.messageBar().pushMessage("Error", "Runway layer has no features", level=Qgis.Critical)
        return None
    
    # Get the reference point
    point_feature = next(point_layer.getFeatures())
    thr_geom = point_feature.geometry().asPoint()
    
    # Get the runway line
    runway_feature = next(runway_layer.getFeatures())
    runway_geom = runway_feature.geometry().asPolyline()
    
    # Get map CRS
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Calculate azimuth
    start_point = QgsPoint(runway_geom[0])
    end_point = QgsPoint(runway_geom[1])
    angle0 = start_point.azimuth(end_point)
    
    # Use end of runway for calculation
    s = -1
    if s == -1:
        s2 = 0
    else:
        s2 = 180
    
    azimuth = angle0 + s2
    back_azimuth = azimuth - 180
    
    # Function to convert from PointXY and add Z value
    def pz(point, z):
        cPoint = QgsPoint(point)
        cPoint.addZValue()
        cPoint.setZ(z)
        return cPoint
    
    # Create memory layer
    v_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, "Basic_ILS_Surfaces", "memory")
    provider = v_layer.dataProvider()
    
    # Add fields
    provider.addAttributes([
        QgsField('ILS_surface', QVariant.String), QgsField('constants', QVariant.String)
    ])
    v_layer.updateFields()
    
    # Calculate surface points
    # Ground surface
    gs_center = thr_geom.project(60, azimuth)
    gs_a = gs_center.project(150, azimuth-90)
    gs_b = gs_a.project(960, back_azimuth)
    gs_d = gs_center.project(150, azimuth+90)
    gs_c = gs_d.project(960, back_azimuth)
    
    # Approach surface section 1
    as1_center = gs_center.project(3000, azimuth)
    as1_a = as1_center.project(3000*.15+150, azimuth-90)
    as1_d = as1_center.project(3000*.15+150, azimuth+90)
    
    # Approach surface section 2
    as2_center = as1_center.project(9600, azimuth)
    as2_a = as2_center.project(12600*.15+150, azimuth-90)
    as2_d = as2_center.project(12600*.15+150, azimuth+90)
    
    # Missed approach surface
    missed_center = thr_geom.project(900, back_azimuth)
    missed_a = missed_center.project(150, azimuth-90)
    missed_m_center = missed_center.project(1800, back_azimuth)
    missed_b = missed_m_center.project(150+1800*((45/(14.3/100))/1800), azimuth-90)
    missed_e = missed_m_center.project(150+1800*((45/(14.3/100))/1800), azimuth+90)
    missed_f = missed_center.project(150, azimuth+90)
    missed_f_center = missed_center.project(12000, back_azimuth)
    missed_c = missed_f_center.project(150+1800*((45/(14.3/100))/1800)+(10200*.25), azimuth-90)
    missed_d = missed_f_center.project(150+1800*((45/(14.3/100))/1800)+(10200*.25), azimuth+90)
    
    # Transition surface side distances
    transition_distance_1 = (300 - 60) / (14.3/100)
    transition_distance_2 = (300 / (14.3/100))
    transition_distance_3 = (300 - 45) / (14.3/100)
    
    # Transition surface points
    transition_e1_left = as1_d.project(transition_distance_1, azimuth + 90)
    transition_e1_right = as1_a.project(transition_distance_1, azimuth - 90)
    transition_e2_left = gs_d.project(transition_distance_2, azimuth + 90)
    transition_e2_right = gs_a.project(transition_distance_2, azimuth - 90)
    transition_e3_left = missed_e.project(transition_distance_3, azimuth + 90)
    transition_e3_right = missed_b.project(transition_distance_3, azimuth - 90)
    
    # Create and add features for each surface
    
    # Ground surface
    exterior_ring = [pz(gs_a, thr_elev), pz(gs_b, thr_elev), pz(gs_c, thr_elev), pz(gs_d, thr_elev)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['ground surface'])
    provider.addFeatures([feature])
    
    # Approach surface section 1
    exterior_ring = [pz(as1_a, thr_elev+60), pz(gs_a, thr_elev), pz(gs_d, thr_elev), pz(as1_d, thr_elev+60)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['approach surface first section'])
    provider.addFeatures([feature])
    
    # Approach surface section 2
    exterior_ring = [pz(as2_a, thr_elev+300), pz(as1_a, thr_elev+60), pz(as1_d, thr_elev+60), pz(as2_d, thr_elev+300)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['approach surface second section'])
    provider.addFeatures([feature])
    
    # Missed approach surface
    exterior_ring = [pz(missed_a, thr_elev), pz(missed_b, thr_elev+1800*0.025), pz(missed_c, thr_elev+12000*.025), pz(missed_d, thr_elev+12000*0.025), pz(missed_e, thr_elev+1800*0.025), pz(missed_f, thr_elev)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['missed approach surface'])
    provider.addFeatures([feature])
    
    # Transition surfaces
    # Left 1
    exterior_ring = [pz(as2_d, thr_elev+300), pz(as1_d, thr_elev+60), pz(transition_e1_left, thr_elev+300)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - left 1'])
    provider.addFeatures([feature])
    
    # Left 2
    exterior_ring = [pz(as1_d, thr_elev+60), pz(transition_e1_left, thr_elev+300), pz(transition_e2_left, thr_elev+300), pz(gs_d, thr_elev)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - left 2'])
    provider.addFeatures([feature])
    
    # Left 3
    exterior_ring = [pz(transition_e2_left, thr_elev+300), pz(gs_d, thr_elev), pz(gs_c, thr_elev), pz(missed_e, thr_elev+1800*0.025), pz(transition_e3_left, thr_elev+300)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - left 3'])
    provider.addFeatures([feature])
    
    # Left 4
    exterior_ring = [pz(missed_e, thr_elev+1800*0.025), pz(missed_d, thr_elev+12000*.025), pz(transition_e3_left, thr_elev+300)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - left 4'])
    provider.addFeatures([feature])
    
    # Right 1
    exterior_ring = [pz(as2_a, thr_elev+300), pz(as1_a, thr_elev+60), pz(transition_e1_right, thr_elev+300)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - right 1'])
    provider.addFeatures([feature])
    
    # Right 2
    exterior_ring = [pz(as1_a, thr_elev+60), pz(transition_e1_right, thr_elev+300), pz(transition_e2_right, thr_elev+300), pz(gs_a, thr_elev)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - right 2'])
    provider.addFeatures([feature])
    
    # Right 3
    exterior_ring = [pz(transition_e2_right, thr_elev+300), pz(transition_e3_right, thr_elev+300), pz(missed_b, thr_elev+1800*0.025), pz(gs_b, thr_elev), pz(gs_a, thr_elev)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - right 3'])
    provider.addFeatures([feature])
    
    # Right 4
    exterior_ring = [pz(missed_b, thr_elev+1800*0.025), pz(missed_c, thr_elev+12000*.025), pz(transition_e3_right, thr_elev+300)]
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(exterior_ring)))
    feature.setAttributes(['transition surface - right 4'])
    provider.addFeatures([feature])
    
    # Update layer extents
    v_layer.updateExtents()
    
    # Style the layer - green with 50% opacity as requested by client
    v_layer.renderer().symbol().setColor(QColor(0, 255, 0, 127))  # Green with 50% opacity
    v_layer.renderer().symbol().symbolLayer(0).setStrokeColor(QColor(0, 255, 0))
    v_layer.renderer().symbol().symbolLayer(0).setStrokeWidth(0.7)
    
    # Add layer to the project
    QgsProject.instance().addMapLayer(v_layer)
    
    # Zoom to layer
    v_layer.selectAll()
    canvas = iface.mapCanvas()
    canvas.zoomToSelected(v_layer)
    v_layer.removeSelection()
    
    # Export to KML if requested
    result = {
        'ils_layer': v_layer
    }
    
    if export_kml:
        # Get current timestamp for unique filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define KML export path
        kml_export_path = os.path.join(output_dir, f'Basic_ILS_Surfaces_{timestamp}.kml')
        
        # Export to KML
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        kml_error = QgsVectorFileWriter.writeAsVectorFormat(
            v_layer,
            kml_export_path,
            'utf-8',
            crs,
            'KML',
            layerOptions=['MODE=2']
        )
        
        # Correct KML structure for better visualization
        def correct_kml_structure(kml_file_path):
            with open(kml_file_path, 'r') as file:
                kml_content = file.read()
            
            # Add altitude mode
            kml_content = kml_content.replace('<Polygon>', '<Polygon>\n  <altitudeMode>absolute</altitudeMode>')
            
            # Add style - green with 50% opacity
            style_kml = '''
            <Style id="style1">
                <LineStyle>
                    <color>ff00ff00</color>
                    <width>2</width>
                </LineStyle>
                <PolyStyle>
                    <fill>1</fill>
                    <color>ff00ff7F</color>
                </PolyStyle>
            </Style>
            '''
            
            kml_content = kml_content.replace('<Document>', f'<Document>{style_kml}')
            kml_content = kml_content.replace('<styleUrl>#</styleUrl>', '<styleUrl>#style1</styleUrl>')
            
            with open(kml_file_path, 'w') as file:
                file.write(kml_content)
        
        # Apply corrections to KML file
        if kml_error[0] == QgsVectorFileWriter.NoError:
            correct_kml_structure(kml_export_path)
            result['kml_path'] = kml_export_path
    
    # Zoom to appropriate scale
    sc = canvas.scale()
    if sc < 20000:
        sc = 20000
    canvas.zoomScale(sc)
    
    # Show success message
    iface.messageBar().pushMessage("QPANSOPY:", "Basic ILS Surfaces created successfully", level=Qgis.Success)
    
    return result