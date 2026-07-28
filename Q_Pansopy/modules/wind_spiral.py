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
import math
import os
import datetime
import json
from ..utils import get_selected_feature, fix_kml_altitude_mode


def ISA_temperature(adElev, tempRef):
    """Calculate ISA temperature and deviation"""
    tempISA = 15 - 0.00198 * adElev
    deltaISA = tempRef - tempISA
    return (adElev, tempRef, tempISA, deltaISA)


def tas_calculation(ias, altitude, var, bank_angle, wind_speed=30):
    """Aviation Calculations for Wind Spiral - Original Formula
    
    :param ias: Indicated Air Speed in knots
    :param altitude: Altitude in feet
    :param var: Temperature variation from ISA
    :param bank_angle: Bank angle in degrees
    :param wind_speed: Wind speed in knots (default 30)
    :return: Tuple of (k, tas, rate_of_turn, radius_of_turn, w)
    """
    k = 171233*(((288+var)-0.00198*altitude)**0.5)/(288-0.00198*altitude)**2.628
    tas = k*ias
    rate_of_turn = (3431*math.tan(math.radians(bank_angle)))/(math.pi*tas)
    radius_of_turn = tas/(20*math.pi*rate_of_turn)
    w = wind_speed
    return k, tas, rate_of_turn, radius_of_turn, w


def build_wind_spiral_points(p_geom, azimuth, IAS, altitude, isa_var, bank_angle,
                              wind_speed, turn_direction='R'):
    """
    Pure geometry builder for the wind spiral curve (no QGIS layers/project
    side effects) — shared by the real calculation and the live preview.

    :param p_geom: Reference point geometry (QgsPoint/QgsPointXY, map CRS)
    :param azimuth: True azimuth of the reference track, in degrees
    :param IAS: Indicated Air Speed in knots
    :param altitude: Altitude in feet
    :param isa_var: ISA temperature deviation in degrees C
    :param bank_angle: Bank angle in degrees
    :param wind_speed: Wind speed in knots
    :param turn_direction: 'R' or 'L'
    :return: (u_points, center_point) where u_points is a list of QgsPoint
        starting at p_geom followed by one drift point per 30 deg step
        (used both for the circular-string curve and the optional
        'show points' marker layer), and center_point is a QgsPoint for the
        turn's center.
    """
    if turn_direction == "L":
        side = 90
        d = (30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330)  # NM
    else:  # Default to right turn
        side = -90
        d = (-30, -60, -90, -120, -150, -180, -210, -240, -270, -300, -330)  # NM

    values = tas_calculation(IAS, altitude, isa_var, bank_angle, wind_speed=wind_speed)
    r_turn = values[3]

    # Calculate drift angle - Original Formula
    drift_angle = math.asin(values[4] / values[1])

    # Calculate wind spiral radii - Original Formula
    wind_spiral_radius = {}
    for i in range(30, 390, 30):
        windspiral = (i / values[2]) * (values[4] / 3600)
        wind_spiral_radius["radius_" + str(i)] = windspiral

    u = [QgsPoint(p_geom)]

    # Calculate center point
    angle = 90 - azimuth + side  # left/right
    angle = math.radians(angle)
    dist_x, dist_y = (r_turn * 1852 * math.cos(angle), r_turn * 1852 * math.sin(angle))
    xc, yc = (p_geom.x() + dist_x, p_geom.y() + dist_y)
    center_point = QgsPoint(xc, yc)

    # Calculate points for wind spiral
    for i in d:
        e = list(wind_spiral_radius.values())[int(abs(i) / 30) - 1]

        angle = 90 - azimuth + i - side
        angle = math.radians(angle)

        # Calculate point on circle
        dist_x, dist_y = (r_turn * 1852 * math.cos(angle), r_turn * 1852 * math.sin(angle))
        cx1, cy2 = (center_point.x() + dist_x, center_point.y() + dist_y)

        # Calculate drift point
        dist_xd, dist_yd = (e * 1852 * math.cos(angle - drift_angle * (side / 90)),
                          e * 1852 * math.sin(angle - drift_angle * (side / 90)))
        dx1, dy2 = (cx1 + dist_xd, cy2 + dist_yd)

        u.append(QgsPoint(dx1, dy2))

    return u, center_point


def build_wind_spiral_geometry(p_geom, azimuth, IAS, altitude, isa_var, bank_angle,
                                wind_speed, turn_direction='R'):
    """QgsGeometry (circular string) for live preview / rubber band use."""
    u, _ = build_wind_spiral_points(p_geom, azimuth, IAS, altitude, isa_var,
                                     bank_angle, wind_speed, turn_direction)
    cString = QgsCircularString()
    cString.setPoints(u)
    return QgsGeometry(cString)


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

    # ISA deviation comes directly from the dockwidget's ISA Variation field
    # (params['isaVar']) — adElev/tempRef are legacy inputs no longer collected
    # by the Wind Spiral UI; they're only used by the standalone ISA Calculator
    # dialog, whose result is what populates isaVar.
    isa_var = float(params.get('isaVar', 0))

    # Create a parameters dictionary for JSON storage
    parameters_dict = {
        'IAS': str(IAS),
        'altitude': str(altitude),
        'altitude_unit': altitude_unit,
        'bankAngle': str(bankAngle),
        'w': str(w),
        'isa_var': str(round(isa_var, 2)),
        'turn_direction': turn_direction,
        'calculation_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'calculation_type': 'Wind Spiral'
    }
    parameters_json = json.dumps(parameters_dict)

    # Log ISA deviation used in the calculation
    iface.messageBar().pushMessage(
        "Info",
        f"ISA Deviation used: {round(isa_var, 2)}°C",
        level=Qgis.Info
    )

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

    # Build the spiral curve points (shared pure geometry builder, also used
    # by the dockwidget's live rubber-band preview)
    u, center_point = build_wind_spiral_points(
        p_geom, azimuth, IAS, altitude, isa_var, bankAngle, w, turn_direction)

    # Create point layer if requested
    if show_points:
        v_layer = QgsVectorLayer("Point?crs=" + map_srid, "Wind Spiral Points", "memory")
        myField = QgsField('spiral', QVariant.String)
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()
        pr = v_layer.dataProvider()

        # Add center point
        seg = QgsFeature()
        seg.setGeometry(QgsGeometry.fromPoint(center_point))
        seg.setAttributes(['Wind Spiral Center'])
        pr.addFeatures([seg])

        # Add each drift point
        for drift_point in u[1:]:
            seg = QgsFeature()
            seg.setGeometry(QgsGeometry.fromPoint(drift_point))
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
            fix_kml_altitude_mode(spiral_export_path)
            result['spiral_path'] = spiral_export_path

    # Show success message
    iface.messageBar().pushMessage("QPANSOPY:", "Wind Spiral created successfully", level=Qgis.Success)

    return result


def copy_parameters_table(params, as_html=False):
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
        sections,
        as_html=as_html
    )
