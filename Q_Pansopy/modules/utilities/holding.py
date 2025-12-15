from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsCircularString, QgsPoint, Qgis
)
from qgis.PyQt.QtGui import QColor
import math

# Reuse existing TAS/turn helpers from wind_spiral
from ..wind_spiral import tas_calculation


def _feet(value, unit):
    return value * 3.28084 if unit == 'm' else value


def run_holding_pattern(iface, routing_layer, params: dict):
    """
    Create a conventional holding (racetrack) geometry based on a selected routing segment.

    params keys:
      - IAS (kt), altitude, altitude_unit ('ft'|'m'), isa_var (°C), bank_angle (deg),
        leg_time_min (minutes), turn ('L'|'R')
    """
    try:
        sel = routing_layer.selectedFeatures()
        if len(sel) != 1:
            iface.messageBar().pushMessage("QPANSOPY", "Select exactly one routing segment", level=Qgis.Warning)
            return False

        feat = sel[0]
        geom = feat.geometry()
        if geom.isEmpty() or geom.type() != QgsWkbTypes.LineGeometry:
            iface.messageBar().pushMessage("QPANSOPY", "Invalid geometry: expected a line", level=Qgis.Warning)
            return False

        line = geom.constGet()  # QgsLineString or similar
        pts = geom.asPolyline()
        if not pts or len(pts) < 2:
            iface.messageBar().pushMessage("QPANSOPY", "Routing segment must be a polyline with 2+ vertices", level=Qgis.Warning)
            return False

        # Follow original script semantics
        start_pt = QgsPoint(pts[-1])  # fix at end of selected polyline
        end_pt = QgsPoint(pts[0])
        angle0 = start_pt.azimuth(end_pt) + 180
        azimuth = angle0  # original uses 'azimuth' variable

        # Inputs
        IAS = float(params.get('IAS', 195))
        altitude = _feet(float(params.get('altitude', 10000)), params.get('altitude_unit', 'ft'))
        isa_var = float(params.get('isa_var', 0.0))
        bank_angle = float(params.get('bank_angle', 25))
        leg_time_min = float(params.get('leg_time_min', 1.0))
        turn = params.get('turn', 'R').upper()
        # side = 90 LEFT, -90 RIGHT
        side = 90 if turn == 'L' else -90

        # Compute TAS, rate and radius via shared helper
        k, tas, rate_of_turn, radius_of_turn, wind = tas_calculation(IAS, altitude, isa_var, bank_angle)

        # Leg ground distance like original: v = tas/3600, t = time*60, L = v*t
        v_nmps = tas / 3600.0
        t_sec = leg_time_min * 60.0
        L_nm = v_nmps * t_sec

        # Build memory line layer (lines only, like original)
        crs = iface.mapCanvas().mapSettings().destinationCrs()
        v_layer = QgsVectorLayer(f"Linestring?crs={crs.authid()}", f"Holding {int(IAS)}kt/{int(altitude)}ft", "memory")
        pr = v_layer.dataProvider()

        # Outbound point from fix (original: angle = 90 - azimuth - 180)
        outbound_pt = _offset_point(start_pt, azimuth + 180, L_nm)  # helper uses course_deg; convert below
        # Our helper expects course_deg (bearing). To mimic angle=90-azimuth-180 we pass (azimuth+180)
        # because _offset_point internally does 90 - course.

        # Segment: outbound -> start
        f1 = QgsFeature()
        f1.setGeometry(QgsGeometry.fromPolyline([outbound_pt, start_pt]))
        pr.addFeatures([f1])

        # Build nominal points exactly as in original
        # From 'start': nominal0 then nominal1
        nominal0 = _offset_point(start_pt, azimuth + side, L_nm)  # angle: 90-azimuth-side
        nominal1 = _offset_point(nominal0, azimuth, L_nm/2)       # angle: 90-azimuth

        # From 'outbound': nominal2 then nominal3
        nominal2 = _offset_point(outbound_pt, azimuth + side, L_nm)      # angle: 90-azimuth-side
        nominal3 = _offset_point(nominal2, azimuth + 180, L_nm/2)        # angle: 90-azimuth+180

        # Arc 1: start -> nominal0 via nominal1
        c1 = QgsCircularString()
        c1.setPoints([start_pt, nominal1, nominal0])
        f2 = QgsFeature(); f2.setGeometry(QgsGeometry(c1)); pr.addFeatures([f2])

        # Straight: nominal0 -> nominal2
        f3 = QgsFeature(); f3.setGeometry(QgsGeometry.fromPolyline([nominal0, nominal2])); pr.addFeatures([f3])

        # Arc 2: nominal2 -> outbound via nominal3
        c2 = QgsCircularString()
        c2.setPoints([nominal2, nominal3, outbound_pt])
        f4 = QgsFeature(); f4.setGeometry(QgsGeometry(c2)); pr.addFeatures([f4])

        v_layer.updateExtents()
        QgsProject.instance().addMapLayer(v_layer)

        try:
            v_layer.renderer().symbol().setColor(QColor("magenta"))
            v_layer.renderer().symbol().setWidth(0.7)
            v_layer.triggerRepaint()
        except Exception:
            pass

        return {"layer": v_layer, "tas": tas, "rate_of_turn": rate_of_turn, "radius_nm": radius_of_turn}
    except Exception as e:
        iface.messageBar().pushMessage("QPANSOPY", f"Holding failed: {e}", level=Qgis.Critical)
        return False


def _offset_point(origin: QgsPoint, course_deg: float, dist_nm: float) -> QgsPoint:
    # Convert a course/bearing in degrees to screen X/Y offsets
    angle = math.radians(90 - course_deg)
    dx = dist_nm * 1852 * math.cos(angle)
    dy = dist_nm * 1852 * math.sin(angle)
    return QgsPoint(origin.x() + dx, origin.y() + dy)
