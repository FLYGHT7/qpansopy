# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QPANSOPY
                                 A QGIS plugin
 Procedure Analysis and Obstacle Protection Surfaces
                             -------------------
        begin                : 2023-04-29
        copyright            : (C) 2023 by Your Name
        email                : your.email@example.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

def classFactory(iface):
    """Load Qpansopy class from file qpansopy.py.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .qpansopy import Qpansopy
    return Qpansopy(iface)