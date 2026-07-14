from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsCircularString, QgsPoint, QgsPointXY, QgsField, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
import math

# Compat for QGIS 3/4: QgsWkbTypes.LineGeometry → Qgis.GeometryType.Line
try:
    _LINE_GEOMETRY = Qgis.GeometryType.Line  # QGIS 4+
except AttributeError:
    try:
        _LINE_GEOMETRY = QgsWkbTypes.LineGeometry  # QGIS 3  # type: ignore[attr-defined]
    except AttributeError:
        _LINE_GEOMETRY = 1  # type: ignore[assignment]  # test-stub sentinel

# Reuse existing TAS/turn helpers from wind_spiral
try:
    from ..wind_spiral import tas_calculation
except ImportError as e:
    raise ImportError(
        f"holding.py requires wind_spiral module in parent package: {e}"
    ) from e


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
        if geom.isEmpty() or geom.type() != _LINE_GEOMETRY:
            iface.messageBar().pushMessage("QPANSOPY", "Invalid geometry: expected a line", level=Qgis.Warning)
            return False

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
        # side = -90 LEFT, +90 RIGHT  (angle_side = 90 - azimuth - side)
        side = -90 if turn == 'L' else 90

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

        # Basic holding area — isolated so failures do not affect the nominal return value
        try:
            show_circles = bool(params.get('show_circles', True))
            side_sign = 1 if turn == 'R' else -1
            p = _wind_params(altitude_ft, leg_time_min, tas, rate_of_turn)
            raw_circles = _build_wind_circles(start_pt, azimuth, side_sign, radius_of_turn, p)
            valid_circles = [c for c in raw_circles if c and not c.isNull() and not c.isEmpty()]

            if show_circles and valid_circles:
                wc_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "HoldingWindCircles", "memory")
                wc_pr = wc_layer.dataProvider()
                for geom in valid_circles:
                    wc_f = QgsFeature()
                    wc_f.setGeometry(geom)
                    wc_pr.addFeatures([wc_f])
                wc_layer.updateExtents()
                QgsProject.instance().addMapLayer(wc_layer)
                try:
                    wc_layer.renderer().symbol().setColor(QColor(255, 0, 0, 128))
                    wc_layer.renderer().symbol().symbolLayer(0).setStrokeColor(QColor("red"))
                    wc_layer.triggerRepaint()
                except Exception:
                    pass

            if valid_circles:
                union = valid_circles[0]
                for c in valid_circles[1:]:
                    union = union.combine(c)
                hull = union.convexHull()
                if hull and not hull.isNull():
                    ba_layer = QgsVectorLayer(
                        f"Polygon?crs={crs.authid()}", "HoldingBasicArea", "memory")
                    ba_pr = ba_layer.dataProvider()
                    ba_f = QgsFeature()
                    ba_f.setGeometry(hull)
                    ba_pr.addFeatures([ba_f])
                    ba_layer.updateExtents()
                    QgsProject.instance().addMapLayer(ba_layer)
                    try:
                        ba_layer.renderer().symbol().setColor(QColor(255, 0, 0, 76))
                        ba_layer.renderer().symbol().symbolLayer(0).setStrokeColor(QColor("red"))
                        ba_layer.renderer().symbol().symbolLayer(0).setStrokeWidth(0.5)
                        ba_layer.triggerRepaint()
                    except Exception:
                        pass
                else:
                    iface.messageBar().pushMessage(
                        "QPANSOPY", "Basic area hull is null — verify CRS and coordinates",
                        level=Qgis.Warning)
        except Exception as e:
            iface.messageBar().pushMessage(
                "QPANSOPY", f"Basic area failed: {e}", level=Qgis.Warning)

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


def _proj(pt: QgsPoint, dist_nm: float, bearing_deg: float) -> QgsPoint:
    """Project point at compass bearing and NM distance (assumes map CRS in metres)."""
    angle = math.radians(90 - bearing_deg)
    d = dist_nm * 1852
    return QgsPoint(pt.x() + d * math.cos(angle), pt.y() + d * math.sin(angle))


def _circle(pt: QgsPoint, r_nm: float) -> QgsGeometry:
    return QgsGeometry.fromPointXY(QgsPointXY(pt.x(), pt.y())).buffer(r_nm * 1852, 36)


def _wind_params(altitude_ft: float, leg_time_min: float, tas: float, rate_of_turn: float) -> dict:
    """ICAO Doc 8168 wind-effect distances (NM) for the Basic Holding Area."""
    tas60 = tas / 3600
    w = (2 * altitude_ft / 1000) + 47
    wp = w / 3600
    e45 = (45 * wp) / rate_of_turn if rate_of_turn > 0 else 0.0
    t = leg_time_min * 60
    ab = 5 * tas60
    ac = 11 * tas60
    g1 = (t - 5) * tas60
    g2 = (t + 21) * tas60
    wb = 5 * wp
    wc = 11 * wp
    wd = wc + e45
    we = wc + 2 * e45
    wf = wc + 3 * e45
    wg = wc + 4 * e45
    wh = wb + 4 * e45
    w1 = (t + 6) * wp + 4 * e45
    w2 = w1 + 14 * wp
    wj = w2 + e45
    wk = w2 + 2 * e45
    wm = w2 + 3 * e45
    wn3 = w1 + 4 * e45
    wn4 = w2 + 4 * e45
    return dict(
        tas60=tas60, wp=wp, e45=e45, t=t,
        ab=ab, ac=ac, g1=g1, g2=g2,
        wb=wb, wc=wc, wd=wd, we=we, wf=wf, wg=wg, wh=wh,
        w1=w1, w2=w2, wj=wj, wk=wk, wm=wm, wn3=wn3, wn4=wn4,
    )


def _build_wind_circles(
    start_pt: QgsPoint, azimuth: float, side_sign: int, radius_nm: float, p: dict
) -> list:
    """Return list of QgsGeometry circles for all wind-tolerance points (basic holding area).

    side_sign: +1 for Right holding, -1 for Left holding.
    """
    back_az = azimuth + 180

    pta = start_pt
    ptb = _proj(pta, p['ab'], azimuth)
    ptc = _proj(pta, p['ac'], azimuth)

    cp1 = _proj(ptc, radius_nm, azimuth + 90 * side_sign)
    bsp1 = cp1.azimuth(ptc)
    ptd = _proj(cp1, radius_nm, bsp1 + 45 * side_sign)
    pte = _proj(cp1, radius_nm, bsp1 + 90 * side_sign)
    ptf = _proj(cp1, radius_nm, bsp1 + 135 * side_sign)
    ptg = _proj(cp1, radius_nm, bsp1 + 180)

    cp2 = _proj(ptb, radius_nm, azimuth + 90 * side_sign)
    pth = _proj(cp2, radius_nm, bsp1 + 180)

    pti1 = _proj(ptg, p['g1'], back_az - 5)
    pti3 = _proj(ptg, p['g1'], back_az + 5)
    pti2 = _proj(ptg, p['g2'], back_az - 5)
    pti4 = _proj(ptg, p['g2'], back_az + 5)

    cpi = _proj(pti2, radius_nm, back_az + 90 * side_sign)
    bspi = cpi.azimuth(pti2)
    ptj = _proj(cpi, radius_nm, bspi + 45 * side_sign)
    ptk = _proj(cpi, radius_nm, bspi + 90 * side_sign)

    cp3 = _proj(pti3, radius_nm, back_az + 90 * side_sign)
    bsp3 = cp3.azimuth(pti3)

    cp4 = _proj(pti4, radius_nm, back_az + 90 * side_sign)
    bsp4 = cp4.azimuth(pti4)
    ptl = _proj(cp4, radius_nm, bsp4 + 90 * side_sign)
    ptm = _proj(cp4, radius_nm, bsp4 + 135 * side_sign)

    ptn3 = _proj(cp3, radius_nm, bsp3 + 180)
    ptn4 = _proj(cp4, radius_nm, bsp4 + 180)

    circles = [
        _circle(ptb, p['wb']), _circle(ptc, p['wc']),
        _circle(ptd, p['wd']), _circle(pte, p['we']),
        _circle(ptf, p['wf']), _circle(ptg, p['wg']),
        _circle(pth, p['wh']),
        _circle(pti1, p['w1']), _circle(pti3, p['w1']),
        _circle(pti2, p['w2']), _circle(pti4, p['w2']),
        _circle(ptj, p['wj']), _circle(ptk, p['wk']),
        _circle(ptl, p['wk']), _circle(ptm, p['wm']),
        _circle(ptn3, p['wn3']), _circle(ptn4, p['wn4']),
    ]

    # Arc-interpolated circles: grow radius with e45 rate
    e45_per_deg = p['e45'] / 45

    for i in range(10, 180, 10):
        aux = _proj(cp1, radius_nm, bsp1 + i * side_sign)
        circles.append(_circle(aux, p['wc'] + i * e45_per_deg))

    for i in range(10, 90, 10):
        aux = _proj(cpi, radius_nm, bspi + i * side_sign)
        circles.append(_circle(aux, p['w2'] + i * e45_per_deg))

    for i in range(90, 180, 10):
        aux = _proj(cp4, radius_nm, bsp4 + i * side_sign)
        circles.append(_circle(aux, p['w2'] + i * e45_per_deg))

    return circles


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
