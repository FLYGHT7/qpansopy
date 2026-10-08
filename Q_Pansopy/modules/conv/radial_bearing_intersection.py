"""Fix tolerance at the intersection of two radials or bearings.

Angles are ICAO Doc 8168, Volume II, Table I-2-2-1 system use accuracies
(2 SD). Geometry is calculated in a projected coordinate system in metres.
"""

import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional


NM_METRES = 1852.0
# (providing track guidance, not providing track guidance)
ACCURACY_DEGREES = {
    'VOR': (5.2, 4.5),
    'ILS': (2.4, 1.4),
    'NDB': (6.9, 6.2),
}


@dataclass(frozen=True)
class ConstructionLine:
    role: str
    navaid: str
    offset_deg: float
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class ToleranceResult:
    ring: tuple[tuple[float, float], ...]
    area_m2: float
    track_angle_deg: float
    cross_angle_deg: float
    early_nm: float
    late_nm: float
    construction_lines: tuple[ConstructionLine, ...] = ()


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _difference(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _rotate(vector, angle):
    cosine, sine = math.cos(angle), math.sin(angle)
    return (vector[0] * cosine - vector[1] * sine,
            vector[0] * sine + vector[1] * cosine)


def _line_intersection(origin_a, direction_a, origin_b, direction_b):
    determinant = _cross(direction_a, direction_b)
    if abs(determinant) < 1e-12:
        raise ValueError('The radial boundaries do not have a finite intersection')
    difference = _difference(origin_b, origin_a)
    distance_a = _cross(difference, direction_b) / determinant
    distance_b = _cross(difference, direction_a) / determinant
    point = (origin_a[0] + distance_a * direction_a[0],
             origin_a[1] + distance_a * direction_a[1])
    return point, distance_a, distance_b


def _construction_segments(
        station: tuple[float, float],
        nominal_direction: tuple[float, float],
        boundary_directions: list[tuple[float, float]],
        angle_deg: float,
        role: str,
        navaid: str,
        corners: list[tuple[float, float]],
) -> tuple[ConstructionLine, ...]:
    """Extend the nominal axis and both boundaries 10% past the polygon."""
    segments = []
    for offset, direction in ((0.0, nominal_direction),
                              (-angle_deg, boundary_directions[0]),
                              (angle_deg, boundary_directions[1])):
        length = 1.1 * max(
            (x - station[0]) * direction[0] + (y - station[1]) * direction[1]
            for x, y in corners)
        end = (station[0] + length * direction[0],
               station[1] + length * direction[1])
        if length <= 0 or not all(math.isfinite(value) for value in (*end, length)):
            raise ValueError('Construction lines must have finite positive lengths')
        segments.append(ConstructionLine(role, navaid, offset, station, end))
    return tuple(segments)


def build_intersection_tolerance(
        tracking_station: tuple[float, float],
        crossing_station: tuple[float, float],
        fix: tuple[float, float],
        tracking_type: str,
        crossing_type: str,
        flight_direction: str,
) -> ToleranceResult:
    """Return the bounded intersection area, along-track limits and construction.

    ``inbound`` means flight toward the tracking station; ``outbound`` means
    flight away from it. The fix is the nominal intersection of both radials.
    """
    if tracking_type not in ACCURACY_DEGREES or crossing_type not in ACCURACY_DEGREES:
        raise ValueError('Navaid type must be VOR, ILS or NDB')
    if flight_direction not in ('inbound', 'outbound'):
        raise ValueError('Flight direction must be inbound or outbound')
    for point in (tracking_station, crossing_station, fix):
        if len(point) != 2 or not all(math.isfinite(value) for value in point):
            raise ValueError('Station and fix coordinates must be finite points')
    if tracking_station == crossing_station:
        raise ValueError('Tracking and crossing stations must be distinct')

    tracking_vector = _difference(fix, tracking_station)
    crossing_vector = _difference(fix, crossing_station)
    tracking_distance = math.hypot(*tracking_vector)
    crossing_distance = math.hypot(*crossing_vector)
    if tracking_distance <= 1e-9 or crossing_distance <= 1e-9:
        raise ValueError('The fix must differ from both stations')
    tracking_unit = (tracking_vector[0] / tracking_distance,
                     tracking_vector[1] / tracking_distance)
    crossing_unit = (crossing_vector[0] / crossing_distance,
                     crossing_vector[1] / crossing_distance)
    track_angle = ACCURACY_DEGREES[tracking_type][0]
    cross_angle = ACCURACY_DEGREES[crossing_type][1]
    crossing_radians = math.atan2(abs(_cross(tracking_unit, crossing_unit)),
                                  tracking_unit[0] * crossing_unit[0] +
                                  tracking_unit[1] * crossing_unit[1])
    minimum_separation = math.radians(track_angle + cross_angle)
    if min(crossing_radians, math.pi - crossing_radians) <= minimum_separation:
        raise ValueError('Radials are too close to parallel for a bounded fix area')

    track_boundaries = [_rotate(tracking_unit, math.radians(sign * track_angle))
                        for sign in (-1, 1)]
    cross_boundaries = [_rotate(crossing_unit, math.radians(sign * cross_angle))
                        for sign in (-1, 1)]
    corners = []
    for track_ray in track_boundaries:
        for cross_ray in cross_boundaries:
            point, track_length, cross_length = _line_intersection(
                tracking_station, track_ray, crossing_station, cross_ray)
            if track_length <= 0 or cross_length <= 0 or not all(map(math.isfinite, point)):
                raise ValueError('Radial boundaries do not enclose the nominal fix')
            corners.append(point)
    centre = (sum(point[0] for point in corners) / 4,
              sum(point[1] for point in corners) / 4)
    corners.sort(key=lambda point: math.atan2(
        point[1] - centre[1], point[0] - centre[0]))
    ring = tuple(corners + [corners[0]])
    doubled_area = sum(_cross(ring[index], ring[index + 1])
                       for index in range(4))
    if doubled_area <= 1e-6:
        raise ValueError('Calculated fix tolerance area is degenerate')

    # The nominal track meets the crossing facility's two boundary radials.
    # These intersections, rather than the polygon vertices, define the
    # earliest and latest limits measured along the flight path.
    flight_unit = tracking_unit if flight_direction == 'outbound' else (
        -tracking_unit[0], -tracking_unit[1])
    along_track = []
    for cross_ray in cross_boundaries:
        point, signed_metres, cross_length = _line_intersection(
            fix, flight_unit, crossing_station, cross_ray)
        if cross_length <= 0 or not all(map(math.isfinite, point)):
            raise ValueError('Nominal track does not cross both radial boundaries')
        along_track.append(signed_metres)
    if min(along_track) >= 0 or max(along_track) <= 0:
        raise ValueError('Nominal fix is outside the calculated tolerance area')

    return ToleranceResult(
        ring=ring,
        area_m2=doubled_area / 2,
        track_angle_deg=track_angle,
        cross_angle_deg=cross_angle,
        early_nm=-min(along_track) / NM_METRES,
        late_nm=max(along_track) / NM_METRES,
        construction_lines=(
            _construction_segments(tracking_station, tracking_unit, track_boundaries,
                                   track_angle, 'Tracking', tracking_type, corners) +
            _construction_segments(crossing_station, crossing_unit, cross_boundaries,
                                   cross_angle, 'Intersecting', crossing_type, corners)),
    )


def _construction_layer(name: str, map_crs, lines: tuple[ConstructionLine, ...]):
    """Prepare the optional QGIS line layer without adding it to the project."""
    from qgis.PyQt.QtCore import QVariant
    from qgis.PyQt.QtGui import QColor
    from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsVectorLayer

    layer = QgsVectorLayer('LineString', name, 'memory')
    if not layer.isValid():
        raise RuntimeError('Could not create construction lines layer')
    layer.setCrs(map_crs)
    provider = layer.dataProvider()
    if not provider.addAttributes([
            QgsField('Role', QVariant.String),
            QgsField('Navaid', QVariant.String),
            QgsField('OffsetDeg', QVariant.Double)]):
        raise RuntimeError('Could not create construction line attributes')
    layer.updateFields()
    features = []
    for line in lines:
        geometry = QgsGeometry.fromPolylineXY([
            QgsPointXY(*line.start), QgsPointXY(*line.end)])
        if geometry.isEmpty() or not geometry.isGeosValid() or geometry.length() <= 0:
            raise ValueError('Calculated construction line is invalid')
        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        feature.setAttributes([line.role, line.navaid, line.offset_deg])
        features.append(feature)
    added, _ = provider.addFeatures(features)
    if not added:
        raise RuntimeError('Could not add construction line features')
    layer.updateExtents()
    layer.renderer().symbol().setColor(QColor('#e6b800'))
    layer.renderer().symbol().setWidth(0.3)
    return layer


def build_intersection_tolerance_from_layers(
        tracking_layer, crossing_layer, fix_layer, map_crs,
        tracking_type='VOR', crossing_type='VOR',
        flight_direction='outbound',
        show_error: Optional[Callable[[str], None]] = None,
) -> ToleranceResult:
    """Resolve input points and calculate without creating layers or UI output."""
    from qgis.core import (
        Qgis, QgsCoordinateTransform, QgsGeometry, QgsProject,
    )
    from ...utils import get_selected_feature

    if map_crs.isGeographic() or map_crs.mapUnits() != Qgis.DistanceUnit.Meters:
        raise ValueError('Set the map canvas to a projected CRS in metres')
    project = QgsProject.instance()

    def selected_point(layer, role):
        if layer is None:
            raise ValueError('Select a {0} point layer'.format(role))
        feature = get_selected_feature(
            layer, lambda message: show_error('{0}: {1}'.format(role, message))
            if show_error is not None else None)
        if feature is None:
            raise ValueError('Select exactly one {0} point'.format(role))
        geometry = QgsGeometry(feature.geometry())
        if (geometry.isNull() or geometry.isEmpty() or geometry.isMultipart() or
                geometry.type() != Qgis.GeometryType.Point):
            raise ValueError('{0} must be a single point'.format(role))
        geometry.transform(QgsCoordinateTransform(layer.crs(), map_crs, project))
        point = geometry.asPoint()
        return (point.x(), point.y())

    tracking = selected_point(tracking_layer, 'tracking station')
    crossing = selected_point(crossing_layer, 'crossing station')
    fix = selected_point(fix_layer, 'nominal fix')
    return build_intersection_tolerance(
        tracking, crossing, fix, tracking_type, crossing_type, flight_direction)


def run_radial_bearing_intersection(
        iface, tracking_layer, crossing_layer, fix_layer, params=None) -> bool:
    """Create a tolerance polygon and optional construction lines in QGIS."""
    from qgis.PyQt.QtCore import QVariant
    from qgis.PyQt.QtGui import QColor
    from qgis.core import (
        Qgis, QgsCoordinateReferenceSystem, QgsFeature, QgsField, QgsGeometry,
        QgsPointXY, QgsProject, QgsVectorFileWriter, QgsVectorLayer,
    )

    params = params or {}
    tracking_type = params.get('tracking_type', 'VOR')
    crossing_type = params.get('crossing_type', 'VOR')
    direction = params.get('flight_direction', 'outbound')
    map_crs = iface.mapCanvas().mapSettings().destinationCrs()
    result = build_intersection_tolerance_from_layers(
        tracking_layer, crossing_layer, fix_layer, map_crs,
        tracking_type, crossing_type, direction,
        show_error=lambda message: iface.messageBar().pushMessage(
            'QPANSOPY', message, level=Qgis.Warning))
    project = QgsProject.instance()

    name = '{0}_{1}_Radial_Bearing_Tolerance'.format(tracking_type, crossing_type)
    layer = QgsVectorLayer('Polygon', name, 'memory')
    layer.setCrs(map_crs)
    layer.dataProvider().addAttributes([
        QgsField('TrackType', QVariant.String),
        QgsField('CrossType', QVariant.String),
        QgsField('TrackDeg', QVariant.Double),
        QgsField('CrossDeg', QVariant.Double),
        QgsField('Direction', QVariant.String),
        QgsField('EarlyNM', QVariant.Double),
        QgsField('LateNM', QVariant.Double),
    ])
    layer.updateFields()
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPolygonXY([
        [QgsPointXY(*point) for point in result.ring]]))
    if not feature.geometry().isGeosValid():
        raise ValueError('Calculated tolerance polygon is invalid')
    feature.setAttributes([
        tracking_type, crossing_type, result.track_angle_deg,
        result.cross_angle_deg, direction, result.early_nm, result.late_nm,
    ])
    layer.dataProvider().addFeatures([feature])
    layer.updateExtents()
    layer.renderer().symbol().setColor(QColor('#365fc8'))
    layer.renderer().symbol().setOpacity(0.35)
    layers = [layer]
    if params.get('include_construction_lines', False):
        construction_name = '{0}_{1}_Radial_Bearing_Construction_Lines'.format(
            tracking_type, crossing_type)
        layers.append(_construction_layer(construction_name, map_crs, result.construction_lines))
    for output_layer in layers:
        project.addMapLayer(output_layer)
    callback = params.get('on_result')
    if callback is not None:
        callback(result)
    iface.messageBar().pushMessage(
        'QPANSOPY', 'Fix tolerance created: early {0:.3f} NM, late {1:.3f} NM'.format(
            result.early_nm, result.late_nm), level=Qgis.Success)

    if params.get('export_kml', False):
        output_dir = params.get('output_dir', '')
        try:
            if not os.path.isdir(output_dir):
                raise ValueError('Choose an existing KML output folder')
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = os.path.join(output_dir, '{0}_{1}.kml'.format(name, stamp))
            exported = QgsVectorFileWriter.writeAsVectorFormat(
                layer, path, 'utf-8', QgsCoordinateReferenceSystem('EPSG:4326'), 'KML')
            if exported[0] != QgsVectorFileWriter.NoError:
                raise RuntimeError('KML export failed: {0}'.format(exported[1]))
        except (OSError, RuntimeError, ValueError) as error:
            iface.messageBar().pushMessage(
                'QPANSOPY', 'Layer created, but {0}'.format(error), level=Qgis.Warning)
    return True
