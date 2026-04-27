# -*- coding: utf-8 -*-
"""Shared helpers for LNAV approach generator modules.

These utilities centralise the repetitive boilerplate that appears in every
``PBN_LNAV_*.py`` file so that each file contains only its unique geometry
logic.
"""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsFeature,
    QgsPolygon, QgsLineString, QgsPoint, Qgis,
)
from qgis.PyQt.QtCore import QVariant
import os


def _resolve_routing_layer(iface, routing_layer):
    """Return a valid routing layer, falling back to a project-wide search.

    Displays a *Critical* bar message and returns ``None`` when no layer is
    found.
    """
    if routing_layer is None:
        for layer in QgsProject.instance().mapLayers().values():
            if "routing" in layer.name().lower():
                routing_layer = layer
                break
    if routing_layer is None:
        iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
    return routing_layer


def _select_segment_features(iface, routing_layer, segment_type):
    """Return the user-selected features whose *segment* attribute matches *segment_type*.

    Relies on ``QgsVectorLayer.selectedFeatures()`` — the caller must ensure
    the user has made a selection.  Returns ``None`` on any validation failure.
    """
    selected = routing_layer.selectedFeatures()
    if not selected:
        iface.messageBar().pushMessage(
            "Please select at least one segment in the routing layer",
            level=Qgis.Critical,
        )
        return None
    filtered = [f for f in selected if f.attribute("segment") == segment_type]
    if not filtered:
        iface.messageBar().pushMessage(
            f"No '{segment_type}' segment found in your selection",
            level=Qgis.Critical,
        )
        return None
    return filtered


def _extract_segment_geom(iface, features, segment_type):
    """Extract geometry data from the first valid polyline in *features*.

    Returns ``(start_point, end_point, azimuth, back_azimuth, length)`` or
    ``None`` when no valid geometry is found.  Uses ``geom[1]`` as end-point
    (FAF→MAPt convention).
    """
    for feat in features:
        try:
            geom = feat.geometry().asPolyline()
            if geom and len(geom) >= 2:
                start_point = QgsPoint(geom[0])
                end_point = QgsPoint(geom[1])
                azimuth = start_point.azimuth(end_point)
                return start_point, end_point, azimuth, azimuth + 180, feat.geometry().length()
        except Exception:
            iface.messageBar().pushMessage(
                "Invalid geometry in selected feature", level=Qgis.Warning
            )
    iface.messageBar().pushMessage(
        f"No valid geometry found in selected {segment_type} segments",
        level=Qgis.Critical,
    )
    return None


def _create_area_layer(map_srid, layer_name, areas, module_file):
    """Create, populate, and add a LNAV protection-area memory layer to the project.

    Parameters
    ----------
    map_srid:
        CRS authority string (e.g. ``'EPSG:32632'``) for the new layer.
    layer_name:
        Name shown in the QGIS layer tree.
    areas:
        Iterable of ``([QgsPoint, …], symbol_string)`` tuples, one per area.
    module_file:
        ``__file__`` from the calling module; used to resolve the shared QML
        style relative to the calling file.

    Returns
    -------
    QgsVectorLayer
        The fully populated and styled layer.
    """
    v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", layer_name, "memory")
    v_layer.dataProvider().addAttributes([QgsField("Symbol", QVariant.String)])
    v_layer.updateFields()

    features = []
    for vertices, symbol in areas:
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(vertices), rings=[]))
        seg.setAttributes([symbol])
        features.append(seg)

    v_layer.dataProvider().addFeatures(features)
    v_layer.updateExtents()
    QgsProject.instance().addMapLayers([v_layer])

    style_path = os.path.join(
        os.path.dirname(module_file), "..", "..", "styles", "primary_secondary_areas.qml"
    )
    if os.path.exists(style_path):
        v_layer.loadNamedStyle(style_path)

    return v_layer
