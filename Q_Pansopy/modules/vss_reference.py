"""Create and export the common VSS/OCS reference line at the threshold."""

import os
from typing import Optional

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsFeature, QgsField, QgsGeometry,
    QgsPoint, QgsPointXY, QgsVectorFileWriter, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..parameters_inspector_dialog import register_parameters_action
from ..utils import fix_kml_altitude_mode


REFERENCE_LINE_NAME = 'VSS_OCS_RWY_reference_line'
REFERENCE_LINE_BUFFER_M = 0.5 * 1852


def create_vss_reference_line(
        threshold: QgsPointXY, azimuth: float, surface_half_width_m: float,
        threshold_elevation_m: float, crs: QgsCoordinateReferenceSystem,
        parameters_json: str) -> QgsVectorLayer:
    """Build a transverse 3D line covering both surfaces plus the SID margin."""
    half_width = surface_half_width_m + REFERENCE_LINE_BUFFER_M
    points = []
    for xy in (
            threshold.project(half_width, azimuth - 90),
            threshold,
            threshold.project(half_width, azimuth + 90)):
        points.append(QgsPoint(xy.x(), xy.y(), threshold_elevation_m))

    layer = QgsVectorLayer('LineStringZ', REFERENCE_LINE_NAME, 'memory')
    layer.setCrs(crs)
    provider = layer.dataProvider()
    provider.addAttributes([
        QgsField('id', QVariant.Int),
        QgsField('description', QVariant.String),
        QgsField('parameters', QVariant.String),
    ])
    layer.updateFields()
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPolyline(points))
    feature.setAttributes([1, 'VSS/OCS runway reference line at THR', parameters_json])
    provider.addFeatures([feature])
    layer.updateExtents()
    layer.renderer().symbol().setColor(QColor('purple'))
    layer.renderer().symbol().setWidth(0.5)
    register_parameters_action(layer)
    layer.triggerRepaint()
    return layer


def export_vss_reference_line(
        layer: QgsVectorLayer, output_dir: str, timestamp: str) -> Optional[str]:
    """Return the KML path only after writing and fixing absolute altitude."""
    path = os.path.join(output_dir, f'{REFERENCE_LINE_NAME}_{timestamp}.kml')
    error = QgsVectorFileWriter.writeAsVectorFormat(
        layer, path, 'utf-8', QgsCoordinateReferenceSystem('EPSG:4326'),
        'KML', layerOptions=['MODE=2'],
    )
    if error[0] != QgsVectorFileWriter.NoError:
        return None
    if not fix_kml_altitude_mode(path):
        return None
    return path
