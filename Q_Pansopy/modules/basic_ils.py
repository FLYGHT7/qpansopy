# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Basic ILS Surfaces Module
                              -------------------
        begin                : 2023-04-29
        copyright            : (C) 2023 by Your Name
        email                : your.email@example.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPoint, 
    QgsLineString, QgsPolygon, QgsField, QgsCoordinateReferenceSystem,
    QgsVectorFileWriter, Qgis
)
from qgis.PyQt.QtCore import QVariant
from PyQt5.QtGui import QColor
from math import *

def calculate_basic_ils(iface, point_layer, runway_layer, params):
    """
    Calculate Basic ILS Surfaces
    
    :param iface: QGIS interface
    :param point_layer: Threshold point layer
    :param runway_layer: Runway line layer
    :param params: Dictionary of parameters
    :return: Dictionary with results
    """
    
    # Extract parameters
    thr_elev = params.get('thr_elev', 985.11)  # Default value in meters
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', None)
    
    # Get the map CRS
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Get the threshold point
    if point_layer.selectedFeatureCount() > 0:
        for feat in point_layer.selectedFeatures():
            thr_geom = feat.geometry().asPoint()
            break
    else:
        # If no feature is selected, use the first feature
        for feat in point_layer.getFeatures():
            thr_geom = feat.geometry().asPoint()
            break
    
    # Get the runway line
    if runway_layer.selectedFeatureCount() > 0:
        for feat in runway_layer.selectedFeatures():
            geom = feat.geometry().asPolyline()
            start_point = QgsPoint(geom[0])
            end_point = QgsPoint(geom[1])
            angle0 = start_point.azimuth(end_point)
            break
    else:
        # If no feature is selected, use the first feature
        for feat in runway_layer.getFeatures():
            geom = feat.geometry().asPolyline()
            start_point = QgsPoint(geom[0])
            end_point = QgsPoint(geom[1])
            angle0 = start_point.azimuth(end_point)
            break
    
    # Set azimuth and back azimuth
    s = -1  # Use -1 for end point
    s2 = 0 if s == -1 else 180
    azimuth = angle0 + s2
    back_azimuth = azimuth - 180
    
    # Function to convert from PointXY and add Z value
    def pz(point, z):
        cPoint = QgsPoint(point)
        cPoint.addZValue()
        cPoint.setZ(z)
        return cPoint
    
    # Create memory layer for Basic ILS Surfaces
    v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "Basic_ILS_Surfaces", "memory")
    myField = QgsField('ILS_surface', QVariant.String)
    v_layer.dataProvider().addAttributes([myField])
    v_layer.updateFields()
    
    # Calculate surfaces
    
    # Ground surface calculation 
    gs_center = thr_geom.project(60, azimuth)
    gs_a = gs_center.project(150, azimuth-90)
    gs_b = gs_a.project(960, back_azimuth)
    gs_d = gs_center.project(150, azimuth+90)
    gs_c = gs_d.project(960, back_azimuth)

    # Approach surface section 1 calculation
    as1_center = gs_center.project(3000, azimuth)
    as1_a = as1_center.project(3000*.15+150, azimuth-90)
    as1_d = as1_center.project(3000*.15+150, azimuth+90)

    # Approach surface section 2 calculation
    as2_center = as1_center.project(9600, azimuth)
    as2_a = as2_center.project(12600*.15+150, azimuth-90)
    as2_d = as2_center.project(12600*.15+150, azimuth+90)

    # Missed approach surface calculation
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
    
    # Add features to the layer
    pr = v_layer.dataProvider()
    
    # Add Ground 
    exterior_ring = [pz(gs_a, thr_elev), pz(gs_b, thr_elev), pz(gs_c, thr_elev), pz(gs_d, thr_elev)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['ground surface'])
    pr.addFeatures([seg])

    # Add AS1
    exterior_ring = [pz(as1_a, thr_elev+60), pz(gs_a, thr_elev), pz(gs_d, thr_elev), pz(as1_d, thr_elev+60)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['approach surface first section'])
    pr.addFeatures([seg])

    # Add AS2
    exterior_ring = [pz(as2_a, thr_elev+300), pz(as1_a, thr_elev+60), pz(as1_d, thr_elev+60), pz(as2_d, thr_elev+300)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['approach surface second section'])
    pr.addFeatures([seg])

    # Add Missed 
    exterior_ring = [pz(missed_a, thr_elev), pz(missed_b, thr_elev+1800*0.025), pz(missed_c, thr_elev+12000*.025), pz(missed_d, thr_elev+12000*0.025), pz(missed_e, thr_elev+1800*0.025), pz(missed_f, thr_elev)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['missed approach surface'])
    pr.addFeatures([seg])

    # Add Transition Left 1 
    exterior_ring = [pz(as2_d, thr_elev+300), pz(as1_d, thr_elev+60), pz(transition_e1_left, thr_elev+300)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - left 1'])
    pr.addFeatures([seg])

    # Add Transition Left 2 
    exterior_ring = [pz(as1_d, thr_elev+60), pz(transition_e1_left, thr_elev+300), pz(transition_e2_left, thr_elev+300), pz(gs_d, thr_elev)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - left 2'])
    pr.addFeatures([seg])

    # Add Transition Left 3 
    exterior_ring = [pz(transition_e2_left, thr_elev+300), pz(gs_d, thr_elev), pz(gs_c, thr_elev), pz(missed_e, thr_elev+1800*0.025), pz(transition_e3_left, thr_elev+300)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - left 3'])
    pr.addFeatures([seg])

    # Add Transition Left 4 
    exterior_ring = [pz(missed_e, thr_elev+1800*0.025), pz(missed_d, thr_elev+12000*.025), pz(transition_e3_left, thr_elev+300)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - left 4'])
    pr.addFeatures([seg])

    # Add Transition Right 1 
    exterior_ring = [pz(as2_a, thr_elev+300), pz(as1_a, thr_elev+60), pz(transition_e1_right, thr_elev+300)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - right 1'])
    pr.addFeatures([seg])

    # Add Transition Right 2 
    exterior_ring = [pz(as1_a, thr_elev+60), pz(transition_e1_right, thr_elev+300), pz(transition_e2_right, thr_elev+300), pz(gs_a, thr_elev)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - right 2'])
    pr.addFeatures([seg])

    # Add Transition Right 3 
    exterior_ring = [pz(transition_e2_right, thr_elev+300), pz(transition_e3_right, thr_elev+300), pz(missed_b, thr_elev+1800*0.025), pz(gs_b, thr_elev), pz(gs_a, thr_elev)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - right 3'])
    pr.addFeatures([seg])

    # Add Transition Right 4 
    exterior_ring = [pz(missed_b, thr_elev+1800*0.025), pz(missed_c, thr_elev+12000*.025), pz(transition_e3_right, thr_elev+300)]
    seg = QgsFeature()
    seg.setGeometry(QgsPolygon(QgsLineString(exterior_ring), rings=[]))
    seg.setAttributes(['transition surface - right 4'])
    pr.addFeatures([seg])
    
    # Update layer extents and add to project
    v_layer.updateExtents()
    QgsProject.instance().addMapLayers([v_layer])
    
    # Zoom to layer
    v_layer.selectAll()
    canvas = iface.mapCanvas()
    canvas.zoomToSelected(v_layer)
    v_layer.removeSelection()
    
    # Set scale
    sc = canvas.scale()
    if sc < 20000:
        sc = 20000
    canvas.zoomScale(sc)
    
    # Export to KML if requested
    kml_path = None
    if export_kml and output_dir:
        # Define the file path for the KML export
        kml_path = os.path.join(output_dir, 'Basic_ILS_Surfaces_layer.kml')
        
        # Export to KML
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        error = QgsVectorFileWriter.writeAsVectorFormat(
            v_layer,
            kml_path,
            'utf-8',
            crs,
            'KML',
            layerOptions=['MODE=2']  # Ensure Z values are included
        )
        
        # Check for errors
        if error[0] != QgsVectorFileWriter.NoError:
            iface.messageBar().pushMessage(
                "Error", 
                f"Error exporting to KML: {error[1]}", 
                level=Qgis.Critical
            )
        else:
            # Correct KML structure
            correct_kml_structure(kml_path)
            iface.messageBar().pushMessage(
                "Success", 
                f"Exported Basic ILS Surfaces to: {kml_path}", 
                level=Qgis.Success
            )
    
    # Return results
    return {
        'layer': v_layer,
        'kml_path': kml_path
    }

def correct_kml_structure(kml_file_path):
    """
    Correct the KML structure to ensure proper display in Google Earth
    
    :param kml_file_path: Path to the KML file
    """
    with open(kml_file_path, 'r') as file:
        kml_content = file.read()

    # Correct the structure to ensure altitudeMode is inside the <Polygon> tag
    kml_content = kml_content.replace('<Polygon>', '<Polygon>\n  <altitudeMode>absolute</altitudeMode>')

    # Add symbology for the polygon (LineStyle and PolyStyle)
    line_color_kml = 'ff0000ff'  # Red line color (RGBA)
    fill_color_kml = 'ff00007F'  # Semi-transparent red fill (50% opacity)

    style_kml = f'''
    <Style id="style1">
        <LineStyle>
            <color>{line_color_kml}</color>
            <width>2</width>
        </LineStyle>
        <PolyStyle>
            <fill>1</fill>
            <color>{fill_color_kml}</color>
        </PolyStyle>
    </Style>
    '''

    # Insert style definition into the <Document> tag
    kml_content = kml_content.replace('<Document>', f'<Document>{style_kml}')

    # Replace the empty <styleUrl> tags with a reference to the style
    kml_content = kml_content.replace('<styleUrl>#</styleUrl>', '<styleUrl>#style1</styleUrl>')

    # Write the corrected KML content back to the file
    with open(kml_file_path, 'w') as file:
        file.write(kml_content)