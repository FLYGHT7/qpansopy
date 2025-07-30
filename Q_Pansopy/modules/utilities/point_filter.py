# -*- coding: utf-8 -*-
"""
/***************************************************************************
Point Filter Module
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces - Point Filter Module
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
from qgis.core import (QgsVectorLayer, QgsField, QgsFeature, QgsProject, 
                       QgsSymbol)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QVariant


def filter_points_by_elevation(iface, point_layer, thr_elevation, output_dir=None, 
                              higher_color=None, lower_color=None, point_size=0.5):
    """
    Filter points based on THR elevation threshold
    
    Args:
        iface: QGIS interface
        point_layer: Input point layer with 'elev' field
        thr_elevation: Threshold elevation value (float)
        output_dir: Output directory (optional)
        higher_color: QColor for points above threshold (default: red)
        lower_color: QColor for points below threshold (default: green)
        point_size: Size of point symbols (default: 0.5)
    
    Returns:
        dict: Results with layer information and counts
    """
    if point_layer is None:
        raise ValueError("No point layer provided")
    
    # Set default colors if not provided
    if higher_color is None:
        higher_color = QColor("red")
    if lower_color is None:
        lower_color = QColor("green")
    
    # Get CRS from input layer
    crs = point_layer.crs().authid()
    
    # Create memory layers
    mem_layer_name = point_layer.name() + "_higher_than_THR_elev"
    mem_layer = QgsVectorLayer(f"Point?crs={crs}", mem_layer_name, "memory")
    mem_layer_data = mem_layer.dataProvider()
    
    # Copy all fields from source layer
    fields = point_layer.fields()
    for field in fields:
        mem_layer_data.addAttributes([field])
    
    # Add custom fields x_dist, y_dist, z_height
    mem_layer_data.addAttributes([
        QgsField("x_dist", QVariant.Double, "double", 10, 3),
        QgsField("y_dist", QVariant.Double, "double", 10, 3),
        QgsField("z_height", QVariant.Double, "double", 10, 3)
    ])
    
    mem_layer.updateFields()
    
    # Create lower layer
    lower_layer_name = point_layer.name() + "_lower_than_THR_elev"
    lower_layer = QgsVectorLayer(f"Point?crs={crs}", lower_layer_name, "memory")
    lower_layer_data = lower_layer.dataProvider()
    
    # Copy all fields from source layer
    fields_lower = point_layer.fields()
    for field in fields_lower:
        lower_layer_data.addAttributes([field])
    
    # Add custom fields x_dist, y_dist, z_height
    lower_layer_data.addAttributes([
        QgsField("x_dist", QVariant.Double, "double", 10, 3),
        QgsField("y_dist", QVariant.Double, "double", 10, 3),
        QgsField("z_height", QVariant.Double, "double", 10, 3)
    ])
    
    lower_layer.updateFields()
    
    # Start editing
    mem_layer.startEditing()
    lower_layer.startEditing()
    
    try:
        # Get field indices
        idx_value = point_layer.fields().indexFromName("elev")
        if idx_value == -1:
            raise ValueError("Input layer must have an 'elev' field")
        
        # Setup symbology
        # Custom symbols for points above threshold
        sym_above = QgsSymbol.defaultSymbol(mem_layer.geometryType())
        sym_above.setColor(higher_color)
        sym_above.setSize(point_size)
        sym_above.symbolLayer(0).setStrokeStyle(Qt.NoPen)
        mem_layer.renderer().setSymbol(sym_above)
        
        # Custom symbols for points below threshold
        sym_below = QgsSymbol.defaultSymbol(lower_layer.geometryType())
        sym_below.setColor(lower_color)
        sym_below.setSize(point_size)
        sym_below.symbolLayer(0).setStrokeStyle(Qt.NoPen)
        lower_layer.renderer().setSymbol(sym_below)
        
        higher_count = 0
        lower_count = 0
        
        # Process each feature
        for feature in point_layer.getFeatures():
            value = feature[idx_value]
            
            if value >= thr_elevation:
                # Create new feature for higher layer
                new_feature_higher = QgsFeature()
                new_feature_higher.setGeometry(feature.geometry())
                new_feature_higher.setAttributes(feature.attributes())
                
                # Calculate z_height
                z_height = value - thr_elevation
                
                # Set custom field values before adding feature
                attributes = new_feature_higher.attributes()
                attributes.extend([0.0, 0.0, z_height])  # x_dist, y_dist, z_height
                new_feature_higher.setAttributes(attributes)
                
                # Add feature to higher layer
                mem_layer_data.addFeature(new_feature_higher)
                higher_count += 1
                
            else:
                # Create new feature for lower layer
                new_feature_lower = QgsFeature()
                new_feature_lower.setGeometry(feature.geometry())
                new_feature_lower.setAttributes(feature.attributes())
                
                # Calculate z_height (will be negative)
                z_height_lower = value - thr_elevation
                
                # Set custom field values before adding feature
                attributes = new_feature_lower.attributes()
                attributes.extend([0.0, 0.0, z_height_lower])  # x_dist, y_dist, z_height
                new_feature_lower.setAttributes(attributes)
                
                # Add feature to lower layer
                lower_layer_data.addFeature(new_feature_lower)
                lower_count += 1
        
        # Commit changes
        mem_layer.commitChanges()
        lower_layer.commitChanges()
        
        # Add layers to project
        QgsProject.instance().addMapLayer(mem_layer)
        QgsProject.instance().addMapLayer(lower_layer)
        
        return {
            'success': True,
            'higher_layer': mem_layer,
            'lower_layer': lower_layer,
            'higher_count': higher_count,
            'lower_count': lower_count,
            'threshold': thr_elevation
        }
        
    except Exception as e:
        # Rollback changes if error occurs
        mem_layer.rollBack()
        lower_layer.rollBack()
        raise e