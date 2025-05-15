# -*- coding: utf-8 -*-
"""
/***************************************************************************
Utility functions for QPANSOPY
                            A QGIS plugin
Procedure Analysis and Obstacle Protection Surfaces
                        -------------------
   begin                : 2023-04-29
   git sha              : $Format:%H$
   copyright            : (C) 2023 by Your Name
   email                : your.email@example.com
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

from qgis.core import Qgis

def get_selected_feature(layer, error_callback=None):
    """
    Obtiene la feature a utilizar según las reglas de selección:
    1. Si no hay features seleccionadas y solo hay una feature, usa esa feature
    2. Si hay features seleccionadas y solo una está seleccionada, usa esa feature
    3. Si hay múltiples features seleccionadas, muestra un error
    
    :param layer: Capa de entrada (QgsVectorLayer)
    :param error_callback: Función para mostrar mensajes de error (opcional)
    :return: QgsFeature o None si hay un error
    """
    if not layer:
        if error_callback:
            error_callback("No layer provided")
        return None
    
    # Verificar si hay features seleccionadas
    selected_count = layer.selectedFeatureCount()
    
    if selected_count == 0:
        # No hay features seleccionadas
        feature_count = layer.featureCount()
        if feature_count == 0:
            # No hay features en la capa
            if error_callback:
                error_callback("No features found in the layer")
            return None
        elif feature_count == 1:
            # Solo hay una feature en la capa, usarla
            return next(layer.getFeatures())
        else:
            # Hay múltiples features, mostrar error
            if error_callback:
                error_callback("Multiple features found but none selected. Please select one feature.")
            return None
    elif selected_count == 1:
        # Hay exactamente una feature seleccionada, usarla
        return next(layer.selectedFeatures())
    else:
        # Hay múltiples features seleccionadas, mostrar error
        if error_callback:
            error_callback("Multiple features selected. Please select only one feature.")
        return None