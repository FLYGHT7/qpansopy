from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsPoint, QgsLineString, QgsPolygon,
    QgsField
)
from qgis.core import Qgis
from qgis.PyQt.QtCore import QVariant
import math
import os


def run_rnav_sid_missed(iface, routing_layer, rnav_mode: str, op_mode: str,
                        export_kml: bool = False, output_dir: str | None = None):
    """Generate RNAV1/2 SID (o Missed) usando la geometría legacy <15NM."""
    try:
        selection = routing_layer.selectedFeatures()
        if not selection:
            iface.messageBar().pushMessage("QPANSOPY", "No features selected", level=Qgis.Critical)
            return False

        geom = selection[0].geometry()
        if geom.isEmpty():
            iface.messageBar().pushMessage("QPANSOPY", "Invalid geometry: empty feature", level=Qgis.Warning)
            return False

        line = geom.asPolyline()
        if not line or len(line) < 2:
            iface.messageBar().pushMessage("QPANSOPY", "Invalid geometry: expected a line with 2+ vertices", level=Qgis.Warning)
            return False

        # Orientación legacy: start = último vértice, end = primero
        start_point = QgsPoint(line[-1])
        end_point = QgsPoint(line[0])
        azimuth = start_point.azimuth(end_point) + 180
        length0 = geom.length()

        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        pts = {}
        a = 0

        # Proyección FAF
        bearing = azimuth
        angle = 90 - bearing
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        dist_x = length0 * math.cos(angle)
        dist_y = length0 * math.sin(angle)
        pts[f"m{a}"] = QgsPoint(end_point.x() + dist_x, end_point.y() + dist_y)
        a += 1
        pts[f"m{a}"] = QgsPoint(end_point.x(), end_point.y())
        a += 1

        # Puntos inferiores desde start (±1, ±2 NM)
        for i in (1.0, 2.0, -1.0, -2.0):
            TNA_dist = i * 1852
            bearing = azimuth + 90
            angle = 90 - bearing
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = TNA_dist * math.cos(angle)
            dist_y = TNA_dist * math.sin(angle)
            pts[f"m{a}"] = QgsPoint(start_point.x() + dist_x, start_point.y() + dist_y)
            a += 1

        # Puntos superiores desde end (±1, ±2 NM)
        for i in (1.0, 2.0, -1.0, -2.0):
            TNA_dist = i * 1852
            bearing = azimuth + 90
            angle = 90 - bearing
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = TNA_dist * math.cos(angle)
            dist_y = TNA_dist * math.sin(angle)
            pts[f"m{a}"] = QgsPoint(end_point.x() + dist_x, end_point.y() + dist_y)
            a += 1

        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "PBN RNAV 1/2", "memory")
        myField = QgsField('Symbol', QVariant.String)
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()

        # Área primaria
        primary = [pts["m2"], pts["m0"], pts["m4"], pts["m8"], pts["m1"], pts["m6"]]
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(primary), rings=[]))
        seg.setAttributes(['Primary Area'])
        v_layer.dataProvider().addFeatures([seg])

        # Secundaria izquierda
        secondary_left = [pts["m3"], pts["m2"], pts["m6"], pts["m7"]]
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(secondary_left), rings=[]))
        seg.setAttributes(['Secondary Area'])
        v_layer.dataProvider().addFeatures([seg])

        # Secundaria derecha
        secondary_right = [pts["m4"], pts["m5"], pts["m9"], pts["m8"]]
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(secondary_right), rings=[]))
        seg.setAttributes(['Secondary Area'])
        v_layer.dataProvider().addFeatures([seg])

        v_layer.updateExtents()
        QgsProject.instance().addMapLayers([v_layer])

        # Estilo legacy
        style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'primary_secondary_areas.qml')
        if os.path.exists(style_path):
            v_layer.loadNamedStyle(style_path)

        # Zoom legacy
        v_layer.selectAll()
        canvas = iface.mapCanvas()
        canvas.zoomToSelected(v_layer)
        v_layer.removeSelection()

        iface.messageBar().pushMessage("QPANSOPY:", f"Finished {rnav_mode} {op_mode} (<30NM)", level=Qgis.Success)
        return {'layer': v_layer}
    except Exception as e:
        iface.messageBar().pushMessage("QPANSOPY", f"RNAV {op_mode} failed: {e}", level=Qgis.Critical)
        return False
