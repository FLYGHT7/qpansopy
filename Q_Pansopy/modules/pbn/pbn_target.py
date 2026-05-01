from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsField,
    QgsGeometry,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, Qgis
)
from qgis.PyQt.QtCore import QVariant
import os

_NM_TO_M = 1852.0
_SEGMENTS = 360


def _utm_crs_for_point(lon_deg, lat_deg):
    """Return a UTM CRS centred on the given WGS84 coordinates."""
    zone = int((lon_deg + 180) / 6) + 1
    south = '+south' if lat_deg < 0 else ''
    return QgsCoordinateReferenceSystem(
        f'PROJ:+proj=utm +zone={zone} {south} +datum=WGS84 +units=m +no_defs'
    )


def run_pbn_target(iface, point_layer):
    """Create 15 NM and 30 NM ARP buffer rings from a point layer."""
    try:
        if point_layer is None:
            iface.messageBar().pushMessage('QPANSOPY', 'No point layer provided', level=Qgis.Critical)
            return None

        selected = point_layer.selectedFeatures()
        feat = selected[0] if selected else next(point_layer.getFeatures(), None)

        if feat is None:
            iface.messageBar().pushMessage('QPANSOPY', 'No feature found in the point layer', level=Qgis.Critical)
            return None

        project_crs = iface.mapCanvas().mapSettings().destinationCrs()
        src_crs = point_layer.crs()
        wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')

        geom_src = feat.geometry()
        to_wgs84 = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
        geom_wgs84 = QgsGeometry(geom_src)
        geom_wgs84.transform(to_wgs84)
        pt_wgs84 = geom_wgs84.asPoint()

        utm_crs = _utm_crs_for_point(pt_wgs84.x(), pt_wgs84.y())

        to_utm = QgsCoordinateTransform(src_crs, utm_crs, QgsProject.instance())
        geom_utm = QgsGeometry(geom_src)
        geom_utm.transform(to_utm)

        from_utm = QgsCoordinateTransform(utm_crs, project_crs, QgsProject.instance())

        v_layer = QgsVectorLayer(f'Polygon?crs={project_crs.authid()}', 'PBN_target', 'memory')
        pr = v_layer.dataProvider()
        pr.addAttributes([QgsField('target', QVariant.String)])
        v_layer.updateFields()

        features = []
        for radius_nm, label in [(15, '15 NM ARP'), (30, '30 NM ARP')]:
            buf_utm = geom_utm.buffer(radius_nm * _NM_TO_M, _SEGMENTS)
            buf_utm.transform(from_utm)
            f = QgsFeature()
            f.setGeometry(buf_utm)
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
