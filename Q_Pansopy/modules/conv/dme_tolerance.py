# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPoint, QgsLineString, QgsPolygon, QgsCircle, QgsField, Qgis,
    QgsDistanceArea, QgsCoordinateTransform, QgsPointXY,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from ...utils import get_selected_feature


def _calculate_dme_tolerance_m(distance_m: float) -> float:
    """Return the one-sided DME tolerance from the unrounded distance."""
    return 0.25 * 1852 + 0.0125 * distance_m


def _geom_to_map_crs(feature, layer, map_crs, project, role='Input') -> QgsPointXY:
    """Validate a single point and return it in the map CRS."""
    g = QgsGeometry(feature.geometry())
    if (g.isNull() or g.isEmpty() or g.isMultipart() or
            g.type() != Qgis.GeometryType.Point):
        raise ValueError(f'{role} must be a nonempty single point')
    g.transform(QgsCoordinateTransform(layer.crs(), map_crs, project))
    return g.asPoint()


def build_tolerance_geometry(
        navid_geom: QgsPointXY, fix_geom: QgsPointXY, rotate: float,
        da: QgsDistanceArea, tracking_geom: QgsPointXY | None = None,
) -> tuple[QgsGeometry, float]:
    """
    Build the fix tolerance polygon: intersection of the ±rotate° angular
    sector off nominal track with the DME tolerance ring (0.25 NM fixed +
    1.25 % of distance), per ICAO Doc 8168.

    :param navid_geom: DME station point geometry (map CRS)
    :param fix_geom: Fix/threshold point geometry (map CRS)
    :param rotate: Sector half-angle in degrees
    :param da: QgsDistanceArea configured with the map CRS ellipsoid
    :param tracking_geom: Separate tracking station, or None for collocation.
        Separate stations require a projected source CRS in metres and no
        more than 23 degrees of divergence at the nominal fix.
    :return: (tolerance_area geometry, distance_nm)
    :raises ValueError: Invalid inputs or an unusable tolerance area
    """
    if tracking_geom is not None:
        source_crs = da.sourceCrs()
        if source_crs.isGeographic() or source_crs.mapUnits() != Qgis.DistanceUnit.Meters:
            raise ValueError('Set the map canvas to a projected CRS in metres')
    tracking = navid_geom if tracking_geom is None else tracking_geom
    for point in (navid_geom, fix_geom, tracking):
        if not all(math.isfinite(value) for value in (point.x(), point.y())):
            raise ValueError('DME, tracking and fix coordinates must be finite points')
    if not math.isfinite(rotate) or not 0 < rotate < 90:
        raise ValueError('Sector half-angle must be greater than 0 and less than 90 degrees')
    if navid_geom.distance(fix_geom) == 0 or tracking.distance(fix_geom) == 0:
        raise ValueError('The fix must differ from both the DME and tracking station')

    azimuth = tracking.azimuth(fix_geom)
    length0 = navid_geom.distance(fix_geom)  # map units
    if tracking_geom is not None:
        divergence = abs((azimuth - navid_geom.azimuth(fix_geom) + 180) % 360 - 180)
        if divergence > 23 + 1e-9:
            raise ValueError(
                f'Tracking/DME divergence is {divergence:.6f}°; maximum is 23°')

    length0_m = da.measureLine(navid_geom, fix_geom)
    if not math.isfinite(length0_m) or length0_m <= 0:
        raise ValueError('DME distance must be finite and greater than zero')
    distance_nm = round(length0_m / 1852, 3)

    dme_tol_m = _calculate_dme_tolerance_m(length0_m)
    dme_tolerance = (dme_tol_m / length0_m) * length0 if length0_m > 0 else dme_tol_m

    reach = length0 * 5
    if tracking_geom is not None:
        # Keep the triangle base beyond the entire outer DME disk, even when
        # the tracking station is close to the fix or far from the DME.
        bound = tracking.distance(navid_geom) + length0 + dme_tolerance
        reach = (bound + max(1.0, bound * 1e-9)) / math.cos(math.radians(rotate))
    pt1 = QgsPoint(tracking)
    proj2 = tracking.project(reach, azimuth + rotate)
    proj3 = tracking.project(reach, azimuth - rotate)
    pt2 = QgsPoint(proj2)
    pt3 = QgsPoint(proj3)
    sector = QgsGeometry(QgsPolygon(QgsLineString([pt1, pt2, pt3])))

    dme_circle = QgsGeometry(
        QgsCircle(QgsPoint(navid_geom), length0).toCircularString()
    ).buffer(dme_tolerance, 360)

    tolerance_area = sector.intersection(dme_circle)
    if tracking_geom is not None and tolerance_area.isMultipart():
        # A radial from an external tracking station can meet the annulus
        # twice. Return the component belonging to the selected nominal fix.
        components = [QgsGeometry.fromPolygonXY(polygon)
                      for polygon in tolerance_area.asMultiPolygon()]
        tolerance_area = next(
            (component for component in components if component.contains(fix_geom)),
            QgsGeometry(),
        )
    if (tolerance_area.isNull() or tolerance_area.isEmpty() or
            tolerance_area.type() != Qgis.GeometryType.Polygon or
            not tolerance_area.isGeosValid() or not tolerance_area.contains(fix_geom)):
        raise ValueError('Calculated tolerance area must be a valid polygon containing the fix')
    return tolerance_area, distance_nm


def run_dme_tolerance(iface, navid_layer, fix_layer, params=None, tracking_layer=None) -> bool:
    """
    Calculate a facility/DME fix tolerance area (VOR/DME, NDB/DME, or LOC/DME).

    :param iface: QGIS interface
    :param navid_layer: Point layer containing the DME station
    :param fix_layer: Point layer containing the fix/threshold point
    :param params: Optional dict; supports 'rotate' (sector half-angle in
        degrees, default 5.2), 'nav_type' (label, default 'VOR/DME') and
        'non_collocated_dme' (default False for existing callers)
    :param tracking_layer: Tracking station layer, required in non-collocated mode
    :return: True on success, False on failure
    :raises ValueError: Invalid geometry, CRS or non-collocated configuration
    """
    if params is None:
        params = {}
    rotate = float(params.get('rotate', 5.2))
    nav_type = params.get('nav_type', 'VOR/DME')
    non_collocated = params.get('non_collocated_dme', False)
    if non_collocated and tracking_layer is None:
        raise ValueError('Please select a Tracking Navaid point layer')

    map_crs = iface.mapCanvas().mapSettings().destinationCrs()
    map_srid = map_crs.authid()
    project = QgsProject.instance()

    def show_error(msg):
        iface.messageBar().pushMessage("QPANSOPY:", msg, level=Qgis.Warning)

    navid_feature = get_selected_feature(navid_layer, show_error)
    if navid_feature is None:
        return False

    fix_feature = get_selected_feature(fix_layer, show_error)
    if fix_feature is None:
        return False

    # All centres share the map CRS, including when source layer CRSs differ.
    navid_geom = _geom_to_map_crs(navid_feature, navid_layer, map_crs, project, 'DME')
    fix_geom = _geom_to_map_crs(fix_feature, fix_layer, map_crs, project, 'Fix')
    tracking_geom = None
    if non_collocated:
        tracking_feature = get_selected_feature(tracking_layer, show_error)
        if tracking_feature is None:
            return False
        tracking_geom = _geom_to_map_crs(
            tracking_feature, tracking_layer, map_crs, project, 'Tracking Navaid')

    da = QgsDistanceArea()
    da.setSourceCrs(map_crs, project.transformContext())
    da.setEllipsoid(project.ellipsoid())

    tolerance_area, distance_nm = build_tolerance_geometry(
        navid_geom, fix_geom, rotate, da, tracking_geom)
    dme_tolerance_nm = _calculate_dme_tolerance_m(da.measureLine(navid_geom, fix_geom)) / 1852

    # Build result layer
    layer_name = f"{nav_type.replace('/', '')}_tolerance"
    v_layer = QgsVectorLayer(f"Polygon?crs={map_srid}", layer_name, "memory")
    pr = v_layer.dataProvider()
    pr.addAttributes([
        QgsField('Symbol', QVariant.String),
        QgsField('Distance_NM', QVariant.Double),
        QgsField('Sector_Angle', QVariant.Double),
        QgsField('DME_Tolerance_NM', QVariant.Double),
    ])
    v_layer.updateFields()

    seg = QgsFeature()
    seg.setGeometry(tolerance_area)
    seg.setAttributes([f'{nav_type} Tolerance', distance_nm, rotate, dme_tolerance_nm])
    pr.addFeatures([seg])
    v_layer.updateExtents()

    v_layer.renderer().symbol().setOpacity(0.3)
    v_layer.renderer().symbol().setColor(QColor('blue'))
    v_layer.triggerRepaint()

    QgsProject.instance().addMapLayer(v_layer)
    iface.messageBar().pushMessage(
        "QPANSOPY:", f"{nav_type} Tolerance calculated successfully", level=Qgis.Success
    )
    return True
