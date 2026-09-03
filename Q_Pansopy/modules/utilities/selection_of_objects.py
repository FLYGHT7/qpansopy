# -*- coding: utf-8 -*-
"""
Object extraction module for QPANSOPY.

Provides extract_objects() to find obstacle points that fall inside
obstacle assessment surfaces, called from the Object Selection dockwidget.
"""

import datetime
import os
from typing import Sequence

from qgis.core import (
    QgsProject,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsSpatialIndex,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsMemoryProviderUtils,
    QgsGeometry,
    QgsSymbol,
    QgsSimpleMarkerSymbolLayer,
    QgsVectorFileWriter,
    Qgis,
)
from qgis.PyQt.QtGui import QColor

from ...utils import fix_kml_altitude_mode


def _prepare_surfaces(surface_features):
    """Index surface features and cache a prepared geometry engine for each.

    Geometries stay in the surface layer's own CRS (the working CRS for the
    intersection test), so nothing is transformed here. Preparing each geometry
    once lets the per-point test hit a GEOS prepared-geometry fast path instead
    of re-reading the surface provider.

    Each map value is an ``(engine, geometry)`` pair: the engine borrows a
    pointer into that geometry, so the geometry has to be kept alive for as
    long as the engine is used.

    :return: (index, {fid: (engine, geometry)}, combined bounding box)
    """
    index = QgsSpatialIndex()
    surfaces = {}
    surface_extent = None
    for feat in surface_features:
        geom = feat.geometry()
        if not geom or geom.isEmpty():
            continue
        fid = feat.id()
        bounding_box = geom.boundingBox()
        index.addFeature(fid, bounding_box)
        engine = QgsGeometry.createGeometryEngine(geom.constGet())
        engine.prepareGeometry()
        surfaces[fid] = (engine, geom)
        if surface_extent is None:
            surface_extent = bounding_box
        else:
            surface_extent.combineExtentWith(bounding_box)
    return index, surfaces, surface_extent


def _candidate_point_request(point_layer, surface_layer, surface_extent):
    """Build a provider-side bounding-box filter for obstacle candidates.

    A failed extent transformation only disables this optimization; the exact
    point transformation and intersection loop remain authoritative.
    """
    request = QgsFeatureRequest()
    if surface_extent is None:
        return request.setFilterFids([])

    candidate_extent = surface_extent
    if point_layer.crs() != surface_layer.crs():
        try:
            extent_transform = QgsCoordinateTransform(
                surface_layer.crs(),
                point_layer.crs(),
                QgsProject.instance(),
            )
            candidate_extent = extent_transform.transformBoundingBox(
                surface_extent
            )
        except Exception:
            return request

    return request.setFilterRect(candidate_extent)


def _create_result_layer(
        point_layer: QgsVectorLayer,
        features: Sequence[QgsFeature]) -> QgsVectorLayer:
    """Create a complete memory copy of the intersecting point features.

    ``QgsMemoryProviderUtils`` preserves the source field order and exact WKB
    type while converting field types unsupported by the memory provider. The
    batch is atomic: a failed conversion must never leave a partial result
    layer which looks like a successful extraction.
    """
    extracted_layer = QgsMemoryProviderUtils.createMemoryLayer(
        "Extracted Objects",
        point_layer.fields(),
        point_layer.wkbType(),
        point_layer.crs(),
        False,
    )
    if not extracted_layer or not extracted_layer.isValid():
        raise RuntimeError("Could not create the Extracted Objects memory layer")

    provider = extracted_layer.dataProvider()
    expected_count = len(features)
    if expected_count:
        flags = QgsFeatureSink.FastInsert | QgsFeatureSink.RollBackOnErrors
        inserted, _ = provider.addFeatures(list(features), flags)
    else:
        inserted = True

    actual_count = extracted_layer.featureCount()
    if not inserted or actual_count != expected_count:
        errors = [str(error) for error in provider.errors()]
        last_error = provider.lastError()
        if last_error and last_error not in errors:
            errors.append(last_error)
        details = "; ".join(errors) or "no provider error was reported"
        raise RuntimeError(
            f"Could not store all extracted objects: expected {expected_count}, "
            f"stored {actual_count}. Provider details: {details}"
        )

    return extracted_layer


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
    :param use_selection_only: Only use currently-selected features of
        surface_layer; every obstacle point inside those surfaces is considered
    :return: dict with 'count' and optionally 'kml_path'
    """
    work_crs = surface_layer.crs()

    xform = None
    if point_layer.crs() != work_crs:
        xform = QgsCoordinateTransform(
            point_layer.crs(), work_crs, QgsProject.instance()
        )

    surface_features = (
        surface_layer.selectedFeatures()
        if use_selection_only
        else surface_layer.getFeatures()
    )
    surface_index, surfaces, surface_extent = _prepare_surfaces(
        surface_features
    )
    point_request = _candidate_point_request(
        point_layer, surface_layer, surface_extent
    )
    point_features = point_layer.getFeatures(point_request)

    intersecting_features = []
    skipped_transforms = 0
    for pt in point_features:
        src_geom = pt.geometry()
        if not src_geom or src_geom.isEmpty():
            continue
        if xform is not None:
            test_geom = QgsGeometry(src_geom)
            try:
                # 0 == Qgis.GeometryOperationResult.Success (flat int, Qt5/Qt6 safe)
                failed = test_geom.transform(xform) != 0
            except Exception:
                # QgsCsException etc. - treat as an unreprojectable point
                failed = True
            if failed:
                skipped_transforms += 1
                continue
        else:
            test_geom = src_geom
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
    extracted_layer = _create_result_layer(
        point_layer, intersecting_features
    )

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

    result = {'count': extracted_layer.featureCount()}

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
