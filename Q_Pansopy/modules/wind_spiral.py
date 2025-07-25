# -*- coding: utf-8 -*-
"""
Wind Spiral Generator
"""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsPointXY, QgsWkbTypes, QgsField, QgsFields, QgsPoint,
    QgsLineString, QgsPolygon, QgsVectorFileWriter, QgsCircularString
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import Qgis
from qgis.utils import iface
import math
import os
import datetime
import json
from ..utils import get_selected_feature

def ISA_temperature(adElev, tempRef):
    """Calculate ISA temperature and deviation"""
    tempISA = 15 - 0.00198 * adElev
    deltaISA = tempRef - tempISA
    return (adElev, tempRef, tempISA, deltaISA)

def tas_calculation(ias, altitude, var, bank_angle):
    """Aviation Calculations for Wind Spiral - Original Formula
    
    :param ias: Indicated Air Speed in knots
    :param altitude: Altitude in feet
    :param var: Temperature variation from ISA
    :param bank_angle: Bank angle in degrees
    :return: Tuple of (k, tas, rate_of_turn, radius_of_turn, w)
    """
    k = 171233*(((288+var)-0.00198*altitude)**0.5)/(288-0.00198*altitude)**2.628
    tas = k*ias
    rate_of_turn = (3431*math.tan(math.radians(bank_angle)))/(math.pi*tas)
    radius_of_turn = tas/(20*math.pi*rate_of_turn)
    w = 30  # Wind speed
    return k, tas, rate_of_turn, radius_of_turn, w

def calculate_wind_spiral(iface, point_layer, reference_layer, params):
    """
    Create Wind Spiral
    
    :param iface: QGIS interface
    :param point_layer: Point layer with the reference point
    :param reference_layer: Reference line layer (runway or approach track)
    :param params: Dictionary with calculation parameters
    :return: Dictionary with results
    """
    # Extraer parámetros
    IAS = float(params.get('IAS', 205))
    altitude = float(params.get('altitude', 800))
    altitude_unit = params.get('altitude_unit', 'ft')
    if altitude_unit == 'm':
        altitude = altitude * 3.28084
    bankAngle = float(params.get('bankAngle', 15))
    w = float(params.get('w', 30))
    turn_direction = params.get('turn_direction', 'R')
    show_points = params.get('show_points', True)
    export_kml = params.get('export_kml', True)
    output_dir = params.get('output_dir', os.path.expanduser('~'))

    # Get aerodrome elevation and temperature reference from params
    adElev = float(params.get('adElev', 0))
    adElev_unit = params.get('adElev_unit', 'ft')
    if adElev_unit == 'm':
        adElev = adElev * 3.28084
    tempRef = float(params.get('tempRef', 15))
    
    # Calculate ISA temperature and deviation
    valueISA = ISA_temperature(adElev, tempRef)
    isa_var = valueISA[3]  # Use the calculated ISA deviation
    
    # Create a parameters dictionary for JSON storage
    parameters_dict = {
        'adElev': str(adElev),
        'adElev_unit': adElev_unit,
        'tempRef': str(tempRef),
        'IAS': str(IAS),
        'altitude': str(altitude),
        'altitude_unit': altitude_unit,
        'bankAngle': str(bankAngle),
        'w': str(w),
        'isa_calculated': str(round(valueISA[2], 2)),
        'isa_var': str(round(isa_var, 2)),
        'turn_direction': turn_direction,
        'calculation_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'calculation_type': 'Wind Spiral'
    }
    parameters_json = json.dumps(parameters_dict)

    # Log ISA calculation results
    iface.messageBar().pushMessage(
        "Info", 
        f"ISA Temperature: {round(valueISA[2], 2)}°C, ISA Deviation: {round(isa_var, 2)}°C", 
        level=Qgis.Info
    )

    # Set turn direction
    if turn_direction == "L":
        side = 90
        d = (30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330)  # NM
    else:  # Default to right turn
        side = -90
        d = (-30, -60, -90, -120, -150, -180, -210, -240, -270, -300, -330)  # NM

    # Calculate TAS and turn parameters using original formula
    values = tas_calculation(IAS, altitude, isa_var, bankAngle)
    r_turn = values[3]
    
    # Calculate drift angle - Original Formula
    drift_angle = math.asin(values[4]/values[1])
    
    # Calculate wind spiral radii - Original Formula
    wind_spiral_radius = {}
    for i in range(30, 390, 30):
        windspiral = (i/values[2])*(values[4]/3600)
        wind_spiral_radius["radius_" + str(i)] = windspiral
    
    # Get map CRS
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    
    # Check if layers exist
    if not point_layer or not reference_layer:
        iface.messageBar().pushMessage("Error", "Point or reference layer not provided", level=Qgis.Critical)
        return None
    
    # Usar la función auxiliar para obtener las features
    def show_error(message):
        iface.messageBar().pushMessage("Error", message, level=Qgis.Critical)
    
    point_feature = get_selected_feature(point_layer, show_error)
    if not point_feature:
        return None
    
    reference_feature = get_selected_feature(reference_layer, show_error)
    if not reference_feature:
        return None
    
    # Get reference line geometry
    geom = reference_feature.geometry().asPolyline()
    start_point = QgsPoint(geom[-1])
    end_point = QgsPoint(geom[0])
    angle0 = start_point.azimuth(end_point) + 180
    
    # Initial true azimuth data
    azimuth = angle0
    
    # Get point geometry
    p_geom = point_feature.geometry().asPoint()
    
    # Initialize points list for circular string
    u = []
    u.append(QgsPoint(p_geom))
    
    # Create point layer if requested
    if show_points:
        v_layer = QgsVectorLayer("Point?crs=" + map_srid, "Wind Spiral Points", "memory")
        myField = QgsField('spiral', QVariant.String)
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()
        pr = v_layer.dataProvider()
        
        # Calculate center point
        angle = 90 - azimuth + side  # left/right
        bearing = math.radians(azimuth)
        angle = math.radians(angle)
        dist_x, dist_y = (r_turn * 1852 * math.cos(angle), r_turn * 1852 * math.sin(angle))
        xc, yc = (p_geom.x() + dist_x, p_geom.y() + dist_y)
        line_start = QgsPointXY(xc, yc)
        
        # Add center point
        seg = QgsFeature()
        seg.setGeometry(QgsGeometry.fromPointXY(line_start))
        seg.setAttributes(['Wind Spiral Center'])
        pr.addFeatures([seg])
        
        # Get angle from Center to P
        connect_line = QgsGeometry.fromPolyline([QgsPoint(line_start), QgsPoint(p_geom)])
        start_point_C = QgsPoint(connect_line.asPolyline()[0])
    else:
        # Calculate center point without creating layer
        angle = 90 - azimuth + side
        bearing = math.radians(azimuth)
        angle = math.radians(angle)
        dist_x, dist_y = (r_turn * 1852 * math.cos(angle), r_turn * 1852 * math.sin(angle))
        xc, yc = (p_geom.x() + dist_x, p_geom.y() + dist_y)
        line_start = QgsPointXY(xc, yc)
        start_point_C = QgsPoint(line_start)
    
    # Calculate points for wind spiral
    for i in d:
        e = list(wind_spiral_radius.values())[int(abs(i) / 30) - 1]
        
        bearing = azimuth
        angle = 90 - bearing + i - side
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        
        # Calculate point on spiral
        dist_x, dist_y = ((r_turn + e) * 1852 * math.cos(angle), (r_turn + e) * 1852 * math.sin(angle))
        bx1, by2 = (start_point_C.x() + dist_x, start_point_C.y() + dist_y)
        line_start1 = QgsPointXY(bx1, by2)
        
        # Calculate point on circle
        dist_x, dist_y = (r_turn * 1852 * math.cos(angle), r_turn * 1852 * math.sin(angle))
        cx1, cy2 = (start_point_C.x() + dist_x, start_point_C.y() + dist_y)
        line_start2 = QgsPointXY(cx1, cy2)
        
        # Calculate drift point
        dist_xd, dist_yd = (e * 1852 * math.cos(angle - drift_angle * (side / 90)), 
                          e * 1852 * math.sin(angle - drift_angle * (side / 90)))
        dx1, dy2 = (cx1 + dist_xd, cy2 + dist_yd)
        line_startd = QgsPointXY(dx1, dy2)
        
        # Add point to circular string
        u.append(QgsPoint(line_startd))
        
        # Add drift point to point layer if requested
        if show_points:
            seg = QgsFeature()
            seg.setGeometry(QgsGeometry.fromPointXY(line_startd))
            seg.setAttributes(['drift_angle'])
            pr.addFeatures([seg])
    
    # Create line layer for wind spiral curve
    layer_name = f"Wind_Spiral_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    pv_layer = QgsVectorLayer("LineString?crs=" + map_srid, layer_name, "memory")
    myField = QgsField('parameters', QVariant.String)
    pv_layer.dataProvider().addAttributes([myField])
    pv_layer.updateFields()
    prv = pv_layer.dataProvider()
    
    # Create circular string geometry
    cString = QgsCircularString()
    cString.setPoints(u)
    geom_cString = QgsGeometry(cString)
    
    # Add feature to line layer
    seg = QgsFeature()
    seg.setGeometry(geom_cString)
    seg.setAttributes([parameters_json])
    prv.addFeatures([seg])
    
    # Update layer extents
    pv_layer.updateExtents()
    
    # Style line layer
    pv_layer.renderer().symbol().setColor(QColor("green"))
    pv_layer.renderer().symbol().setWidth(0.5)
    pv_layer.triggerRepaint()
    
    # Add layers to the project
    QgsProject.instance().addMapLayer(pv_layer)
    
    if show_points:
        v_layer.updateExtents()
        QgsProject.instance().addMapLayer(v_layer)
    
    # Export to KML if requested
    result = {
        'spiral_layer': pv_layer
    }
    
    if show_points:
        result['points_layer'] = v_layer
    
    if export_kml:
        # Get current timestamp for unique filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define KML export path
        spiral_export_path = os.path.join(output_dir, f'wind_spiral_{timestamp}.kml')
        
        # Export to KML
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        # Export spiral layer
        spiral_error = QgsVectorFileWriter.writeAsVectorFormat(
            pv_layer,
            spiral_export_path,
            'utf-8',
            crs,
            'KML',
            layerOptions=['MODE=2']
        )
        
        # Apply corrections to KML file
        if spiral_error[0] == QgsVectorFileWriter.NoError:
            result['spiral_path'] = spiral_export_path
    
    # Show success message
    iface.messageBar().pushMessage("QPANSOPY:", "Wind Spiral created successfully", level=Qgis.Success)
    
    return result

def copy_parameters_table(params):
    """Generate formatted table for Wind Spiral parameters"""
    from ..utils import format_parameters_table
    
    # Calculate ISA values if adElev and tempRef are provided
    adElev = float(params.get('adElev', 0))
    tempRef = float(params.get('tempRef', 15))
    valueISA = ISA_temperature(adElev, tempRef)
    
    params_dict = {
        'airport_data': {
            'aerodrome_elevation': {'value': params.get('adElev', 0), 'unit': params.get('adElev_unit', 'ft')},
            'temperature_reference': {'value': params.get('tempRef', 15), 'unit': '°C'},
            'isa_calculated': {'value': round(valueISA[2], 2), 'unit': '°C'},
            'isa_variation': {'value': round(valueISA[3], 2), 'unit': '°C'}
        },
        'flight_params': {
            'IAS': {'value': params.get('IAS', 205), 'unit': 'kt'},
            'altitude': {'value': params.get('altitude', 800), 'unit': params.get('altitude_unit', 'ft')},
            'bank_angle': {'value': params.get('bankAngle', 15), 'unit': '°'}
        },
        'wind_data': {
            'wind_speed': {'value': params.get('w', 30), 'unit': 'kt'},
            'turn_direction': {'value': params.get('turn_direction', 'R'), 'unit': ''}
        }
    }

    sections = {
        'aerodrome_elevation': 'Airport Data',
        'temperature_reference': 'Airport Data',
        'isa_calculated': 'Airport Data',
        'isa_variation': 'Airport Data',
        'IAS': 'Flight Parameters',
        'altitude': 'Flight Parameters',
        'bank_angle': 'Flight Parameters',
        'wind_speed': 'Wind Data',
        'turn_direction': 'Wind Data'
    }

    return format_parameters_table(
        "QPANSOPY WIND SPIRAL PARAMETERS",
        params_dict,
        sections
    )