# -*- coding: utf-8 -*-
from .qpansopy_dme_tolerance_dockwidget import QPANSOPYDMEToleranceDockWidget


class QPANSOPYLOCDMEToleranceDockWidget(QPANSOPYDMEToleranceDockWidget):
    NAV_TYPE = 'LOC/DME'
    DEFAULT_ROTATE = 2.4
    POINT_LAYER_LABEL = 'LOC Point Layer'
