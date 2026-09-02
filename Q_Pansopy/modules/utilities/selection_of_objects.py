# -*- coding: utf-8 -*-
"""
Object extraction module for QPANSOPY.

Provides extract_objects() to find obstacle points that fall inside
obstacle assessment surfaces, called from the Object Selection dockwidget.
"""

import os
import datetime
from qgis.core import (
    QgsProject,
    QgsSpatialIndex,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsGeometry,
    QgsSymbol,
    QgsSimpleMarkerSymbolLayer,
    QgsVectorFileWriter,
    Qgis,
)
from qgis.PyQt.QtGui import QColor

from ...utils import fix_kml_altitude_mode


def _prepare_surfaces(surface_layer):
    """Index every surface feature and cache a prepared geometry engine for it.

    Geometries stay in the surface layer's own CRS (the working CRS for the
    intersection test), so nothing is transformed here. Preparing each geometry
    once lets the per-point test hit a GEOS prepared-geometry fast path instead
    of re-reading the surface provider.

    Each map value is an ``(engine, geometry)`` pair: the engine borrows a
    pointer into that geometry, so the geometry has to be kept alive for as
    long as the engine is used.

    :return: (QgsSpatialIndex, {fid: (QgsGeometryEngine, QgsGeometry)})
    """
    index = QgsSpatialIndex()
    surfaces = {}
    for feat in surface_layer.getFeatures():
        geom = feat.geometry()
        if not geom or geom.isEmpty():
            continue
        fid = feat.id()
        index.addFeature(fid, geom.boundingBox())
        engine = QgsGeometry.createGeometryEngine(geom.constGet())
        engine.prepareGeometry()
        surfaces[fid] = (engine, geom)
    return index, surfaces


def extract_objects(iface, point_layer, surface_layer,
                    export_kml=False, output_dir=None, use_selection_only=False):
    """
    Extract obstacle points that fall inside any surface of *surface_layer*.

    The intersection test runs entirely in the surface layer's CRS; obstacle
    point geometries are transformed into it on the fly when the two layers
    differ. The project/canvas CRS does not affect the result.

    :param iface: QGIS interface instance
    :param point_layer: QgsVectorLayer with obstacle points (any CRS)
    :param surface_layer: QgsVectorLayer with assessment surfaces (polygon)
    :param export_kml: Whether to export the result to a KML file
    :param output_dir: Directory for the KML file (required when export_kml=True)
    :param use_selection_only: Only process currently-selected features of
        point_layer; every surface feature is always considered
    :return: dict with 'count' and optionally 'kml_path'
    """
    work_crs = surface_layer.crs()

    xform = None
    if point_layer.crs() != work_crs:
        xform = QgsCoordinateTransform(
            point_layer.crs(), work_crs, QgsProject.instance()
        )

    surface_index, surfaces = _prepare_surfaces(surface_layer)

    point_features = (
        point_layer.selectedFeatures() if use_selection_only
        else point_layer.getFeatures()
    )

    intersecting_features = []
    skipped_transforms = 0
    for pt in point_features:
        src_geom = pt.geometry()
        if not src_geom or src_geom.isEmpty():
            continue
        test_geom = QgsGeometry(src_geom)
        if xform is not None:
            try:
                # 0 == Qgis.GeometryOperationResult.Success (flat int, Qt5/Qt6 safe)
                failed = test_geom.transform(xform) != 0
            except Exception:
                # QgsCsException etc. - treat as an unreprojectable point
                failed = True
            if failed:
                skipped_transforms += 1
                continue
        abstract = test_geom.constGet()
        for fid in surface_index.intersects(test_geom.boundingBox()):
            if surfaces[fid][0].intersects(abstract):
                intersecting_features.append(pt)
                break

    if skipped_transforms:
        iface.messageBar().pushMessage(
            "QPANSOPY:",
            "{0} obstacle point(s) could not be reprojected to the surface "
            "CRS and were skipped".format(skipped_transforms),
            level=Qgis.Warning,
        )

    # ----- Build result layer (original, untransformed geometries) -----
    # setCrs() with the CRS object, not an authid string: a custom/unregistered
    # point-layer CRS has an empty authid and would yield an invalid layer.
    extracted_layer = QgsVectorLayer("Point", "Extracted Objects", "memory")
    extracted_layer.setCrs(point_layer.crs())
    extracted_layer.dataProvider().addAttributes(point_layer.fields())
    extracted_layer.updateFields()
    extracted_layer.dataProvider().addFeatures(intersecting_features)

    # Style: red dots, size 3, no stroke
    symbol = QgsSymbol.defaultSymbol(extracted_layer.geometryType())
    sym_layer = QgsSimpleMarkerSymbolLayer()
    sym_layer.setColor(QColor("red"))
    sym_layer.setSize(3)
    sym_layer.setStrokeColor(QColor(0, 0, 0, 0))
    sym_layer.setStrokeWidth(0)
    symbol.changeSymbolLayer(0, sym_layer)
    extracted_layer.renderer().setSymbol(symbol)

    extracted_layer.updateExtents()
    QgsProject.instance().addMapLayer(extracted_layer)

    result = {'count': len(intersecting_features)}

    # ----- Optional KML export -----
    if export_kml and output_dir:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        kml_path = os.path.join(output_dir, f"extracted_objects_{timestamp}.kml")
        kml_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        err = QgsVectorFileWriter.writeAsVectorFormat(
            extracted_layer, kml_path, 'utf-8', kml_crs, 'KML',
            layerOptions=['MODE=2']
        )
        if err[0] == QgsVectorFileWriter.NoError:
            fix_kml_altitude_mode(kml_path)
            result['kml_path'] = kml_path
        else:
            iface.messageBar().pushMessage(
                "QPANSOPY:", "KML export failed", level=Qgis.Warning
            )

    return result
