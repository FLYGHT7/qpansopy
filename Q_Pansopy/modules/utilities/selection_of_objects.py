# -*- coding: utf-8 -*-
"""
Object extraction module for QPANSOPY.

Provides extract_objects() to find obstacle points that intersect
obstacle assessment surfaces, called from the Object Selection dockwidget.
"""

import os
import datetime
from qgis.core import (
    QgsProject,
    QgsFeatureRequest,
    QgsSpatialIndex,
    QgsCoordinateTransform,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsFeature,
    QgsSymbol,
    QgsSimpleMarkerSymbolLayer,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    Qgis,
)
from qgis.PyQt.QtGui import QColor


def extract_objects(iface, point_layer, surface_layer,
                    export_kml=False, output_dir=None, use_selection_only=False):
    """
    Extract obstacle points that intersect any surface in *surface_layer*.

    :param iface: QGIS interface instance
    :param point_layer: QgsVectorLayer with obstacle points (any CRS)
    :param surface_layer: QgsVectorLayer with assessment surfaces (polygon)
    :param export_kml: Whether to export the result to a KML file
    :param output_dir: Directory for the KML file (required when export_kml=True)
    :param use_selection_only: Only process currently-selected features of point_layer
    :return: dict with 'count' and optionally 'kml_path', or None on failure
    """
    map_crs = QgsProject.instance().crs()

    # ----- Optional reprojection of obstacle layer -----
    if point_layer.crs() != map_crs:
        transform = QgsCoordinateTransform(point_layer.crs(), map_crs, QgsProject.instance())
        transformed_features = []
        source_features = (
            point_layer.selectedFeatures() if use_selection_only
            else point_layer.getFeatures()
        )
        for f in source_features:
            geom = f.geometry()
            if geom and not geom.isEmpty():
                geom.transform(transform)
                f.setGeometry(geom)
                transformed_features.append(f)

        work_layer = QgsVectorLayer(
            f"Point?crs={map_crs.authid()}", "reprojected_opea", "memory"
        )
        work_layer.dataProvider().addAttributes(point_layer.fields())
        work_layer.updateFields()
        work_layer.dataProvider().addFeatures(transformed_features)

        if point_layer.crs().authid() == 'EPSG:4326':
            iface.messageBar().pushMessage(
                "Reprojection Notice",
                f"'{point_layer.name()}' was reprojected from EPSG:4326 to match the map CRS.",
                level=Qgis.Info,
                duration=5,
            )
    else:
        work_layer = point_layer

    # ----- Spatial index & intersection test -----
    surface_index = QgsSpatialIndex(surface_layer.getFeatures())
    intersecting_features = []

    source_features = (
        work_layer.selectedFeatures() if use_selection_only
        else work_layer.getFeatures()
    )
    for pt in source_features:
        geom = pt.geometry()
        if not geom or geom.isEmpty():
            continue
        candidate_ids = surface_index.intersects(geom.boundingBox())
        for surf in surface_layer.getFeatures(
            QgsFeatureRequest().setFilterFids(candidate_ids)
        ):
            if geom.intersects(surf.geometry()):
                intersecting_features.append(pt)
                break

    # ----- Build result layer -----
    extracted_layer = QgsVectorLayer(
        f"Point?crs={work_layer.crs().authid()}", "Extracted Objects", "memory"
    )
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
            extracted_layer, kml_path, 'utf-8', kml_crs, 'KML'
        )
        if err[0] == QgsVectorFileWriter.NoError:
            result['kml_path'] = kml_path

    return result
