"""Overhead VOR/NDB fix tolerance (ICAO Doc 8168, Figures I-2-2-3/4)."""

import math
import os
from datetime import datetime

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsField, QgsGeometry, QgsPalLayerSettings, QgsPointXY, QgsProject,
    QgsVectorFileWriter, QgsVectorLayer, QgsVectorLayerSimpleLabeling,
)


NM_METRES = 1852.0
FT_METRES = 0.3048
_ANGLES = {'VOR': (50.0, 5.0), 'NDB': (40.0, 15.0)}


def build_overhead_coordinates(station, inbound, height_ft, navaid_type):
    """Return polygon, cone, and named points in projected metre coordinates.

    ``inbound`` points toward the facility. The entry vertices are offset
    ±q from track; the exit vertices follow lines diverging by 5 degrees.
    The end arcs are sampled on the cone circle, not convex-hulled.
    """
    if navaid_type not in _ANGLES:
        raise ValueError('Navaid must be VOR or NDB')
    if not math.isfinite(height_ft) or height_ft <= 0:
        raise ValueError('Aircraft altitude must exceed station elevation')
    dx, dy = inbound
    norm = math.hypot(dx, dy)
    if not math.isfinite(norm) or norm < 1e-9:
        raise ValueError('Track has no usable inbound direction')
    ux, uy = dx / norm, dy / norm
    vx, vy = -uy, ux
    cone_angle, entry_angle = _ANGLES[navaid_type]
    radius = 0.164 * (height_ft / 1000.0) * math.tan(
        math.radians(cone_angle)) * NM_METRES
    q = radius * math.sin(math.radians(entry_angle))
    entry_x = -math.sqrt(radius * radius - q * q)
    slope = math.tan(math.radians(5.0))

    def local(x, y):
        return (station[0] + x * ux + y * vx,
                station[1] + x * uy + y * vy)

    # The first line/circle intersection is the entry point; the second is
    # obtained by substituting p + t*d in x²+y²=r².
    def exit_point(sign):
        y = sign * q
        m = sign * slope
        t = -2.0 * (entry_x + y * m) / (1.0 + m * m)
        if t <= 0:
            raise ValueError('Overhead construction has no exit intersection')
        return (entry_x + t, y + t * m)

    upper_exit = exit_point(1)
    lower_exit = exit_point(-1)
    upper_entry = (entry_x, q)
    lower_entry = (entry_x, -q)

    def clockwise_arc(start, end):
        a = math.atan2(start[1], start[0])
        b = math.atan2(end[1], end[0])
        while b >= a:
            b -= 2.0 * math.pi
        steps = max(2, math.ceil((a - b) / math.radians(2.0)))
        return [local(radius * math.cos(a + (b - a) * i / steps),
                      radius * math.sin(a + (b - a) * i / steps))
                for i in range(1, steps)]

    area = [local(*upper_entry), local(*upper_exit)]
    area.extend(clockwise_arc(upper_exit, lower_exit))
    area.extend([local(*lower_exit), local(*lower_entry)])
    area.extend(clockwise_arc(lower_entry, upper_entry))
    area.append(area[0])
    cone = [local(radius * math.cos(2 * math.pi * i / 180),
                  radius * math.sin(2 * math.pi * i / 180))
            for i in range(181)]
    prefix = 'V' if navaid_type == 'VOR' else 'N'
    points = {
        'Station': station,
        prefix + '1': local(*upper_exit),
        prefix + '2': local(*upper_entry),
        prefix + '3': local(*lower_exit),
        prefix + '4': local(*lower_entry),
    }
    return area, cone, points, radius / NM_METRES, q / NM_METRES


def inbound_from_track(station, vertices, reverse=False):
    """Choose the endpoint nearer the station; ties use digitized order."""
    if len(vertices) < 2:
        raise ValueError('Track must have at least two vertices')
    first = vertices[0]
    last = vertices[-1]
    d_first = math.hypot(station[0] - first[0], station[1] - first[1])
    d_last = math.hypot(station[0] - last[0], station[1] - last[1])
    tied = math.isclose(d_first, d_last, abs_tol=0.01)
    if d_first < d_last and not tied:
        direction = (first[0] - vertices[1][0],
                     first[1] - vertices[1][1])
    else:
        direction = (last[0] - vertices[-2][0],
                     last[1] - vertices[-2][1])
    if reverse:
        direction = (-direction[0], -direction[1])
    return direction, tied


def _selected_one(layer, name):
    selected = layer.selectedFeatures()
    if len(selected) != 1:
        raise ValueError('Select exactly one {0} feature'.format(name))
    return selected[0]


def _map_geometry(feature, layer, map_crs, project):
    geometry = QgsGeometry(feature.geometry())
    if geometry.isNull() or geometry.isEmpty():
        raise ValueError('Selected geometry is empty')
    geometry.transform(QgsCoordinateTransform(layer.crs(), map_crs, project))
    return geometry


def _polygon_layer(name, crs, ring, color):
    layer = QgsVectorLayer('Polygon', name, 'memory')
    layer.setCrs(crs)
    layer.dataProvider().addAttributes([QgsField('Name', QVariant.String)])
    layer.updateFields()
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPolygonXY([[QgsPointXY(*p) for p in ring]]))
    if not feature.geometry().isGeosValid():
        raise ValueError('Calculated tolerance geometry is invalid')
    feature.setAttributes([name])
    layer.dataProvider().addFeatures([feature])
    layer.updateExtents()
    layer.renderer().symbol().setColor(QColor(color))
    layer.renderer().symbol().setOpacity(0.35)
    return layer


def _points_layer(name, crs, points):
    layer = QgsVectorLayer('Point', name, 'memory')
    layer.setCrs(crs)
    layer.dataProvider().addAttributes([QgsField('Name', QVariant.String)])
    layer.updateFields()
    features = []
    for label, coordinates in points.items():
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*coordinates)))
        feature.setAttributes([label])
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    layer.updateExtents()
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = 'Name'
    layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
    layer.setLabelsEnabled(True)
    return layer


def _export_kml(layer, output_dir, stamp):
    path = os.path.join(output_dir, '{0}_{1}.kml'.format(layer.name(), stamp))
    result = QgsVectorFileWriter.writeAsVectorFormat(
        layer, path, 'utf-8', QgsCoordinateReferenceSystem('EPSG:4326'), 'KML')
    if result[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError('KML export failed: {0}'.format(result[1]))
    return path


def run_overhead_tolerance(iface, navaid_layer, track_layer, params=None):
    """Create selected VOR/NDB overhead tolerance and optional construction layers."""
    params = params or {}
    if ('aircraft_altitude_ft' not in params or
            'station_elevation_ft' not in params):
        raise ValueError('Enter aircraft altitude and station elevation')
    navaid_type = params.get('navaid_type', 'VOR')
    aircraft_ft = float(params['aircraft_altitude_ft'])
    station_ft = float(params['station_elevation_ft'])
    map_crs = iface.mapCanvas().mapSettings().destinationCrs()
    if map_crs.isGeographic() or map_crs.mapUnits() != Qgis.DistanceUnit.Meters:
        raise ValueError('Set the map canvas to a projected CRS in metres')
    project = QgsProject.instance()
    station_geom = _map_geometry(
        _selected_one(navaid_layer, 'navaid point'), navaid_layer, map_crs, project)
    track_geom = _map_geometry(
        _selected_one(track_layer, 'track line'), track_layer, map_crs, project)
    if station_geom.isMultipart() or station_geom.type() != Qgis.GeometryType.Point:
        raise ValueError('Navaid must be a single point')
    if track_geom.isMultipart() or track_geom.type() != Qgis.GeometryType.Line:
        raise ValueError('Track must be a single LineString')
    station_point = station_geom.asPoint()
    station = (station_point.x(), station_point.y())
    vertices = [(p.x(), p.y()) for p in track_geom.asPolyline()]
    direction, tied = inbound_from_track(
        station, vertices, params.get('reverse_direction', False))
    area, cone, points, radius_nm, q_nm = build_overhead_coordinates(
        station, direction, aircraft_ft - station_ft, navaid_type)
    layers = [_polygon_layer('{0}_Overhead_Tolerance'.format(navaid_type),
                             map_crs, area, '#f28c28')]
    if params.get('include_cone', False):
        layers.append(_polygon_layer('{0}_Cone_of_Silence'.format(navaid_type),
                                     map_crs, cone, '#6c86a0'))
    if params.get('include_points', False):
        layers.append(_points_layer('{0}_Construction_Points'.format(navaid_type),
                                    map_crs, points))
    for layer in layers:
        project.addMapLayer(layer)
    if tied:
        iface.messageBar().pushMessage(
            'QPANSOPY', 'Track endpoints equidistant: using digitized direction; '
            'check Invert direction if needed', level=Qgis.Warning)
    iface.messageBar().pushMessage(
        'QPANSOPY', '{0} overhead tolerance created (z={1:.3f} NM, q={2:.3f} NM)'.format(
            navaid_type, radius_nm, q_nm), level=Qgis.Success)
    if params.get('export_kml', False):
        output_dir = params.get('output_dir', '')
        try:
            if not os.path.isdir(output_dir):
                raise ValueError('Choose an existing KML output folder')
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            for layer in layers:
                _export_kml(layer, output_dir, stamp)
        except (OSError, RuntimeError, ValueError) as exc:
            iface.messageBar().pushMessage(
                'QPANSOPY', 'Layers created, but {0}'.format(exc), level=Qgis.Warning)
    return True
