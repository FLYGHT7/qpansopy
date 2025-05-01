# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QPANSOPYAlgorithm
                                 A QGIS plugin
 Procedure Analysis and Obstacle Protection Surfaces - Processing Algorithms
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
import processing
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFolderDestination,
    QgsProcessingOutputVectorLayer,
    QgsProcessingParameterFileDestination,
    QgsVectorLayer,
    QgsWkbTypes
)
from PyQt5.QtGui import QIcon

class VSSAlgorithm(QgsProcessingAlgorithm):
    """
    Algorithm for calculating VSS (Visual Segment Surface)
    """
    
    # Constants used to refer to parameters and outputs
    INPUT_POINT = 'INPUT_POINT'
    INPUT_RUNWAY = 'INPUT_RUNWAY'
    VSS_TYPE = 'VSS_TYPE'
    RWY_WIDTH = 'RWY_WIDTH'
    THR_ELEV = 'THR_ELEV'
    STRIP_WIDTH = 'STRIP_WIDTH'
    OCH = 'OCH'
    RDH = 'RDH'
    VPA = 'VPA'
    EXPORT_KML = 'EXPORT_KML'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    OUTPUT_VSS = 'OUTPUT_VSS'
    OUTPUT_OCS = 'OUTPUT_OCS'
    
    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm
        """
        # Add input parameters
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POINT,
                'Threshold Point Layer (WGS84)',
                [QgsProcessing.TypeVectorPoint]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_RUNWAY,
                'Runway Line Layer (Projected)',
                [QgsProcessing.TypeVectorLine]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.VSS_TYPE,
                'VSS Type',
                options=['Straight In NPA', 'ILS/LOC/APV'],
                defaultValue=0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RWY_WIDTH,
                'Runway Width (m)',
                QgsProcessingParameterNumber.Double,
                45.0,
                minValue=10.0,
                maxValue=100.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THR_ELEV,
                'Threshold Elevation (m)',
                QgsProcessingParameterNumber.Double,
                22.0,
                minValue=-100.0,
                maxValue=5000.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STRIP_WIDTH,
                'Strip Width (m)',
                QgsProcessingParameterNumber.Double,
                280.0,
                minValue=50.0,
                maxValue=500.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.OCH,
                'OCH (m)',
                QgsProcessingParameterNumber.Double,
                140.21,
                minValue=10.0,
                maxValue=500.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RDH,
                'RDH (m)',
                QgsProcessingParameterNumber.Double,
                15.0,
                minValue=5.0,
                maxValue=50.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.VPA,
                'VPA (degrees)',
                QgsProcessingParameterNumber.Double,
                3.0,
                minValue=2.0,
                maxValue=6.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.EXPORT_KML,
                'Export to KML',
                defaultValue=True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                'Output Folder',
                optional=True
            )
        )
        
        # Add output parameters
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_VSS,
                'VSS Layer'
            )
        )
        
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_OCS,
                'OCS Layer'
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        """
        Process the algorithm
        """
        # Get parameters
        point_layer = self.parameterAsVectorLayer(parameters, self.INPUT_POINT, context)
        runway_layer = self.parameterAsVectorLayer(parameters, self.INPUT_RUNWAY, context)
        vss_type_idx = self.parameterAsEnum(parameters, self.VSS_TYPE, context)
        rwy_width = self.parameterAsDouble(parameters, self.RWY_WIDTH, context)
        thr_elev = self.parameterAsDouble(parameters, self.THR_ELEV, context)
        strip_width = self.parameterAsDouble(parameters, self.STRIP_WIDTH, context)
        och = self.parameterAsDouble(parameters, self.OCH, context)
        rdh = self.parameterAsDouble(parameters, self.RDH, context)
        vpa = self.parameterAsDouble(parameters, self.VPA, context)
        export_kml = self.parameterAsBool(parameters, self.EXPORT_KML, context)
        output_dir = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        
        # Prepare parameters
        params = {
            'rwy_width': rwy_width,
            'thr_elev': thr_elev,
            'strip_width': strip_width,
            'OCH': och,
            'RDH': rdh,
            'VPA': vpa,
            'export_kml': export_kml,
            'output_dir': output_dir
        }
        
        # Get QGIS interface
        from qgis.utils import iface
        
        # Run calculation based on type
        if vss_type_idx == 0:  # Straight In NPA
            feedback.pushInfo("Running VSS Straight In NPA calculation...")
            from .modules.vss_straight import calculate_vss_straight
            result = calculate_vss_straight(iface, point_layer, runway_layer, params)
        else:  # ILS/LOC/APV
            feedback.pushInfo("Running VSS ILS/LOC/APV calculation...")
            from .modules.vss_loc import calculate_vss_loc
            result = calculate_vss_loc(iface, point_layer, runway_layer, params)
        
        # Return results
        outputs = {
            self.OUTPUT_VSS: result['vss_layer'].id(),
            self.OUTPUT_OCS: result['ocs_layer'].id()
        }
        
        return outputs
    
    def name(self):
        """
        Returns the algorithm name
        """
        return 'vss'
    
    def displayName(self):
        """
        Returns the algorithm display name
        """
        return 'Visual Segment Surface (VSS)'
    
    def group(self):
        """
        Returns the name of the group this algorithm belongs to
        """
        return 'QPANSOPY'
    
    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to
        """
        return 'qpansopy'
    
    def shortHelpString(self):
        """
        Returns a short help string for the algorithm
        """
        return 'Calculates Visual Segment Surface (VSS) for approach procedures'
    
    def createInstance(self):
        """
        Creates a new instance of the algorithm
        """
        return VSSAlgorithm()
    
    def icon(self):
        """
        Returns the algorithm icon
        """
        return QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'vss_icon.png'))


class BasicILSAlgorithm(QgsProcessingAlgorithm):
    """
    Algorithm for calculating Basic ILS Surfaces
    """
    
    # Constants used to refer to parameters and outputs
    INPUT_POINT = 'INPUT_POINT'
    INPUT_RUNWAY = 'INPUT_RUNWAY'
    THR_ELEV = 'THR_ELEV'
    EXPORT_KML = 'EXPORT_KML'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    OUTPUT_LAYER = 'OUTPUT_LAYER'
    
    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm
        """
        # Add input parameters
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POINT,
                'Threshold Point Layer (WGS84)',
                [QgsProcessing.TypeVectorPoint]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_RUNWAY,
                'Runway Line Layer (Projected)',
                [QgsProcessing.TypeVectorLine]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THR_ELEV,
                'Threshold Elevation (m)',
                QgsProcessingParameterNumber.Double,
                985.11,
                minValue=-100.0,
                maxValue=5000.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.EXPORT_KML,
                'Export to KML',
                defaultValue=True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                'Output Folder',
                optional=True
            )
        )
        
        # Add output parameters
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_LAYER,
                'Basic ILS Surfaces Layer'
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        """
        Process the algorithm
        """
        # Get parameters
        point_layer = self.parameterAsVectorLayer(parameters, self.INPUT_POINT, context)
        runway_layer = self.parameterAsVectorLayer(parameters, self.INPUT_RUNWAY, context)
        thr_elev = self.parameterAsDouble(parameters, self.THR_ELEV, context)
        export_kml = self.parameterAsBool(parameters, self.EXPORT_KML, context)
        output_dir = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        
        # Prepare parameters
        params = {
            'thr_elev': thr_elev,
            'export_kml': export_kml,
            'output_dir': output_dir
        }
        
        # Get QGIS interface
        from qgis.utils import iface
        
        # Run calculation
        feedback.pushInfo("Running Basic ILS calculation...")
        from .modules.basic_ils import calculate_basic_ils
        result = calculate_basic_ils(iface, point_layer, runway_layer, params)
        
        # Return results
        outputs = {
            self.OUTPUT_LAYER: result['layer'].id()
        }
        
        return outputs
    
    def name(self):
        """
        Returns the algorithm name
        """
        return 'basic_ils'
    
    def displayName(self):
        """
        Returns the algorithm display name
        """
        return 'Basic ILS Surfaces'
    
    def group(self):
        """
        Returns the name of the group this algorithm belongs to
        """
        return 'QPANSOPY'
    
    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to
        """
        return 'qpansopy'
    
    def shortHelpString(self):
        """
        Returns a short help string for the algorithm
        """
        return 'Calculates Basic ILS Surfaces for approach procedures'
    
    def createInstance(self):
        """
        Creates a new instance of the algorithm
        """
        return BasicILSAlgorithm()
    
    def icon(self):
        """
        Returns the algorithm icon
        """
        return QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'ils_icon.png'))