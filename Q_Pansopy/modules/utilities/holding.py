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

        start_pt = QgsPoint(pts[-1])  # Use end of selection as holding fix
        end_pt = QgsPoint(pts[0])
        inbound_az = start_pt.azimuth(end_pt) + 180  # true course inbound to fix

        # Inputs
        IAS = float(params.get('IAS', 195))
        altitude = _feet(float(params.get('altitude', 10000)), params.get('altitude_unit', 'ft'))
        isa_var = float(params.get('isa_var', 0.0))
        bank_angle = float(params.get('bank_angle', 25))
        leg_time_min = float(params.get('leg_time_min', 1.0))
        turn = params.get('turn', 'R').upper()

        # Turn direction sign
        side = 90 if turn == 'L' else -90

        # Compute TAS, rate and radius via shared helper
        k, tas, rate_of_turn, radius_of_turn, wind = tas_calculation(IAS, altitude, isa_var, bank_angle)

        # Leg ground distance (very simplified, time*speed)
        v_nmps = tas / 3600.0  # kt -> NM per second
        L_nm = v_nmps * (leg_time_min * 60.0)

        # Build memory line layer
        crs = iface.mapCanvas().mapSettings().destinationCrs()
        v_layer = QgsVectorLayer(f"Linestring?crs={crs.authid()}", f"Holding {int(IAS)}kt/{int(altitude)}ft", "memory")
        pr = v_layer.dataProvider()

        # Outbound line from fix
        angle = math.radians(90 - inbound_az - 180)  # nominal outbound direction
        dx = L_nm * 1852 * math.cos(angle)
        dy = L_nm * 1852 * math.sin(angle)
        outbound_pt = QgsPoint(start_pt.x() + dx, start_pt.y() + dy)

        # First outbound segment
        f1 = QgsFeature()
        f1.setGeometry(QgsGeometry.fromPolyline([outbound_pt, start_pt]))
        pr.addFeatures([f1])

        # First 180° turn (top arc)
        c1 = QgsCircularString()
        # Create intermediate points roughly using side direction and half-leg offset
        turn1_mid = _offset_point(start_pt, inbound_az + side, L_nm/2)
        c1.setPoints([start_pt, turn1_mid, outbound_pt])
        f2 = QgsFeature(); f2.setGeometry(QgsGeometry(c1)); pr.addFeatures([f2])

        # Outbound to opposite point
        outbound2_pt = _offset_point(outbound_pt, inbound_az + side, L_nm)
        f3 = QgsFeature(); f3.setGeometry(QgsGeometry.fromPolyline([outbound_pt, outbound2_pt])); pr.addFeatures([f3])

        # Second 180° turn (bottom arc) back to initial outbound point
        c2 = QgsCircularString()
        turn2_mid = _offset_point(outbound2_pt, inbound_az, L_nm/2)
        c2.setPoints([outbound2_pt, turn2_mid, outbound_pt])
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
    angle = math.radians(90 - course_deg)
    dx = dist_nm * 1852 * math.cos(angle)
    dy = dist_nm * 1852 * math.sin(angle)
    return QgsPoint(origin.x() + dx, origin.y() + dy)
