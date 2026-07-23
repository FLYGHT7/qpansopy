# -*- coding: utf-8 -*-
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPoint, QgsLineString, QgsPolygon, QgsCircle, QgsField, Qgis,
    QgsDistanceArea, QgsCoordinateTransform,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from ...utils import get_selected_feature


def _geom_to_map_crs(feature, layer, map_crs, project):
    """Return feature point geometry transformed to the map CRS."""
    g = feature.geometry()
    g.transform(QgsCoordinateTransform(layer.crs(), map_crs, project))
    return g.asPoint()


def build_tolerance_geometry(navid_geom, fix_geom, rotate, da):
    """
    Build the fix tolerance polygon: intersection of the ±rotate° angular
    sector off nominal track with the DME tolerance ring (0.25 NM fixed +
    1.25 % of distance), per ICAO Doc 8168.

    :param navid_geom: NAVID station point geometry (map CRS)
    :param fix_geom: Fix/threshold point geometry (map CRS)
    :param rotate: Sector half-angle in degrees
    :param da: QgsDistanceArea configured with the map CRS ellipsoid
    :return: (tolerance_area geometry, distance_nm)
    """
    azimuth = navid_geom.azimuth(fix_geom)
    length0 = navid_geom.distance(fix_geom)  # map units

    length0_m = da.measureLine(navid_geom, fix_geom)
    distance_nm = round(length0_m / 1852, 3)

    dme_tol_m = 0.25 * 1852 + 0.0125 * length0_m
    dme_tolerance = (dme_tol_m / length0_m) * length0 if length0_m > 0 else dme_tol_m

    pt1 = QgsPoint(navid_geom)
    proj2 = navid_geom.project(length0 * 5, azimuth + rotate)
    proj3 = navid_geom.project(length0 * 5, azimuth - rotate)
    pt2 = QgsPoint(proj2)
    pt3 = QgsPoint(proj3)
    sector = QgsGeometry(QgsPolygon(QgsLineString([pt1, pt2, pt3])))

    dme_circle = QgsGeometry(
        QgsCircle(QgsPoint(navid_geom), length0).toCircularString()
    ).buffer(dme_tolerance, 360)

    tolerance_area = sector.intersection(dme_circle)
    return tolerance_area, distance_nm


def run_dme_tolerance(iface, navid_layer, fix_layer, params=None):
    """
    Calculate a facility/DME fix tolerance area (VOR/DME, NDB/DME, or LOC/DME).

    :param iface: QGIS interface
    :param navid_layer: Point layer containing the station (NAVID)
    :param fix_layer: Point layer containing the fix/threshold point
    :param params: Optional dict; supports 'rotate' (sector half-angle in
        degrees, default 5.2) and 'nav_type' (label, default 'VOR/DME')
    :return: True on success, False on failure
    """
    if params is None:
        params = {}
    rotate = float(params.get('rotate', 5.2))
    nav_type = params.get('nav_type', 'VOR/DME')

    map_crs = iface.mapCanvas().mapSettings().destinationCrs()
    map_srid = map_crs.authid()
    project = QgsProject.instance()

    def show_error(msg):
        iface.messageBar().pushMessage("QPANSOPY:", msg, level=Qgis.Critical)

    navid_feature = get_selected_feature(navid_layer, show_error)
    if navid_feature is None:
        return False

    fix_feature = get_selected_feature(fix_layer, show_error)
    if fix_feature is None:
        return False

    # Transform both points to map CRS so calculations and output layer match
    navid_geom = _geom_to_map_crs(navid_feature, navid_layer, map_crs, project)
    fix_geom = _geom_to_map_crs(fix_feature, fix_layer, map_crs, project)

    da = QgsDistanceArea()
    da.setSourceCrs(map_crs, project.transformContext())
    da.setEllipsoid(project.ellipsoid())

    tolerance_area, distance_nm = build_tolerance_geometry(navid_geom, fix_geom, rotate, da)

    # Build result layer
    layer_name = f"{nav_type.replace('/', '')}_tolerance"
    v_layer = QgsVectorLayer(f"Polygon?crs={map_srid}", layer_name, "memory")
    pr = v_layer.dataProvider()
    pr.addAttributes([
        QgsField('Symbol', QVariant.String),
        QgsField('Distance_NM', QVariant.Double),
        QgsField('Sector_Angle', QVariant.Double),
    ])
    v_layer.updateFields()

    seg = QgsFeature()
    seg.setGeometry(tolerance_area)
    seg.setAttributes([f'{nav_type} Tolerance', distance_nm, rotate])
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
