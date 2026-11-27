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


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load QPANSOPY class from file QPANSOPY.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import QT_VERSION_STR, PYQT_VERSION_STR

    if (not 40000 <= Qgis.QGIS_VERSION_INT < 50000
            or QT_VERSION_STR.split('.')[0] != '6'
            or PYQT_VERSION_STR.split('.')[0] != '6'):
        raise RuntimeError(
            'QPANSOPY requires QGIS 4 with Qt6 and PyQt6 '
            f'(found QGIS version {Qgis.QGIS_VERSION_INT}, '
            f'Qt {QT_VERSION_STR}, PyQt {PYQT_VERSION_STR}).')

    from .qpansopy import Qpansopy
    return Qpansopy(iface)
