# -*- coding: utf-8 -*-
from .qpansopy_dme_tolerance_dockwidget import QPANSOPYDMEToleranceDockWidget


class QPANSOPYVORDMEToleranceDockWidget(QPANSOPYDMEToleranceDockWidget):
    NAV_TYPE = 'VOR/DME'
    DEFAULT_ROTATE = 5.2
    POINT_LAYER_LABEL = 'DME Point Layer'
