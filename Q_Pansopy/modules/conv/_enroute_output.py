"""Shared single-layer output for straight VOR/VOR en-route areas."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsGeometry,
        QgsVectorLayer,
    )


_AREA_STYLE = (
    Path(__file__).resolve().parents[2]
    / "styles"
    / "primary_secondary_areas.qml"
)


def _create_enroute_area_layer(
    name: str,
    primary: QgsGeometry,
    outer: QgsGeometry,
    outer_area_type: Literal["Secondary area", "Buffer area"],
    case: int,
    distance_nm: float,
    crs: QgsCoordinateReferenceSystem,
    method: Literal["Simplified", "Refined"],
) -> QgsVectorLayer:
    """Create one categorized layer containing primary and outer areas."""
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import (
        QgsCategorizedSymbolRenderer,
        QgsFeature,
        QgsField,
        QgsMapLayer,
        QgsRendererCategory,
    )
    from ..pbn.dme_dme_coverage import _new_layer

    if outer_area_type not in ("Secondary area", "Buffer area"):
        raise ValueError("outer_area_type must be 'Secondary area' or 'Buffer area'")

    if method not in ("Simplified", "Refined"):
        raise ValueError("Unsupported ENR method")

    layer = _new_layer("Polygon", name, crs, [
        QgsField("area_type", QVariant.String),
        QgsField("case", QVariant.Int),
        QgsField("distance_nm", QVariant.Double),
        QgsField("method", QVariant.String),
    ])

    message, loaded = layer.loadNamedStyle(
        str(_AREA_STYLE),
        categories=QgsMapLayer.StyleCategory.Symbology,
    )
    if not loaded:
        raise RuntimeError("Could not load ENR area symbology: {0}".format(message))

    style_renderer = layer.renderer()
    if not isinstance(style_renderer, QgsCategorizedSymbolRenderer):
        raise RuntimeError("The shared PBN area style has no categorized renderer")
    symbols = {
        category.value(): category.symbol().clone()
        for category in style_renderer.categories()
        if category.value() in ("Primary Area", "Secondary Area")
    }
    if set(symbols) != {"Primary Area", "Secondary Area"}:
        raise RuntimeError("The shared PBN area style is missing an area category")

    category_value = {
        "Primary area": "Primary Area",
        "Secondary area": "Secondary Area",
        "Buffer area": "Secondary Area",
    }
    categories = [
        QgsRendererCategory(
            area_type,
            symbols[category_value[area_type]].clone(),
            label,
        )
        for area_type, label in (
            ("Primary area", "Primary Area"),
            (
                outer_area_type,
                "Buffer Area" if outer_area_type == "Buffer area" else "Secondary Area",
            ),
        )
    ]
    layer.setRenderer(QgsCategorizedSymbolRenderer("area_type", categories))

    features = []
    for geometry, area_type in (
        (primary, "Primary area"),
        (outer, outer_area_type),
    ):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        feature.setAttributes([area_type, case, distance_nm, method])
        features.append(feature)
    success, _ = layer.dataProvider().addFeatures(features)
    if not success:
        raise RuntimeError("Could not populate the ENR area layer")
    layer.updateExtents()
    return layer
