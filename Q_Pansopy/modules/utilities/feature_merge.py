# -*- coding: utf-8 -*-
"""
/***************************************************************************
Feature Merge Module
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - Feature Merge Module
                        -------------------
   begin                : 2025-07-29
   git sha              : $Format:%H$
   copyright            : (C) 2025 by QPANSOPY Team
   email                : support@qpansopy.com
***************************************************************************/

/***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************/
"""

import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsWkbTypes, QgsFeature,
    QgsFields, QgsField, QgsFeatureRequest
)
from PyQt5.QtCore import QVariant


def merge_selected_layers(iface, selected_layers=None, merged_layer_name="Merged_Layer", output_dir=None):
    """
    Merge multiple vector layers into a single layer
    
    Args:
        iface: QGIS interface
        selected_layers: List of QgsVectorLayer objects to merge (optional, uses selected layers if None)
        merged_layer_name: Name for the resulting merged layer
        output_dir: Output directory (optional)
    
    Returns:
        dict: Results with layer information and counts
    """
    
    # Get selected layers if not provided
    if selected_layers is None:
        selected_layers = iface.layerTreeView().selectedLayers()
    
    # Filter to only vector layers
    selected_layers = [layer for layer in selected_layers if isinstance(layer, QgsVectorLayer)]
    
    if len(selected_layers) < 2:
        raise ValueError("Select at least two vector layers.")
    
    # Check geometry and CRS compatibility
    geom_type = selected_layers[0].wkbType()
    crs = selected_layers[0].crs()
    for layer in selected_layers[1:]:
        if layer.wkbType() != geom_type:
            raise ValueError("Geometry types differ between layers.")
        if layer.crs() != crs:
            raise ValueError("CRS differ between layers.")
    
    # Build union of all fields
    all_fields = QgsFields()
    field_names = {}
    
    for layer in selected_layers:
        for field in layer.fields():
            if field.name() not in field_names:
                all_fields.append(QgsField(field.name(), field.type()))
                field_names[field.name()] = field.type()
    
    # Create memory layer
    merged_layer = QgsVectorLayer(f"{QgsWkbTypes.displayString(geom_type)}?crs={crs.authid()}", merged_layer_name, "memory")
    merged_provider = merged_layer.dataProvider()
    merged_provider.addAttributes(all_fields)
    merged_layer.updateFields()
    
    # Add features from each layer
    total_features = 0
    layer_counts = {}
    
    for layer in selected_layers:
        layer_feature_count = 0
        for feature in layer.getFeatures():
            new_feat = QgsFeature(merged_layer.fields())
            new_feat.setGeometry(feature.geometry())
            for field in layer.fields():
                if field.name() in field_names:
                    new_feat.setAttribute(field.name(), feature[field.name()])
            merged_provider.addFeature(new_feat)
            layer_feature_count += 1
            total_features += 1
        
        layer_counts[layer.name()] = layer_feature_count
    
    merged_layer.updateExtents()
    QgsProject.instance().addMapLayer(merged_layer)
    
    return {
        'success': True,
        'merged_layer': merged_layer,
        'total_features': total_features,
        'layer_counts': layer_counts,
        'source_layers': [layer.name() for layer in selected_layers],
        'geometry_type': QgsWkbTypes.displayString(geom_type),
        'crs': crs.authid()
    }
