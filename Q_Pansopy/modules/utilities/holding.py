from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsCircularString, QgsPoint, QgsPointXY, QgsField, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
import json
import html
import math

from ...parameters_inspector_dialog import (
    TableContent, register_parameters_action,
)

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


def format_holding_table_parameters(summary):
    """Return the rows displayed by both Holding table entry points."""
    return {
        'IAS_kt': f"{summary.get('IAS_kt', 0):.1f}",
        'Altitude_ft': f"{summary.get('Altitude_ft', 0):.0f}",
        'ISA_var_C': f"{summary.get('ISA_var_C', 0):.1f}",
        'Bank_deg': f"{summary.get('Bank_deg', 0):.1f}",
        'Leg_min': f"{summary.get('Leg_min', 0):.2f}",
        'Leg_nm': f"{summary.get('Leg_nm', 0):.2f}",
        'Turn': summary.get('Turn', ''),
        'TAS_kt': f"{summary.get('TAS_kt', 0):.2f}",
        'Rate_deg_s': f"{summary.get('Rate_deg_s', 0):.3f}",
        'Radius_nm': f"{summary.get('Radius_nm', 0):.3f}",
    }


def build_holding_feature_parameters(summary):
    """Return a numeric, versioned snapshot for the Holding area action."""
    return {
        'calculation_type': 'Holding Pattern',
        'schema_version': 2,
        'summary': dict(summary),
    }


def _holding_complete_rows(summary):
    """Return Doc 8168 table rows from the actual Holding calculation values."""
    tas_kt = float(summary['TAS_kt'])
    rate = float(summary['Rate_deg_s'])
    radius_nm = float(summary['Radius_nm'])
    altitude_ft = float(summary['Altitude_ft'])
    leg_minutes = float(summary['Leg_min'])
    bank = float(summary['Bank_deg'])
    wind_kt = (2 * altitude_ft / 1000.0) + 47.0
    v_nmps = tas_kt / 3600.0
    wind_nmps = wind_kt / 3600.0
    params = _wind_params(altitude_ft, leg_minutes, tas_kt, rate)
    t = params['t']
    e45 = params['e45']
    xe_nm = (
        2 * radius_nm + (t + 15) * v_nmps
        + (t + 26 + 195 / rate) * wind_nmps
    )
    ye_nm = (
        11 * v_nmps * math.cos(math.radians(20))
        + radius_nm * (1 + math.sin(math.radians(20)))
        + (t + 15) * v_nmps * math.tan(math.radians(5))
        + (t + 26 + 125 / rate) * wind_nmps
    )

    si_speed = tas_kt * 1.852  # km/h
    si_v = si_speed / 3600.0  # km/s
    si_w = wind_kt * 1.852  # km/h, converted from the geometry's wind value
    si_wp = si_w / 3600.0

    def si_dist(distance_nm):
        return distance_nm * 1.852

    h_ft = altitude_ft / 1000.0
    h_m = altitude_ft * 0.3048 / 1000.0
    ias_kt = float(summary['IAS_kt'])
    k = float(summary.get('K_factor', tas_kt / ias_kt))
    angle_rate = (
        'R = (3431 tan {0:.1f}°) / (π V)'.format(bank)
        if abs(bank - 25.0) > 1e-9 else 'R = 509.26 / V'
    )

    definitions = [
        ('1', 'K', 'Conversion factor at entered altitude and ISA deviation',
         'Conversion factor at entered altitude and ISA deviation', k, k, (3, 4)),
        ('2', 'V', 'V = K × IAS', 'V = K × IAS', si_speed, tas_kt, 2),
        ('3', 'v', 'v = V ÷ 3 600', 'v = V ÷ 3 600', si_v, v_nmps, (4, 5)),
        ('4', 'R',
         'R = (9.81 tan φ ÷ V) × 180/π, V in m/s (φ = {0:.1f}°)'.format(bank),
         angle_rate, rate, rate, 2),
        ('5', 'r', 'r = v × 57.296 ÷ R', 'r = V ÷ (62.83 R)',
         si_dist(radius_nm), radius_nm, 2),
        ('6', 'h', 'h in thousands of metres', 'h in thousands of feet',
         h_m, h_ft, 2),
        ('7', 'w', 'w = (2h_ft + 47) × 1.852 km/h', 'w = 2h + 47',
         si_w, wind_kt, (1, 0)),
        ('8', 'w′', 'w′ = w ÷ 3 600', 'w′ = w ÷ 3 600',
         si_wp, wind_nmps, (5, 4)),
        ('9', 'E₄₅', 'E₄₅ = 45w′ ÷ R', 'E₄₅ = 45w′ ÷ R',
         si_dist(e45), e45, 3),
        ('10', 't', 't = 60T', 't = 60T', t, t, 0),
        ('11', 'L', 'L = vt', 'L = vt', si_dist(v_nmps * t), v_nmps * t, 2),
        ('12', 'ab', 'ab = 5v', 'ab = 5v', si_dist(params['ab']), params['ab'], 2),
        ('13', 'ac', 'ac = 11v', 'ac = 11v', si_dist(params['ac']), params['ac'], 2),
        ('14', 'g₁ = g₃', 'g₁ = g₃ = (t − 5)v', 'g₁ = g₃ = (t − 5)v',
         si_dist(params['g1']), params['g1'], 2),
        ('15', 'g₂ = g₄', 'g₂ = g₄ = (t + 21)v', 'g₂ = g₄ = (t + 21)v',
         si_dist(params['g2']), params['g2'], 2),
        ('16', 'Wb', 'Wb = 5w′', 'Wb = 5w′', si_dist(params['wb']), params['wb'], 2),
        ('17', 'Wc', 'Wc = 11w′', 'Wc = 11w′', si_dist(params['wc']), params['wc'], 2),
        ('18', 'Wd', 'Wd = Wc + E₄₅', 'Wd = Wc + E₄₅', si_dist(params['wd']), params['wd'], 2),
        ('19', 'We', 'We = Wc + 2E₄₅', 'We = Wc + 2E₄₅', si_dist(params['we']), params['we'], 2),
        ('20', 'Wf', 'Wf = Wc + 3E₄₅', 'Wf = Wc + 3E₄₅', si_dist(params['wf']), params['wf'], 2),
        ('21', 'Wg', 'Wg = Wc + 4E₄₅', 'Wg = Wc + 4E₄₅', si_dist(params['wg']), params['wg'], 2),
        ('22', 'Wh', 'Wh = Wb + 4E₄₅', 'Wh = Wb + 4E₄₅', si_dist(params['wh']), params['wh'], 2),
        ('23', 'Wo', 'Wo = Wb + 5E₄₅', 'Wo = Wb + 5E₄₅',
         si_dist(params['wb'] + 5 * e45), params['wb'] + 5 * e45, 2),
        ('24', 'Wp', 'Wp = Wb + 6E₄₅', 'Wp = Wb + 6E₄₅',
         si_dist(params['wb'] + 6 * e45), params['wb'] + 6 * e45, 2),
        ('25', 'W₁ = W₃', 'W₁ = W₃ = (t + 6)w′ + 4E₄₅',
         'W₁ = W₃ = (t + 6)w′ + 4E₄₅', si_dist(params['w1']), params['w1'], 2),
        ('26', 'W₁₂ = W₁₄', 'W₁₂ = W₁₄ = W₁ + 14w′',
         'W₁₂ = W₁₄ = W₁ + 14w′', si_dist(params['w2']), params['w2'], 2),
        ('27', 'Wj', 'Wj = W₁₂ + E₄₅', 'Wj = W₁₂ + E₄₅', si_dist(params['wj']), params['wj'], 2),
        ('28', 'Wk = Wl', 'Wk = Wl = W₁₂ + 2E₄₅',
         'Wk = Wl = W₁₂ + 2E₄₅', si_dist(params['wk']), params['wk'], 2),
        ('29', 'Wm', 'Wm = W₁₂ + 3E₄₅', 'Wm = W₁₂ + 3E₄₅', si_dist(params['wm']), params['wm'], 2),
        ('30', 'Wn₃', 'Wn₃ = W₁ + 4E₄₅', 'Wn₃ = W₁ + 4E₄₅', si_dist(params['wn3']), params['wn3'], 2),
        ('31', 'Wn₄', 'Wn₄ = W₁₂ + 4E₄₅', 'Wn₄ = W₁₂ + 4E₄₅', si_dist(params['wn4']), params['wn4'], 2),
        ('32', 'XE', 'XE = 2r + (t + 15)v + (t + 26 + 195 ÷ R)w′',
         'XE = 2r + (t + 15)v + (t + 26 + 195 ÷ R)w′',
         si_dist(xe_nm), xe_nm, 2),
        ('33', 'YE', 'YE = 11v cos 20° + r(1 + sin 20°) + (t + 15)v tan 5° + (t + 26 + 125 ÷ R)w′',
         'YE = 11v cos 20° + r(1 + sin 20°) + (t + 15)v tan 5° + (t + 26 + 125 ÷ R)w′',
         si_dist(ye_nm), ye_nm, 2),
    ]
    return definitions, (ias_kt * 1.852, tas_kt, altitude_ft * 0.3048,
                         altitude_ft, leg_minutes, summary['ISA_var_C'], bank)


def format_holding_complete_table(summary):
    """Return the complete ICAO table as Word HTML and tab-separated text."""
    definitions, _input_data = _holding_complete_rows(summary)
    html_rows = []
    text_rows = [
        'Line\tParameter\tSI Formula\tSI Value\tNon-SI Formula\tNon-SI Value'
    ]
    cell_style = (
        'border:1px solid #333;color:#111;background:#fff;padding:5px 7px;'
        'font-family:Calibri,Arial,sans-serif;font-size:10pt;vertical-align:middle;'
        'white-space:normal'
    )
    for line, label, si_formula, non_si_formula, si_value, non_si_value, digits in definitions:
        si_digits, non_si_digits = digits if isinstance(digits, tuple) else (digits, digits)
        si_units = {'2': 'km/h', '3': 'km/s', '4': '°/s', '5': 'km',
                    '7': 'km/h', '8': 'km/s', '9': 'km', '10': 's'}
        non_si_units = {'2': 'kt', '3': 'NM/s', '4': '°/s', '5': 'NM',
                        '7': 'kt', '8': 'NM/s', '9': 'NM', '10': 's'}
        si_unit = si_units.get(line, 'km' if line not in ('1', '4', '6', '10') else '')
        non_si_unit = non_si_units.get(
            line, 'NM' if line not in ('1', '4', '6', '10') else '')
        si_value_text = '{0:.{1}f}{2}'.format(si_value, si_digits, ' ' + si_unit if si_unit else '')
        non_si_value_text = '{0:.{1}f}{2}'.format(non_si_value, non_si_digits, ' ' + non_si_unit if non_si_unit else '')
        html_rows.append(
            '<tr><td style="{6}">{0}</td><td style="{6}">{1}</td>'
            '<td style="{6}">{2}</td><td style="{7}">{3}</td>'
            '<td style="{6}">{4}</td><td style="{7}">{5}</td></tr>'.format(
                html.escape(line), html.escape(label), html.escape(si_formula),
                html.escape(si_value_text), html.escape(non_si_formula),
                html.escape(non_si_value_text), cell_style,
                cell_style + ';text-align:center;white-space:nowrap'))
        text_rows.append('\t'.join((line, label, si_formula, si_value_text,
                                    non_si_formula, non_si_value_text)))

    _si_speed, _tas_kt, altitude_m, altitude_ft, leg_minutes, isa_var, bank = _input_data
    isa_text = 'ISA {0:+.1f} °C'.format(float(isa_var))
    data_th = (
        'border:1px solid #333;background:#000;color:#fff;padding:6px;'
        'text-align:center;font-family:Calibri,Arial,sans-serif;font-size:10pt'
    )
    data_td = (
        'border:1px solid #333;color:#111;background:#fff;padding:5px 7px;'
        'font-family:Calibri,Arial,sans-serif;font-size:10pt'
    )
    data_html = (
        '<table class="holding-data" style="width:82%;min-width:700px;margin:0 auto 16px;'
        'border-collapse:collapse;font-family:Calibri,Arial,sans-serif;font-size:10pt">'
        '<tr><th colspan="3" style="{0}">DATA</th></tr>'
        '<tr><th style="{0}">Input</th><th style="{0}">SI Units</th>'
        '<th style="{0}">Non-SI Units</th></tr>'
        '<tr><td style="{1}">IAS</td><td style="{1}">{2:.2f} km/h</td>'
        '<td style="{1}">{3:.2f} kt</td></tr>'
        '<tr><td style="{1}">Altitude</td><td style="{1}">{4:.0f} m</td>'
        '<td style="{1}">{5:.0f} ft</td></tr>'
        '<tr><td style="{1}">T</td><td style="{1}">{6:.2f} min</td>'
        '<td style="{1}">{6:.2f} min</td></tr>'
        '<tr><td style="{1}">Temperature</td><td style="{1}">{7}</td>'
        '<td style="{1}">{7}</td></tr>'
        '<tr><td style="{1}">Bank angle</td><td style="{1}">{8:.1f}°</td>'
        '<td style="{1}">{8:.1f}°</td></tr></table>'.format(
            data_th, data_td, _si_speed, float(summary['IAS_kt']),
            altitude_m, altitude_ft, leg_minutes, html.escape(isa_text), bank)
    )
    plain_data = [
        'DATA', 'Input\tSI Units\tNon-SI Units',
        'IAS\t{0:.2f} km/h\t{1:.2f} kt'.format(_si_speed, float(summary['IAS_kt'])),
        'Altitude\t{0:.0f} m\t{1:.0f} ft'.format(altitude_m, altitude_ft),
        'T\t{0:.2f} min\t{0:.2f} min'.format(leg_minutes),
        'Temperature\t{0}\t{0}'.format(isa_text),
        'Bank angle\t{0:.1f}°\t{0:.1f}°'.format(bank),
        '',
        'Line\tParameter\tSI Formula\tSI Value\tNon-SI Formula\tNon-SI Value',
    ]
    header_style = (
        'border:1px solid #333;background:#000;color:#fff;padding:7px 5px;'
        'text-align:center;font-family:Calibri,Arial,sans-serif;font-size:10pt;'
        'font-weight:bold;text-transform:none;letter-spacing:normal;width:auto'
    )
    table_html = (
        '<div class="holding-complete-table" style="overflow-x:auto;min-width:1450px">{0}'
        '<table class="holding-calculations" border="1" cellpadding="0" '
        'cellspacing="0" style="min-width:1450px;width:1450px;table-layout:fixed;'
        'border-collapse:collapse;font-family:Calibri,Arial,sans-serif;font-size:10pt">'
        '<colgroup><col style="width:5%"><col style="width:7%">'
        '<col style="width:30%"><col style="width:8%">'
        '<col style="width:42%"><col style="width:8%"></colgroup>'
        '<thead><tr><th rowspan="2" style="{2}">Line</th>'
        '<th rowspan="2" style="{2}">Parameter</th>'
        '<th colspan="2" style="{2}">Calculations using SI units</th>'
        '<th colspan="2" style="{2}">Calculations using non-SI units</th></tr>'
        '<tr><th style="{2}">Formula</th><th style="{2}">Value</th>'
        '<th style="{2}">Formula</th><th style="{2}">Value</th></tr></thead>'
        '<tbody>{1}</tbody></table></div>'.format(
            data_html, ''.join(html_rows), header_style)
    )
    return table_html, '\n'.join(plain_data + text_rows[1:])


def _holding_short_content(summary):
    params = format_holding_table_parameters(summary)
    header = '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">'
    rows = ['<tr><th>Parameter</th><th>Value</th></tr>']
    rows.extend(
        '<tr><td><b>{0}</b></td><td>{1}</td></tr>'.format(
            html.escape(str(key)), html.escape(str(value)))
        for key, value in params.items()
    )
    plain = ['Parameter\tValue'] + [
        '{0}\t{1}'.format(key, value) for key, value in params.items()
    ]
    return TableContent(header + ''.join(rows) + '</table>', '\n'.join(plain))


def build_holding_table_views(summary):
    """Return complete and short views in the default display order."""
    complete_html, complete_text = format_holding_complete_table(summary)
    return (
        ('Complete', TableContent(complete_html, complete_text)),
        ('Short', _holding_short_content(summary)),
    )


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
            "K_factor": k,
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
        except Exception:  # nosec B110 - cosmetic styling; must not abort a successful calculation
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
                except Exception:  # nosec B110 - cosmetic styling; must not abort a successful calculation
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
                    ba_pr.addAttributes([QgsField('parameters', QVariant.String)])
                    ba_layer.updateFields()
                    ba_f = QgsFeature()
                    ba_f.setGeometry(hull)
                    ba_f.setAttributes([json.dumps(build_holding_feature_parameters(summary))])
                    ba_pr.addFeatures([ba_f])
                    ba_layer.updateExtents()
                    QgsProject.instance().addMapLayer(ba_layer)
                    register_parameters_action(ba_layer)
                    try:
                        ba_layer.renderer().symbol().setColor(QColor(255, 0, 0, 76))
                        ba_layer.renderer().symbol().symbolLayer(0).setStrokeColor(QColor("red"))
                        ba_layer.renderer().symbol().symbolLayer(0).setStrokeWidth(0.5)
                        ba_layer.triggerRepaint()
                    except Exception:  # nosec B110 - cosmetic styling; must not abort a successful calculation
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
