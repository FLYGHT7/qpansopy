"""Refined conventional en-route areas for a straight VOR/VOR segment."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from qgis.core import QgsGeometry


NM_TO_M = 1852.0
CASE_ONE_LIMIT_M = 75 * NM_TO_M
PRIMARY_RADIUS_M = 7400.0
EXTERIOR_RADIUS_M = 14800.0
EXTRA_MARGIN_M = 3700.0
PRIMARY_SPLAY = 0.10
EXTERIOR_SPLAY = 0.16
BUFFER_SEGMENTS = 360
Point = tuple[float, float]


@dataclass(frozen=True)
class RefinedEnrouteProfile:
    """Unrounded station distance and the applicable numerical criteria."""

    distance_m: float
    case: Literal[1, 2]

    def half_widths(self, along_m: float) -> tuple[float, float]:
        position = float(along_m)
        if not math.isfinite(position) or not 0 <= position <= self.distance_m:
            raise ValueError('Position must lie between the two VOR stations')
        if self.case == 1:
            return PRIMARY_RADIUS_M, EXTERIOR_RADIUS_M
        nearest = min(position, self.distance_m - position)
        # A perpendicular margin on a sloping line is larger in the y direction.
        margin_y = EXTRA_MARGIN_M * math.hypot(1.0, EXTERIOR_SPLAY)
        return (
            max(PRIMARY_RADIUS_M, PRIMARY_SPLAY * nearest),
            max(EXTERIOR_RADIUS_M, EXTERIOR_SPLAY * nearest + margin_y),
        )


@dataclass(frozen=True)
class ConstructionLine:
    role: str
    splay_pct: int
    start: Point
    end: Point


@dataclass(frozen=True)
class RefinedEnrouteAreas:
    profile: RefinedEnrouteProfile
    primary: QgsGeometry
    secondary: QgsGeometry
    construction_lines: tuple[ConstructionLine, ...]


def calculate_profile(distance_m: float) -> RefinedEnrouteProfile:
    """Select the case from the raw distance, with an inclusive 75 NM limit."""
    distance = float(distance_m)
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError('VOR separation must be finite and greater than zero')
    return RefinedEnrouteProfile(distance, 1 if distance <= CASE_ONE_LIMIT_M else 2)


def build_enroute_geometry(
    point_a: Point, point_b: Point, distance_m: float | None = None,
) -> RefinedEnrouteAreas:
    """Build areas in projected metres, without project or interface side effects.

    ``distance_m`` retains the measured geodesic distance for case selection.
    A midpoint AEQD projection makes its station distance equal to the planar
    separation, apart from transformation precision.
    """
    from qgis.core import QgsGeometry, QgsPointXY
    from ..pbn.dme_dme_coverage import _checked_geometry

    if any(not math.isfinite(value) for point in (point_a, point_b) for value in point):
        raise ValueError('VOR coordinates must be finite')
    dx, dy = point_b[0] - point_a[0], point_b[1] - point_a[1]
    length = math.hypot(dx, dy)
    profile = calculate_profile(length if distance_m is None else distance_m)
    if length <= 0 or not math.isclose(length, profile.distance_m, rel_tol=1e-9, abs_tol=1e-4):
        raise ValueError('VOR coordinates must use the local projected metre CRS')
    ux, uy = dx / length, dy / length

    def map_point(x: float, y: float) -> Point:
        return point_a[0] + ux * x - uy * y, point_a[1] + uy * x + ux * y

    def polygon(points: tuple[Point, ...]) -> QgsGeometry:
        ring = [QgsPointXY(*map_point(x, y)) for x, y in points]
        return QgsGeometry.fromPolygonXY([ring + [ring[0]]])

    axis = QgsGeometry.fromPolylineXY([QgsPointXY(*point_a), QgsPointXY(*point_b)])
    primary = axis.buffer(PRIMARY_RADIUS_M, BUFFER_SEGMENTS)
    exterior = axis.buffer(EXTERIOR_RADIUS_M, BUFFER_SEGMENTS)
    construction = []
    if profile.case == 2:
        middle = length / 2
        primary_y, exterior_y = profile.half_widths(profile.distance_m / 2)
        primary = primary.combine(polygon((
            (0, 0), (middle, primary_y), (length, 0), (middle, -primary_y),
        )))
        margin_y = EXTRA_MARGIN_M * math.hypot(1.0, EXTERIOR_SPLAY)
        # Offset the splay sides only between stations. Buffering a complete
        # diamond with mitred joins would create spikes beyond the round ends.
        exterior = exterior.combine(polygon((
            (0, margin_y), (middle, exterior_y), (length, margin_y),
            (length, -margin_y), (middle, -exterior_y), (0, -margin_y),
        )))
        construction.append(ConstructionLine('Axis', 0, map_point(-PRIMARY_RADIUS_M, 0),
                                             map_point(length + PRIMARY_RADIUS_M, 0)))
        for percentage in (10, 16):
            for sign, side in ((1, 'left'), (-1, 'right')):
                tip = map_point(middle, sign * percentage / 100 * profile.distance_m / 2)
                for station, point in (('A', point_a), ('B', point_b)):
                    construction.append(ConstructionLine(f'{station}_{side}', percentage, point, tip))
    else:
        construction.append(ConstructionLine('Axis', 0, point_a, point_b))
    primary = _checked_geometry(primary, 'Primary area')
    exterior = _checked_geometry(exterior, 'exterior envelope')
    secondary = _checked_geometry(exterior.difference(primary), 'Secondary area')
    return RefinedEnrouteAreas(profile, primary, secondary, tuple(construction))


def _construction_layer(lines, crs):
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsLineSymbol, QgsPointXY, QgsSingleSymbolRenderer
    from ..pbn.dme_dme_coverage import _new_layer

    layer = _new_layer('LineString', 'VOR/VOR construction lines', crs, [
        QgsField('role', QVariant.String), QgsField('splay_pct', QVariant.Int),
    ])
    features = []
    for line in lines:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*line.start), QgsPointXY(*line.end)]))
        feature.setAttributes([line.role, line.splay_pct])
        features.append(feature)
    if not layer.dataProvider().addFeatures(features)[0]:
        raise RuntimeError('Could not populate the construction lines')
    layer.updateExtents()
    layer.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple({
        'line_color': '45,45,45,255', 'line_width': '0.25', 'line_style': 'dash',
    })))
    return layer


def _output_group(project, vor_layer, layers, feature_a_id, feature_b_id):
    """Place results first in the tree while drawing them below the VOR."""
    root = project.layerTreeRoot()
    previous_order = list(root.layerOrder())
    project.addMapLayers(layers, False)
    group = root.insertGroup(0, f'Refined ENR VOR/VOR — A {feature_a_id}, B {feature_b_id}')
    for layer in layers:
        group.addLayer(layer).setItemVisibilityChecked(True)
    index = previous_order.index(vor_layer) + 1 if vor_layer in previous_order else len(previous_order)
    root.setCustomLayerOrder(previous_order[:index] + layers + previous_order[index:])
    root.setHasCustomLayerOrder(True)
    return group


def run_enroute_vor_vor_refined(iface, vor_layer, params=None) -> bool:
    """Create refined areas from exactly two selected VOR point features."""
    from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform
    from qgis.core import QgsDistanceArea, QgsLayerNotesUtils, QgsProject
    from ..pbn.dme_dme_coverage import _local_crs, _point_wgs84
    from ._enroute_output import _create_enroute_area_layer

    params = {} if params is None else params
    log = params.get('log', lambda _message: None)
    if vor_layer is None or not vor_layer.isValid():
        raise ValueError('Select a valid VOR point layer')
    if vor_layer.geometryType() != Qgis.GeometryType.Point:
        raise ValueError('The VOR layer must contain points')
    if not vor_layer.crs().isValid():
        raise ValueError('The VOR layer must have a valid CRS')
    selected = sorted(vor_layer.selectedFeatures(), key=lambda feature: feature.id())
    if len(selected) != 2:
        raise ValueError('Select exactly two VOR stations in the layer')
    project = QgsProject.instance()
    feature_a, feature_b = selected
    wgs_a = _point_wgs84(feature_a, vor_layer, project, 'A')
    wgs_b = _point_wgs84(feature_b, vor_layer, project, 'B')
    distance_area = QgsDistanceArea()
    distance_area.setSourceCrs(QgsCoordinateReferenceSystem('EPSG:4326'), project.transformContext())
    distance_area.setEllipsoid('WGS84')
    distance_m = distance_area.measureLine(wgs_a, wgs_b)
    calculate_profile(distance_m)
    crs, _ = _local_crs(wgs_a, distance_m, distance_area.bearing(wgs_a, wgs_b), project)
    transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, project)
    a, b = transform.transform(wgs_a), transform.transform(wgs_b)
    result = build_enroute_geometry((a.x(), a.y()), (b.x(), b.y()), distance_m)
    areas = _create_enroute_area_layer(
        'Refined ENR VOR/VOR areas', result.primary, result.secondary,
        'Secondary area', result.profile.case,
        result.profile.distance_m / NM_TO_M, crs, 'Refined',
    )
    construction = None
    if params.get('include_construction_lines', False):
        construction = _construction_layer(result.construction_lines, crs)
    notes = (
        '<h3>Refined ENR — VOR/VOR (straight)</h3><p>'
        f'VOR A/B feature IDs: {feature_a.id()}/{feature_b.id()}<br>'
        f'Case: {result.profile.case}; WGS84 distance: {distance_m:.9f} m<br>'
        'Case 1 limit: 75 NM, inclusive; 1 NM = 1852 m.<br>'
        'Exact primary/exterior radii: 7400/14800 m.<br>'
        'Case 2 splays: 10% and 16%; perpendicular exterior margin: 3700 m.<br>'
        'Secondary area excludes Primary area. Both areas are features in one layer. '
        'Construction uses a local midpoint AEQD CRS.</p>'
    )
    layers = [areas] if construction is None else [construction, areas]
    for layer in layers:
        QgsLayerNotesUtils.setLayerNotes(layer, notes)
    _output_group(project, vor_layer, layers, feature_a.id(), feature_b.id())
    log(f'Case {result.profile.case}; distance: {distance_m / NM_TO_M:.6f} NM ({distance_m / 1000:.6f} km).')
    log('Created Primary area and Secondary area in one layer with exact kilometre widths.')
    if construction is not None:
        if result.profile.case == 1:
            log('Loaded the centerline between the two VOR stations.')
        else:
            log('Loaded the axis and eight 10%/16% construction segments.')
    iface.messageBar().pushMessage('QPANSOPY', 'Refined VOR/VOR areas created', level=Qgis.Success)
    return True
