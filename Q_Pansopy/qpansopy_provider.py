# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QPANSOPYProvider
                                 A QGIS plugin
 Procedure Analysis and Obstacle Protection Surfaces - Processing Provider
                             -------------------
        begin                : 2023-04-29
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

import os
from qgis.core import QgsProcessingProvider
from PyQt5.QtGui import QIcon
from .qpansopy_algorithm import (
    VSSAlgorithm,
    BasicILSAlgorithm
)

class QPANSOPYProvider(QgsProcessingProvider):
    """
    Processing provider for QPANSOPY algorithms
    """

    def __init__(self):
        QgsProcessingProvider.__init__(self)

    def load(self):
        """
        Called when the provider is first loaded
        """
        self.refreshAlgorithms()
        return True

    def unload(self):
        """
        Called when the provider is unloaded
        """
        pass

    def name(self):
        """
        Returns the unique provider name
        """
        return 'qpansopy'

    def longName(self):
        """
        Returns the provider's full name
        """
        return 'QPANSOPY'

    def id(self):
        """
        Returns the provider ID
        """
        return 'qpansopy'

    def icon(self):
        """
        Returns the provider icon
        """
        return QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'vss_icon.png'))

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider
        """
        self.addAlgorithm(VSSAlgorithm())
        self.addAlgorithm(BasicILSAlgorithm())