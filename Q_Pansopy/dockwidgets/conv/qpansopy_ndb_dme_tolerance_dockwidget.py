# -*- coding: utf-8 -*-
from .qpansopy_dme_tolerance_dockwidget import QPANSOPYDMEToleranceDockWidget


class QPANSOPYNDBDMEToleranceDockWidget(QPANSOPYDMEToleranceDockWidget):
    NAV_TYPE = 'NDB/DME'
    DEFAULT_ROTATE = 6.9
    POINT_LAYER_LABEL = 'NDB Point Layer'
