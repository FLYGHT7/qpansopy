"""Constant-width GNSS en-route protection corridors."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qgis.core import QgsGeometry


@dataclass(frozen=True)
class EnrouteSpec:
    identifier: str
    label: str
    half_width_nm: float


SPECS = (
    EnrouteSpec('rnav5', 'RNAV 5', 5.77),
    EnrouteSpec('rnp4', 'RNP 4', 8.0),
    EnrouteSpec('rnav2', 'RNAV 2', 5.0),
    EnrouteSpec('rnp2', 'RNP 2', 5.0),
    EnrouteSpec('arnp2', 'Advanced RNP — RNP 2', 5.0),
    EnrouteSpec('arnp1', 'Advanced RNP — RNP 1', 3.5),
    EnrouteSpec('rnav1', 'RNAV 1', 5.0),
    EnrouteSpec('rnp03', 'RNP 0.3 (CAT H)', 1.45),
)
STYLE_PATH = Path(__file__).resolve().parents[2] / 'styles' / 'primary_secondary_areas.qml'


def resolve_spec(identifier: str) -> EnrouteSpec:
    for spec in SPECS:
        if spec.identifier == identifier:
            return spec
    raise ValueError('Unknown GNSS en-route specification: {0}'.format(identifier))


def build_enroute_geometry(
    a: tuple[float, float], b: tuple[float, float], nav_spec: str,
) -> tuple[QgsGeometry, QgsGeometry, QgsGeometry]:
    """Return primary, left and right rectangles in projected metres."""
    from qgis.core import QgsGeometry, QgsPointXY
    from .dme_dme_coverage import _checked_geometry

    width = resolve_spec(nav_spec).half_width_nm * 1852.0
    if not all(math.isfinite(v) for point in (a, b) for v in point):
        raise ValueError('Segment coordinates must be finite')
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length <= 0 or not math.isfinite(length):
        raise ValueError('Segment endpoints must be distinct')
    nx, ny = -dy / length, dx / length

    def rectangle(low: float, high: float) -> QgsGeometry:
        ring = [QgsPointXY(point[0] + nx * offset, point[1] + ny * offset)
                for point, offset in ((a, low), (b, low), (b, high), (a, high))]
        return _checked_geometry(QgsGeometry.fromPolygonXY([ring + [ring[0]]]), 'ENR area')

    return (rectangle(-width / 2, width / 2), rectangle(width / 2, width),
            rectangle(-width, -width / 2))


def run_pbn_enroute_gnss(iface, routing_layer, params=None) -> bool:
    """Generate one three-feature corridor from one selected straight segment."""
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import (
        Qgis, QgsCategorizedSymbolRenderer, QgsCoordinateReferenceSystem,
        QgsCoordinateTransform, QgsDistanceArea, QgsFeature, QgsField,
        QgsGeometry, QgsLayerNotesUtils, QgsMapLayer, QgsProject, QgsWkbTypes,
    )
    from .dme_dme_coverage import _local_crs, _new_layer

    params = {} if params is None else params
    spec = resolve_spec(params.get('nav_spec', 'rnav5'))
    if (routing_layer is None or not routing_layer.isValid()
            or routing_layer.geometryType() != Qgis.GeometryType.Line
            or not routing_layer.crs().isValid()):
        raise ValueError('Select a valid line layer with a valid CRS')
    selected = routing_layer.selectedFeatures()
    if len(selected) != 1:
        raise ValueError('Select exactly one straight segment')
    source = selected[0]
    geometry = QgsGeometry(source.geometry())
    if (geometry.isNull() or geometry.isEmpty() or geometry.isMultipart()
            or QgsWkbTypes.flatType(geometry.wkbType()) != QgsWkbTypes.LineString
            or len(geometry.asPolyline()) != 2):
        raise ValueError('Select a single straight LineString with exactly two vertices')
    if not all(math.isfinite(v) for p in geometry.asPolyline() for v in (p.x(), p.y())):
        raise ValueError('Segment coordinates must be finite')
    project = QgsProject.instance()
    wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
    geometry.transform(QgsCoordinateTransform(routing_layer.crs(), wgs84, project))
    a, b = geometry.asPolyline()
    if not all(math.isfinite(p.x()) and math.isfinite(p.y())
               and -180 <= p.x() <= 180 and -90 <= p.y() <= 90 for p in (a, b)):
        raise ValueError('Segment endpoints must be valid WGS84 coordinates')
    distance = QgsDistanceArea()
    distance.setSourceCrs(wgs84, project.transformContext())
    distance.setEllipsoid('WGS84')
    length = distance.measureLine(a, b)
    if not math.isfinite(length) or length <= 0:
        raise ValueError('Segment endpoints must be distinct')
    crs, _ = _local_crs(a, length, distance.bearing(a, b), project)
    transform = QgsCoordinateTransform(wgs84, crs, project)
    a, b = transform.transform(a), transform.transform(b)
    areas = build_enroute_geometry((a.x(), a.y()), (b.x(), b.y()), spec.identifier)
    layer = _new_layer('Polygon', 'PBN ENR GNSS — ' + spec.label, crs, [
        QgsField('Symbol', QVariant.String), QgsField('nav_spec', QVariant.String),
        QgsField('sensor', QVariant.String), QgsField('half_width_nm', QVariant.Double),
        QgsField('distance_nm', QVariant.Double), QgsField('source_fid', QVariant.LongLong),
    ])
    features = []
    for area, symbol in zip(areas, ('Primary Area', 'Secondary Area', 'Secondary Area')):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(area)
        feature.setAttributes([symbol, spec.label, 'GNSS', spec.half_width_nm,
                               length / 1852.0, source.id()])
        features.append(feature)
    if not layer.dataProvider().addFeatures(features)[0]:
        raise RuntimeError('Could not populate GNSS en-route areas')
    message, loaded = layer.loadNamedStyle(
        str(STYLE_PATH), categories=QgsMapLayer.StyleCategory.Symbology)
    if not loaded or not isinstance(layer.renderer(), QgsCategorizedSymbolRenderer):
        raise RuntimeError('Could not load PBN symbology: ' + message)
    layer.updateExtents()
    notes = ('GNSS only; outer semi-width {0:g} NM; primary '
             'semi-width {1:g} NM; flat ends.').format(
                 spec.half_width_nm, spec.half_width_nm / 2)
    notes += (' Widths are Cartesian in the output layer local AEQD CRS. '
              'To verify: set the project CRS to this layer CRS, use Cartesian '
              'measurement and snap perpendicular to the track. UTM Cartesian '
              'and WGS84 ellipsoidal measurements may differ. Construction CRS: '
              + crs.toProj())
    QgsLayerNotesUtils.setLayerNotes(layer, notes)
    project.addMapLayer(layer, False)
    group = project.layerTreeRoot().insertGroup(
        0, 'PBN ENR GNSS — {0} — segment {1}'.format(spec.label, source.id()))
    group.addLayer(layer)
    params.get('log', lambda message: None)(
        '{0}; distance {1:.6f} NM; outer ±{2:g} NM; primary ±{3:g} NM.'.format(
            spec.label, length / 1852.0, spec.half_width_nm, spec.half_width_nm / 2))
    params.get('log', lambda message: None)('Construction CRS (metres): ' + crs.toProj())
    iface.messageBar().pushMessage('QPANSOPY', 'PBN ENR GNSS areas created', level=Qgis.Success)
    return True
