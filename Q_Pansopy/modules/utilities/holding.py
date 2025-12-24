from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsCircularString, QgsPoint, QgsField, Qgis
)
from qgis.PyQt.QtCore import QVariant
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
        altitude_ft = _feet(float(params.get('altitude', 10000)), params.get('altitude_unit', 'ft'))
        isa_var = float(params.get('isa_var', 0.0))
        bank_angle = float(params.get('bank_angle', 25))
        leg_time_min = float(params.get('leg_time_min', 1.0))
        turn = params.get('turn', 'R').upper()
        # side = 90 LEFT, -90 RIGHT
        side = 90 if turn == 'L' else -90

        # Compute TAS, rate and radius via shared helper
        k, tas, rate_of_turn, radius_of_turn, wind = tas_calculation(IAS, altitude_ft, isa_var, bank_angle)

        # Leg ground distance like original: v = tas/3600, t = time*60, L = v*t
        v_nmps = tas / 3600.0
        t_sec = leg_time_min * 60.0
        L_nm = v_nmps * t_sec

        summary = {
            "IAS_kt": IAS,
            "Altitude_ft": altitude_ft,
            "ISA_var_C": isa_var,
            "Bank_deg": bank_angle,
            "Leg_min": leg_time_min,
            "Turn": turn,
            "TAS_kt": tas,
            "Rate_deg_s": rate_of_turn,
            "Radius_nm": radius_of_turn,
            "Leg_nm": L_nm,
        }
        summary_text = (
            f"IAS {IAS:.1f} kt | Alt {altitude_ft:.0f} ft | ISA Δ {isa_var:.1f} °C | "
            f"Bank {bank_angle:.1f} ° | Leg {leg_time_min:.2f} min ({L_nm:.2f} NM) | "
            f"Turn {turn} | TAS {tas:.2f} kt | Rate {rate_of_turn:.3f} °/s | Radius {radius_of_turn:.3f} NM"
        )

        # Build memory line layer (lines only, like original)
        crs = iface.mapCanvas().mapSettings().destinationCrs()
        v_layer = QgsVectorLayer(f"Linestring?crs={crs.authid()}", f"Holding {int(IAS)}kt/{int(altitude_ft)}ft", "memory")
        pr = v_layer.dataProvider()
        fields = [
            QgsField('ias_kt', QVariant.Double),
            QgsField('alt_ft', QVariant.Double),
            QgsField('isa_var_c', QVariant.Double),
            QgsField('bank_deg', QVariant.Double),
            QgsField('leg_min', QVariant.Double),
            QgsField('turn', QVariant.String),
            QgsField('tas_kt', QVariant.Double),
            QgsField('rate_deg_s', QVariant.Double),
            QgsField('radius_nm', QVariant.Double),
            QgsField('leg_nm', QVariant.Double),
            QgsField('summary_txt', QVariant.String),
        ]
        pr.addAttributes(fields)
        v_layer.updateFields()

        attrs = [
            IAS,
            altitude_ft,
            isa_var,
            bank_angle,
            leg_time_min,
            turn,
            tas,
            rate_of_turn,
            radius_of_turn,
            L_nm,
            summary_text,
        ]

        # Angles as per original script (using math angles, 0° at +X, CCW)
        angle_outbound = 90 - azimuth - 180           # outbound from fix
        angle_side = 90 - azimuth - side              # side turn (side=±90)
        angle_mid_start = 90 - azimuth                # mid control for top arc
        angle_mid_outbound = 90 - azimuth + 180       # mid control for bottom arc

        # Outbound point from fix
        outbound_pt = _offset_by_angle(start_pt, angle_outbound, L_nm)

        # Segment: outbound -> start
        f1 = QgsFeature()
        f1.setGeometry(QgsGeometry.fromPolyline([outbound_pt, start_pt]))
        f1.setAttributes(attrs)
        pr.addFeatures([f1])

        # Build nominal points mirroring legacy script
        # From 'start': nominal0 (full L along side angle) then nominal1 (half side + half mid)
        nominal0 = _offset_by_angle(start_pt, angle_side, L_nm)
        mid_top = _offset_by_angle(start_pt, angle_side, L_nm / 2.0)
        nominal1 = _offset_by_angle(mid_top, angle_mid_start, L_nm / 2.0)

        # From 'outbound': nominal2 (full L along side angle) then nominal3 (half side + half mid outbound)
        nominal2 = _offset_by_angle(outbound_pt, angle_side, L_nm)
        mid_bottom = _offset_by_angle(outbound_pt, angle_side, L_nm / 2.0)
        nominal3 = _offset_by_angle(mid_bottom, angle_mid_outbound, L_nm / 2.0)

        # Arc 1: start -> nominal0 via nominal1
        c1 = QgsCircularString()
        c1.setPoints([start_pt, nominal1, nominal0])
        f2 = QgsFeature()
        f2.setGeometry(QgsGeometry(c1))
        f2.setAttributes(attrs)
        pr.addFeatures([f2])

        # Straight: nominal0 -> nominal2
        f3 = QgsFeature()
        f3.setGeometry(QgsGeometry.fromPolyline([nominal0, nominal2]))
        f3.setAttributes(attrs)
        pr.addFeatures([f3])

        # Arc 2: nominal2 -> outbound via nominal3
        c2 = QgsCircularString()
        c2.setPoints([nominal2, nominal3, outbound_pt])
        f4 = QgsFeature()
        f4.setGeometry(QgsGeometry(c2))
        f4.setAttributes(attrs)
        pr.addFeatures([f4])

        v_layer.updateExtents()
        QgsProject.instance().addMapLayer(v_layer)

        try:
            v_layer.renderer().symbol().setColor(QColor("magenta"))
            v_layer.renderer().symbol().setWidth(0.7)
            v_layer.triggerRepaint()
        except Exception:
            pass

        return {
            "layer": v_layer,
            "tas": tas,
            "rate_of_turn": rate_of_turn,
            "radius_nm": radius_of_turn,
            "summary": summary,
            "summary_text": summary_text,
        }
    except Exception as e:
        iface.messageBar().pushMessage("QPANSOPY", f"Holding failed: {e}", level=Qgis.Critical)
        return False


def _offset_point(origin: QgsPoint, course_deg: float, dist_nm: float) -> QgsPoint:
    # Convert a course/bearing in degrees to screen X/Y offsets
    angle = math.radians(90 - course_deg)
    dx = dist_nm * 1852 * math.cos(angle)
    dy = dist_nm * 1852 * math.sin(angle)
    return QgsPoint(origin.x() + dx, origin.y() + dy)


def _offset_by_angle(origin: QgsPoint, angle_deg: float, dist_nm: float) -> QgsPoint:
    """Offset using mathematical angle (0° = +X, CCW) matching legacy script."""
    angle = math.radians(angle_deg)
    dx = dist_nm * 1852 * math.cos(angle)
    dy = dist_nm * 1852 * math.sin(angle)
    return QgsPoint(origin.x() + dx, origin.y() + dy)
