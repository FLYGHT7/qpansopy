from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsField,
    QgsGeometry, Qgis
)
from qgis.PyQt.QtCore import QVariant
import os

_NM_TO_M = 1852.0
_SEGMENTS = 360


def run_pbn_target(iface, point_layer):
    """Create 15 NM and 30 NM ARP buffer rings from a point layer."""
    try:
        if point_layer is None:
            iface.messageBar().pushMessage('QPANSOPY', 'No point layer provided', level=Qgis.Critical)
            return None

        layer_crs = point_layer.crs()
        if layer_crs.isGeographic():
            iface.messageBar().pushMessage(
                'QPANSOPY',
                'Layer CRS must be projected (metre-based). '
                'Reproject your ARP layer before running PBN Target.',
                level=Qgis.Critical,
            )
            return None

        selected = point_layer.selectedFeatures()
        feat = selected[0] if selected else next(point_layer.getFeatures(), None)

        if feat is None:
            iface.messageBar().pushMessage('QPANSOPY', 'No feature found in the point layer', level=Qgis.Critical)
            return None

        geom = feat.geometry()

        v_layer = QgsVectorLayer(f'Polygon?crs={layer_crs.authid()}', 'PBN_target', 'memory')
        pr = v_layer.dataProvider()
        pr.addAttributes([QgsField('target', QVariant.String)])
        v_layer.updateFields()

        features = []
        for radius_nm, label in [(15, '15 NM ARP'), (30, '30 NM ARP')]:
            buf = geom.buffer(radius_nm * _NM_TO_M, _SEGMENTS)
            f = QgsFeature()
            f.setGeometry(buf)
            f.setAttributes([label])
            features.append(f)

        pr.addFeatures(features)
        v_layer.updateExtents()
        QgsProject.instance().addMapLayers([v_layer])

        style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'pbn_target.qml')
        if os.path.exists(style_path):
            v_layer.loadNamedStyle(style_path)

        v_layer.triggerRepaint()

        v_layer.selectAll()
        iface.mapCanvas().zoomToSelected(v_layer)
        v_layer.removeSelection()

        iface.messageBar().pushMessage('QPANSOPY', 'PBN Target rings created (15 NM / 30 NM)', level=Qgis.Success)
        return {'layer': v_layer}

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        iface.messageBar().pushMessage('QPANSOPY', f'PBN Target error: {e}', level=Qgis.Critical)
        return None
