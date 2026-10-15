"""Build the theoretical Doc 8168 dual-DME update area."""

from __future__ import annotations

import math
from typing import Callable

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsLineSymbol,
    QgsProject,
    QgsSingleSymbolRenderer,
    QgsVariantUtils,
    QgsVectorLayer,
    Qgis,
)

NM_TO_M = 1852.0
MAX_DOC_NM = 200.0
BUFFER_SEGMENTS = 360
ANGLE_CIRCLE_RADII_NM = 1.0


def _circle(center, radius_m: float) -> QgsGeometry:
    if not math.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("Circle radius must be finite and greater than zero")
    return QgsGeometry.fromPointXY(center).buffer(radius_m, BUFFER_SEGMENTS)


def _circle_line(center, radius_m: float) -> QgsGeometry:
    points = []
    for index in range(BUFFER_SEGMENTS * 4):
        angle = 2 * math.pi * index / (BUFFER_SEGMENTS * 4)
        points.append(type(center)(
            center.x() + radius_m * math.cos(angle),
            center.y() + radius_m * math.sin(angle),
        ))
    points.append(points[0])
    return QgsGeometry.fromPolylineXY(points)


def _checked_geometry(geometry: QgsGeometry, role: str) -> QgsGeometry:
    if (geometry is None or geometry.isNull() or geometry.isEmpty()
            or geometry.type() != Qgis.GeometryType.Polygon
            or not geometry.isGeosValid() or geometry.area() <= 0):
        raise ValueError("Could not build a valid {0} polygon".format(role))
    return geometry


def _doc_value(feature, field_name: str, role: str) -> tuple[float, str]:
    if not field_name:
        return MAX_DOC_NM, "defaulted to 200 NM (no DOC field selected)"

    raw_value = feature[field_name]
    if QgsVariantUtils.isNull(raw_value):
        return MAX_DOC_NM, "defaulted to 200 NM (DOC is NULL)"
    try:
        value = float(raw_value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("DOC for station {0} must be numeric".format(role)) from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            "DOC for station {0} must be finite and greater than zero".format(role))
    if value > MAX_DOC_NM:
        return MAX_DOC_NM, "capped from {0:g} NM to 200 NM".format(value)
    return value, "using {0:g} NM DOC".format(value)


def _point_wgs84(feature, layer, project, role: str):
    geometry = QgsGeometry(feature.geometry())
    if (geometry.isNull() or geometry.isEmpty() or geometry.isMultipart()
            or geometry.type() != Qgis.GeometryType.Point):
        raise ValueError("Station {0} must be a nonempty single point".format(role))
    geometry.transform(QgsCoordinateTransform(
        layer.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), project))
    point = geometry.asPoint()
    if not all(math.isfinite(value) for value in (point.x(), point.y())):
        raise ValueError("Station {0} coordinates must be finite".format(role))
    if not -180 <= point.x() <= 180 or not -90 <= point.y() <= 90:
        raise ValueError("Station {0} is outside valid WGS84 coordinates".format(role))
    return point


def _local_crs(point_a, distance_m: float, bearing: float, project):
    distance_area = QgsDistanceArea()
    distance_area.setSourceCrs(
        QgsCoordinateReferenceSystem("EPSG:4326"), project.transformContext())
    distance_area.setEllipsoid("WGS84")
    midpoint = distance_area.computeSpheroidProject(
        point_a, distance_m / 2, bearing)
    local_crs = QgsCoordinateReferenceSystem.fromProj(
        "+proj=aeqd +lat_0={0:.12f} +lon_0={1:.12f} "
        "+datum=WGS84 +units=m +no_defs".format(midpoint.y(), midpoint.x()))
    if not local_crs.isValid():
        raise ValueError("Could not create the local DME coverage projection")
    return local_crs, distance_area


def _add_feature(layer, geometry, attributes):
    feature = QgsFeature(layer.fields())
    feature.setGeometry(geometry)
    feature.setAttributes(attributes)
    return feature


def _new_layer(geometry_name: str, name: str, crs,
               fields: list[QgsField]) -> QgsVectorLayer:
    layer = QgsVectorLayer(geometry_name, name, "memory")
    if not layer.isValid():
        raise RuntimeError("Could not create {0} output layer".format(name))
    layer.setCrs(crs)
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    return layer


def _style_layers(coverage, construction, excluded):
    coverage.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({
        "color": "245,158,11,105",
        "outline_color": "31,41,55,255",
        "outline_width": "0.45",
    })))
    if excluded is not None:
        excluded.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({
            "color": "239,68,68,40",
            "outline_color": "185,28,28,220",
            "outline_width": "0.35",
            "outline_style": "dash",
        })))
    if construction is not None:
        categories = []
        styles = {
            "DOC_A": ("105,105,105,220", "solid"),
            "DOC_B": ("105,105,105,220", "solid"),
            "D_A": ("34,197,94,230", "solid"),
            "D_B": ("34,197,94,230", "solid"),
            "ANGLE_PLUS": ("37,99,235,230", "dash"),
            "ANGLE_MINUS": ("37,99,235,230", "dash"),
            "NO_UPDATE_A": ("185,28,28,255", "solid"),
            "NO_UPDATE_B": ("185,28,28,255", "solid"),
            "D": ("31,41,55,180", "solid"),
        }
        for role, (color, line_style) in styles.items():
            symbol = QgsLineSymbol.createSimple({
                "line_color": color,
                "line_style": line_style,
                "line_width": "0.35",
            })
            categories.append((role, symbol))
        from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory
        construction.setRenderer(QgsCategorizedSymbolRenderer(
            "Role", [QgsRendererCategory(role, symbol, role)
                     for role, symbol in categories]))


def _build_outputs(point_a, point_b, d_m, fid_a, fid_b,
                   doc_a_nm, doc_b_nm, doc_field, local_crs):
    d = point_a.distance(point_b)
    if not math.isfinite(d) or d <= 0:
        raise ValueError("The two DME stations must have distinct positions")
    midpoint_x = (point_a.x() + point_b.x()) / 2
    midpoint_y = (point_a.y() + point_b.y()) / 2
    unit_x = (point_b.x() - point_a.x()) / d
    unit_y = (point_b.y() - point_a.y()) / d
    normal_x, normal_y = -unit_y, unit_x
    offset = math.sqrt(3) * d / 2
    center_plus = type(point_a)(
        midpoint_x + normal_x * offset, midpoint_y + normal_y * offset)
    center_minus = type(point_a)(
        midpoint_x - normal_x * offset, midpoint_y - normal_y * offset)

    doc_a = _circle(point_a, doc_a_nm * NM_TO_M)
    doc_b = _circle(point_b, doc_b_nm * NM_TO_M)
    distance_a = _circle(point_a, d)
    distance_b = _circle(point_b, d)
    angle_plus = _circle(center_plus, d)
    angle_minus = _circle(center_minus, d)
    no_update_a = _circle(point_a, NM_TO_M)
    no_update_b = _circle(point_b, NM_TO_M)
    central_exclusion = _checked_geometry(
        angle_plus.intersection(angle_minus), "central excluded")
    angle_area = _checked_geometry(
        angle_plus.symDifference(angle_minus), "30/150-degree")
    doc_overlap = _checked_geometry(doc_a.intersection(doc_b), "dual-DOC")
    distance_overlap = _checked_geometry(
        distance_a.intersection(distance_b), "radius-D overlap")
    valid_overlap = doc_overlap.intersection(distance_overlap).intersection(angle_area)
    if valid_overlap.isNull() or valid_overlap.isEmpty() or valid_overlap.area() <= 0:
        return None
    exclusions = _checked_geometry(
        no_update_a.combine(no_update_b), "no-update")
    coverage = valid_overlap.difference(exclusions)
    if coverage.isNull() or coverage.isEmpty() or coverage.area() <= 0:
        return None
    coverage = _checked_geometry(coverage, "final DME/DME coverage")
    coverage.convertToMultiType()

    fields = [
        QgsField("A_FID", QVariant.LongLong),
        QgsField("B_FID", QVariant.LongLong),
        QgsField("D_NM", QVariant.Double),
        QgsField("DOC_A_NM", QVariant.Double),
        QgsField("DOC_B_NM", QVariant.Double),
        QgsField("DOC_FIELD", QVariant.String),
    ]
    coverage_layer = _new_layer(
        "MultiPolygon", "DME_DME_Coverage", local_crs, fields)
    coverage_layer.dataProvider().addFeatures([_add_feature(
        coverage_layer, coverage, [
            fid_a, fid_b, d_m / NM_TO_M,
            doc_a_nm, doc_b_nm, doc_field or "",
        ])])
    coverage_layer.updateExtents()

    construction_layer = None
    excluded_layer = None
    construction_roles = [
        ("DOC_A", point_a, doc_a_nm * NM_TO_M, doc_a_nm),
        ("DOC_B", point_b, doc_b_nm * NM_TO_M, doc_b_nm),
        ("D_A", point_a, d, d / NM_TO_M),
        ("D_B", point_b, d, d / NM_TO_M),
        ("ANGLE_PLUS", center_plus, d, d / NM_TO_M),
        ("ANGLE_MINUS", center_minus, d, d / NM_TO_M),
        ("NO_UPDATE_A", point_a, NM_TO_M, ANGLE_CIRCLE_RADII_NM),
        ("NO_UPDATE_B", point_b, NM_TO_M, ANGLE_CIRCLE_RADII_NM),
    ]
    construction_layer = _new_layer(
        "LineString", "DME_DME_Construction", local_crs,
        [
            QgsField("Role", QVariant.String),
            QgsField("Radius_NM", QVariant.Double),
        ],
    )
    line_features = [
        _add_feature(construction_layer, _circle_line(center, radius_m),
                     [role, radius_nm])
        for role, center, radius_m, radius_nm in construction_roles
    ]
    from qgis.core import QgsGeometry, QgsPointXY
    baseline = QgsGeometry.fromPolylineXY([
        QgsPointXY(point_a), QgsPointXY(point_b)])
    line_features.append(_add_feature(
        construction_layer, baseline, ["D", None]))
    construction_layer.dataProvider().addFeatures(line_features)
    construction_layer.updateExtents()

    excluded_layer = _new_layer("MultiPolygon", "DME_DME_Excluded_Areas",
                                local_crs, [QgsField("Role", QVariant.String)])
    excluded_features = [
        _add_feature(excluded_layer, geometry, [role])
        for role, geometry in [
            ("CENTRAL", central_exclusion),
            ("NO_UPDATE_A", no_update_a),
            ("NO_UPDATE_B", no_update_b),
        ]
    ]
    excluded_layer.dataProvider().addFeatures(excluded_features)
    excluded_layer.updateExtents()
    _style_layers(coverage_layer, construction_layer, excluded_layer)
    return coverage_layer, construction_layer, excluded_layer


def run_dme_dme_coverage(iface, dme_layer, params=None) -> bool:
    """Calculate coverage for exactly two selected DME point features."""
    params = {} if params is None else params
    log: Callable[[str], None] = params.get("log", lambda _message: None)
    if dme_layer is None or not dme_layer.isValid():
        raise ValueError("Select a valid DME point layer")
    if dme_layer.geometryType() != Qgis.GeometryType.Point:
        raise ValueError("The DME layer must contain point features")

    selected = sorted(dme_layer.selectedFeatures(), key=lambda feature: feature.id())
    if len(selected) != 2:
        raise ValueError("Select exactly two DME stations in the layer")
    feature_a, feature_b = selected
    doc_field = str(params.get("doc_field") or "")
    if doc_field and dme_layer.fields().indexFromName(doc_field) < 0:
        raise ValueError("The selected DOC field no longer exists in the layer")

    doc_a_nm, doc_a_note = _doc_value(feature_a, doc_field, "A")
    doc_b_nm, doc_b_note = _doc_value(feature_b, doc_field, "B")
    project = QgsProject.instance()
    wgs84_a = _point_wgs84(feature_a, dme_layer, project, "A")
    wgs84_b = _point_wgs84(feature_b, dme_layer, project, "B")
    distance_area = QgsDistanceArea()
    wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    distance_area.setSourceCrs(wgs84_crs, project.transformContext())
    distance_area.setEllipsoid("WGS84")
    d_m = distance_area.measureLine(wgs84_a, wgs84_b)
    if not math.isfinite(d_m) or d_m <= 0:
        raise ValueError("The two DME stations must have distinct positions")
    if d_m >= (doc_a_nm + doc_b_nm) * NM_TO_M:
        log("No theoretical DME/DME coverage for this pair (DOC circles do not overlap).")
        return False
    local_crs, _distance_area = _local_crs(
        wgs84_a, d_m, distance_area.bearing(wgs84_a, wgs84_b), project)
    transform = QgsCoordinateTransform(wgs84_crs, local_crs, project)
    point_a = transform.transform(wgs84_a)
    point_b = transform.transform(wgs84_b)
    if point_a.distance(point_b) <= 0:
        raise ValueError("The two DME stations must have distinct positions")

    outputs = _build_outputs(
        point_a, point_b, d_m, feature_a.id(), feature_b.id(),
        doc_a_nm, doc_b_nm, doc_field, local_crs)
    if outputs is None:
        log("No theoretical DME/DME coverage for this pair.")
        return False
    coverage, construction, excluded = outputs
    construction_enabled = bool(params.get("include_construction_layers", True))
    name = "DME/DME Coverage — A {0}, B {1}".format(
        feature_a.id(), feature_b.id())
    root = project.layerTreeRoot()
    group = root.insertGroup(0, name)
    project.addMapLayer(coverage, False)
    group.addLayer(coverage)
    if construction_enabled:
        project.addMapLayer(excluded, False)
        group.addLayer(excluded)
        project.addMapLayer(construction, False)
        group.addLayer(construction)

    log("Stations A/B FID: {0}/{1}; D: {2:.2f} NM.".format(
        feature_a.id(), feature_b.id(), d_m / NM_TO_M))
    log("DOC A: {0}; DOC B: {1}.".format(doc_a_note, doc_b_note))
    log("Created theoretical DME/DME coverage in local AEQD CRS.")
    if construction_enabled:
        log("Added DOC, radius-D, 30°/150°, 1 NM, D and excluded-area layers.")
    iface.messageBar().pushMessage(
        "QPANSOPY", "DME/DME theoretical coverage calculated successfully",
        level=Qgis.Success)
    return True
