# -*- coding: utf-8 -*-
"""
Straight In NPA Surface Generator
"""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsPointXY, QgsWkbTypes, QgsField, QgsFields, QgsPoint,
    QgsLineString, QgsPolygon, QgsVectorFileWriter
)
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor
from qgis.core import Qgis
from qgis.utils import iface
import math
import os
import datetime
import json
from ..utils import get_selected_feature

def calculate_vss_straight(iface, point_layer, runway_layer, params):
    """
    Create Straight In NPA Surface
    
    :param iface: QGIS interface
    :param point_layer: Point layer with the reference point (WGS84)
    :param runway_layer: Runway layer (projected CRS)
    :param params: Dictionary with calculation parameters
    :return: Dictionary with results
    """
    # Extract parameters - convert string values to float for calculations
    rwy_width = float(params.get('rwy_width', 45))
    thr_elev_raw = float(params.get('thr_elev', 0))
    strip_width = float(params.get('strip_width', 140))
    OCH_raw = float(params.get('OCH', 100))
    RDH_raw = float(params.get('RDH', 15))
    VPA = float(params.get('VPA', 3.0))
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', os.path.expanduser('~'))
    
    # Get units
    thr_elev_unit = params.get('thr_elev_unit', 'm')
    OCH_unit = params.get('OCH_unit', 'm')
    RDH_unit = params.get('RDH_unit', 'm')
    
    # Convert units to meters if needed
    thr_elev = thr_elev_raw if thr_elev_unit == 'm' else thr_elev_raw * 0.3048
    OCH = OCH_raw if OCH_unit == 'm' else OCH_raw * 0.3048
    RDH = RDH_raw if RDH_unit == 'm' else RDH_raw * 0.3048
    
    # Create a parameters dictionary for JSON storage - store original values
    parameters_dict = {
        'rwy_width': str(rwy_width),
        'thr_elev': str(thr_elev_raw),
        'strip_width': str(strip_width),
        'OCH': str(OCH_raw),
        'RDH': str(RDH_raw),
        'VPA': str(VPA),
        'thr_elev_unit': thr_elev_unit,
        'OCH_unit': OCH_unit,
        'RDH_unit': RDH_unit,
        'calculation_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'calculation_type': 'Straight In NPA'
    }
    
    # Convert parameters to JSON string
    parameters_json = json.dumps(parameters_dict)
    
    # Log the units being used
    iface.messageBar().pushMessage(
        "Info", 
        f"Using units - Threshold Elevation: {thr_elev_unit}, OCH: {OCH_unit}, RDH: {RDH_unit}", 
        level=Qgis.Info
    )
    
    # Check if layers exist
    if not point_layer or not runway_layer:
        iface.messageBar().pushMessage("Error", "Point or runway layer not provided", level=Qgis.Critical)
        return None
    
    # Usar la función auxiliar para obtener las features
    def show_error(message):
        iface.messageBar().pushMessage("Error", message, level=Qgis.Critical)
    
    point_feature = get_selected_feature(point_layer, show_error)
    if not point_feature:
        return None
    
    runway_feature = get_selected_feature(runway_layer, show_error)
    if not runway_feature:
        return None
    
    # Get the reference point (in WGS84)
    point_geom = point_feature.geometry().asPoint()
    
    # Get the runway line (in projected system)
    runway_geom = runway_feature.geometry().asPolyline()
    
    # Get map CRS
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Transform the point to projected CRS
    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")  # WGS84
    dest_crs = runway_layer.crs()
    transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    
    new_geom = transform.transform(point_geom)
    
    # Calculate azimuth
    start_point = QgsPoint(runway_geom[-1])
    end_point = QgsPoint(runway_geom[0])
    angle0 = start_point.azimuth(end_point) + 180
    azimuth = angle0 - 180
    
    # Function to convert from PointXY and add Z value
    def pz(point, z):
        cPoint = QgsPoint(point)
        cPoint.addZValue()
        cPoint.setZ(z)
        return cPoint
    
    # Calculate VSS parameters
    D_VSS = OCH / math.tan(math.radians(VPA - 1.12))
    
    # VSS point definition
    VSS_s = new_geom.project(60, azimuth)
    VSS_a = VSS_s.project(strip_width/2, azimuth-90)
    VSS_e = VSS_s.project(D_VSS, azimuth)
    VSS_b = VSS_e.project(D_VSS*0.15+strip_width/2, azimuth-90)
    VSS_c = VSS_e.project(D_VSS*0.15+strip_width/2, azimuth+90)
    VSS_d = VSS_s.project(strip_width/2, azimuth+90)
    
    # Create VSS layer
    vss_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, "Straight In - VSS area", "memory")
    vss_provider = vss_layer.dataProvider()
    
    # Add fields
    vss_provider.addAttributes([
        QgsField('id', QVariant.Int),
        QgsField('description', QVariant.String),
        QgsField('parameters', QVariant.String)  # New field for parameters
    ])
    vss_layer.updateFields()
    
    # Create VSS feature
    vss_base = [
        pz(VSS_a, thr_elev),
        pz(VSS_b, (thr_elev + D_VSS * math.tan(math.radians(VPA - 1.12)))),
        pz(VSS_c, (thr_elev + D_VSS * math.tan(math.radians(VPA - 1.12)))),
        pz(VSS_d, thr_elev)
    ]
    vss_feature = QgsFeature()
    vss_feature.setGeometry(QgsPolygon(QgsLineString(vss_base)))
    vss_feature.setAttributes([1, 'VSS area', parameters_json])  # Include parameters JSON
    vss_provider.addFeatures([vss_feature])
    
    # Style VSS layer
    vss_layer.renderer().symbol().setColor(QColor(200, 0, 255, 50))  # RGBA
    vss_layer.renderer().symbol().symbolLayer(0).setStrokeColor(QColor(200, 0, 255))
    vss_layer.renderer().symbol().symbolLayer(0).setStrokeWidth(0.7)
    vss_layer.triggerRepaint()
    
    # Calculate OCS parameters
    OCS_length = (OCH - RDH) / math.tan(math.radians(VPA))
    OCS_E_width = OCS_length * math.tan(math.radians(2)) + 120
    
    # OCS point definition
    OCS_start = new_geom
    OCS_a = OCS_start.project(30 + rwy_width/2, azimuth-90)
    OCS_e = OCS_start.project(OCS_length, azimuth)
    OCS_b = OCS_e.project(OCS_E_width, azimuth-90)
    OCS_c = OCS_e.project(OCS_E_width, azimuth+90)
    OCS_d = OCS_start.project(30 + rwy_width/2, azimuth+90)
    
    # Create OCS layer
    ocs_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, "Straight In - OCS area", "memory")
    ocs_provider = ocs_layer.dataProvider()
    
    # Add fields
    ocs_provider.addAttributes([
        QgsField('id', QVariant.Int),
        QgsField('description', QVariant.String),
        QgsField('parameters', QVariant.String)  # New field for parameters
    ])
    ocs_layer.updateFields()
    
    # Create OCS feature
    ocs_base = [
        pz(OCS_a, thr_elev),
        pz(OCS_b, (thr_elev + OCS_length * math.tan(math.radians(VPA - 1)))),
        pz(OCS_c, (thr_elev + OCS_length * math.tan(math.radians(VPA - 1)))),
        pz(OCS_d, thr_elev)
    ]
    ocs_feature = QgsFeature()
    ocs_feature.setGeometry(QgsPolygon(QgsLineString(ocs_base)))
    ocs_feature.setAttributes([1, 'OCS area', parameters_json])  # Include parameters JSON
    ocs_provider.addFeatures([ocs_feature])
    
    # Style OCS layer
    ocs_layer.renderer().symbol().setColor(QColor(255, 146, 0, 50))  # RGBA
    ocs_layer.renderer().symbol().symbolLayer(0).setStrokeColor(QColor(255, 146, 0))
    ocs_layer.renderer().symbol().symbolLayer(0).setStrokeWidth(0.7)
    ocs_layer.triggerRepaint()
    
    # Add layers to the project
    QgsProject.instance().addMapLayers([vss_layer, ocs_layer])
    
    # Export to KML if requested
    result = {
        'vss_layer': vss_layer,
        'ocs_layer': ocs_layer
    }
    
    if export_kml:
        # Get current timestamp for unique filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define KML export paths
        vss_export_path = os.path.join(output_dir, f'vss_layer_{timestamp}.kml')
        ocs_export_path = os.path.join(output_dir, f'ocs_layer_{timestamp}.kml')
        
        # Export to KML
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        # Export VSS layer
        vss_error = QgsVectorFileWriter.writeAsVectorFormat(
            vss_layer,
            vss_export_path,
            'utf-8',
            crs,
            'KML',
            layerOptions=['MODE=2']
        )
        
        # Export OCS layer
        ocs_error = QgsVectorFileWriter.writeAsVectorFormat(
            ocs_layer,
            ocs_export_path,
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
            
            # Add style
            style_kml = '''
            <Style id="style1">
                <LineStyle>
                    <color>ff0000ff</color>
                    <width>2</width>
                </LineStyle>
                <PolyStyle>
                    <fill>1</fill>
                    <color>ff00007F</color>
                </PolyStyle>
            </Style>
            '''
            
            kml_content = kml_content.replace('<Document>', f'<Document>{style_kml}')
            kml_content = kml_content.replace('<styleUrl>#</styleUrl>', '<styleUrl>#style1</styleUrl>')
            
            with open(kml_file_path, 'w') as file:
                file.write(kml_content)
        
        # Apply corrections to KML files
        if vss_error[0] == QgsVectorFileWriter.NoError:
            correct_kml_structure(vss_export_path)
            result['vss_path'] = vss_export_path
        
        if ocs_error[0] == QgsVectorFileWriter.NoError:
            correct_kml_structure(ocs_export_path)
            result['ocs_path'] = ocs_export_path
    
    # Zoom to appropriate scale
    sc = iface.mapCanvas().scale()
    if sc < 20000:
        sc = 20000
    iface.mapCanvas().zoomScale(sc)
    
    return result

def copy_parameters_table(params):
    """Generate formatted table for VSS Straight parameters"""
    from ..utils import format_parameters_table
    
    params_dict = {
        'runway_details': {
            'rwy_width': {'value': params.get('rwy_width', 45), 'unit': 'm'},
            'thr_elev': {'value': params.get('thr_elev', 0), 'unit': params.get('thr_elev_unit', 'm')},
            'strip_width': {'value': params.get('strip_width', 140), 'unit': 'm'}
        },
        'approach_params': {
            'OCH': {'value': params.get('OCH', 100), 'unit': params.get('OCH_unit', 'm')},
            'RDH': {'value': params.get('RDH', 15), 'unit': params.get('RDH_unit', 'm')},
            'VPA': {'value': params.get('VPA', 3.0), 'unit': '°'}
        }
    }

    sections = {
        'rwy_width': 'Runway Data',
        'thr_elev': 'Runway Data',
        'strip_width': 'Runway Data',
        'OCH': 'Approach Parameters',
        'RDH': 'Approach Parameters',
        'VPA': 'Approach Parameters'
    }

    return format_parameters_table(
        "QPANSOPY VSS STRAIGHT PARAMETERS",
        params_dict,
        sections
    )