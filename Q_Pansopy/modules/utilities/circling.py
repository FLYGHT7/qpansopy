# -*- coding: utf-8 -*-
"""
Visual Manoeuvring (Circling) Protection Area.

Ports the per-category circling radius calculation from the PANS-OPS web
calculator (``html/calculators/circling_parameters.html``) and draws the
protection area in QGIS: each selected runway threshold point is buffered by
the circling radius, the buffers are unioned and the convex hull is taken,
producing a stadium/racetrack polygon per aircraft category (CAT A-E).

Reference: ICAO PANS-OPS Vol I, Part I, Section 4 (Visual Manoeuvring).
"""
import datetime
import html
import json
import math
import os
from typing import Mapping, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsField,
    QgsGeometry, QgsPointXY, QgsProject, QgsVectorFileWriter, QgsVectorLayer,
    Qgis,
)
from qgis.PyQt.QtCore import QVariant

from ...parameters_inspector_dialog import register_parameters_action
from ...utils import fix_kml_altitude_mode

# Straight segment constant S per category (NM) -- PANS-OPS tabulated value.
S_CONST = {"A": 0.3, "B": 0.4, "C": 0.5, "D": 0.6, "E": 0.7}

# ICAO default circling IAS per category (kt), at maximum circling speed.
IAS_DEFAULTS = {"A": 100, "B": 135, "C": 180, "D": 205, "E": 240}

CATEGORIES = ("A", "B", "C", "D", "E")

FT2M = 0.3048
KT2MS = 0.514444
NM2M = 1852.0
MAX_RATE_OF_TURN = 3.0  # deg/s cap

# Per-category fill colours (R, G, B) for the categorized renderer.
_CAT_COLORS = {
    "A": (31, 120, 180),
    "B": (51, 160, 44),
    "C": (255, 127, 0),
    "D": (227, 26, 28),
    "E": (106, 61, 154),
}

# Row schema copied from the web calculator's complete results table. A source
# prefixed with ``params.`` comes from the input snapshot; all other sources
# come from the per-category calculation summary.
_COMPLETE_TABLE_ROWS = (
    ("Bank Angle [°]", "params.bank_deg", 1),
    ("ΔT ISA [°C]", "params.delta_isa", 1),
    ("IAS [KT]", "ias_kt", 0),
    ("Protected Height [ft AGL]", "params.prot_height_ft", 0),
    ("Altitude (h1) [ft]", "h1_ft", 4),
    ("K Factor", "k_factor", 4),
    ("TAS + 25KT", "tas_plus_wind_kt", 4),
    ("Rate of Turn (R) calculated [°/s]", "rate_turn_calc", 4),
    ("Rate of Turn (R) used [°/s]", "rate_turn_used", 4),
    ("Nominal Radius (r) [NM]", "nominal_radius_nm", 4),
    ("Straight Segment (S) [NM]", "straight_segment_nm", 1),
    ("Circling Radius = 2r + S [NM]", "circling_radius_nm", 4),
)


def _complete_table_value(
        category_result: Mapping[str, float], params: Mapping[str, object],
        source: str, decimals: int) -> str:
    """Return one formatted value for the complete Circling table."""
    try:
        if source.startswith("params."):
            value = params[source.split(".", 1)[1]]
        else:
            value = category_result[source]
        return "{0:.{1}f}".format(float(value), decimals)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Cannot format Circling table value for {0}".format(source)
        ) from exc


def format_circling_complete_table(
        summary: Mapping[str, Mapping[str, float]],
        params: Mapping[str, object]) -> Tuple[str, str]:
    """Build the web-style CAT A-E results table for Word and plain text.

    All five category columns are retained. A category absent from *summary*
    was disabled for the calculation and is represented by an em dash.
    """
    headers = ("Parameters",) + tuple(
        "CAT {0}".format(cat) for cat in CATEGORIES)
    text_rows = ["\t".join(headers)]
    rendered_rows = []

    for label, source, decimals in _COMPLETE_TABLE_ROWS:
        values = []
        for cat in CATEGORIES:
            result = summary.get(cat)
            values.append(
                _complete_table_value(result, params, source, decimals)
                if result is not None else "—"
            )
        text_rows.append("\t".join((label,) + tuple(values)))
        rendered_rows.append((label, values))

    header_style = (
        "background:#0c2240;color:#ffffff;padding:8px;"
        "text-align:left;font-weight:bold"
    )
    cell_style = "padding:8px;text-align:left"
    header_html = "".join(
        '<th style="{0}">{1}</th>'.format(header_style, html.escape(value))
        for value in headers
    )
    body_html = []
    for label, values in rendered_rows:
        cells = [
            '<td style="{0}"><b>{1}</b></td>'.format(
                cell_style, html.escape(label))
        ]
        cells.extend(
            '<td style="{0}">{1}</td>'.format(
                cell_style, html.escape(value))
            for value in values
        )
        body_html.append("<tr>{0}</tr>".format("".join(cells)))

    table_html = (
        '<table border="1" style="border-collapse:collapse;width:100%;'
        'font-family:Calibri,Arial,sans-serif;font-size:11pt">'
        '<tr>{0}</tr>{1}</table>'.format(header_html, "".join(body_html))
    )
    return table_html, "\n".join(text_rows)


def calc_density_ratio(h_ft, delta_isa):
    """Return the ISA density ratio (sigma) at pressure altitude *h_ft* (ft AMSL)
    with a temperature deviation of *delta_isa* degrees Celsius."""
    t_isa = 288.15 - 0.0019812 * h_ft
    theta = (t_isa + delta_isa) / 288.15
    delta = (t_isa / 288.15) ** 5.2561
    return delta / theta


def calc_circling_category(ias_kt, prot_height_ft, elev_ft, bank_deg, delta_isa,
                           s_const):
    """Compute the circling parameters for a single aircraft category.

    :param ias_kt: Indicated airspeed (kt).
    :param prot_height_ft: Protected height above the aerodrome (ft AGL).
    :param elev_ft: Aerodrome elevation (ft AMSL).
    :param bank_deg: Average achieved bank angle (deg).
    :param delta_isa: Temperature deviation from ISA (deg C).
    :param s_const: Straight segment constant S for this category (NM).
    :return: dict with h1_ft, k_factor, tas_kt, tas_plus_wind_kt,
        rate_turn_calc, rate_turn_used, nominal_radius_nm,
        straight_segment_nm and circling_radius_nm.
    """
    h1_ft = elev_ft + prot_height_ft
    sigma = calc_density_ratio(h1_ft, delta_isa)
    k_factor = 1.0 / math.sqrt(sigma)
    tas_kt = ias_kt * k_factor
    tas_plus_wind_kt = tas_kt + 25.0

    tas_plus_wind_ms = tas_plus_wind_kt * KT2MS
    rate_turn_calc = (
        9.81 * math.tan(math.radians(bank_deg)) / tas_plus_wind_ms
    ) * (180.0 / math.pi)
    rate_turn_used = min(MAX_RATE_OF_TURN, rate_turn_calc)

    nominal_radius_nm = tas_plus_wind_kt / (20.0 * math.pi * rate_turn_used)
    circling_radius_nm = 2.0 * nominal_radius_nm + s_const

    return {
        "ias_kt": ias_kt,
        "h1_ft": h1_ft,
        "k_factor": k_factor,
        "tas_kt": tas_kt,
        "tas_plus_wind_kt": tas_plus_wind_kt,
        "rate_turn_calc": rate_turn_calc,
        "rate_turn_used": rate_turn_used,
        "nominal_radius_nm": nominal_radius_nm,
        "straight_segment_nm": s_const,
        "circling_radius_nm": circling_radius_nm,
    }


def build_circling_area(points_map_crs, radius_m):
    """Return the circling protection polygon: convex hull of the *radius_m*
    buffers around every point in *points_map_crs* (a list of QgsPointXY in the
    map CRS, assumed projected in metres)."""
    circles = [
        QgsGeometry.fromPointXY(pt).buffer(radius_m, 72)
        for pt in points_map_crs
    ]
    union = circles[0]
    for circle in circles[1:]:
        union = union.combine(circle)
    return union.convexHull()


def _elev_to_ft(value, unit):
    return value / FT2M if unit == "m" else value


def _threshold_points_map_crs(features, layer, map_crs, project):
    """Transform the selected threshold point features to the map CRS."""
    transform = QgsCoordinateTransform(layer.crs(), map_crs, project)
    points = []
    for feat in features:
        geom = feat.geometry()
        geom.transform(transform)
        points.append(QgsPointXY(geom.asPoint()))
    return points


def _apply_categorized_style(v_layer):
    """Style the layer with one semi-transparent fill colour per category."""
    from qgis.core import (
        QgsCategorizedSymbolRenderer, QgsFillSymbol, QgsRendererCategory,
    )

    categories = []
    for cat in CATEGORIES:
        r, g, b = _CAT_COLORS[cat]
        symbol = QgsFillSymbol.createSimple({
            "color": "{0},{1},{2},50".format(r, g, b),
            "outline_color": "{0},{1},{2},255".format(r, g, b),
            "outline_width": "0.6",
        })
        categories.append(QgsRendererCategory(cat, symbol, "CAT {0}".format(cat)))
    v_layer.setRenderer(QgsCategorizedSymbolRenderer("category", categories))
    v_layer.triggerRepaint()


def run_circling(iface, threshold_layer, params=None):
    """Build the Circling Protection Area layer from the selected threshold
    points.

    :param iface: QGIS interface.
    :param threshold_layer: Point layer with two or more selected threshold
        features.
    :param params: dict with keys ``elev`` (float), ``elev_unit`` ('ft'|'m'),
        ``bank_deg``, ``delta_isa``, ``prot_height_ft``, ``ias_by_cat``
        (``{cat: ias_kt}`` for the categories to draw), ``export_kml`` (bool)
        and ``output_dir`` (str).
    :return: dict with ``layer``, ``summary`` (``{cat: params_dict}``) and
        ``kml_path`` on success, or ``False`` on failure.
    """
    if params is None:
        params = {}

    selected = list(threshold_layer.selectedFeatures())
    if len(selected) < 2:
        iface.messageBar().pushMessage(
            "QPANSOPY:", "Select at least 2 threshold features before calculating",
            level=Qgis.Warning,
        )
        return False

    ias_by_cat = params.get("ias_by_cat") or {}
    if not ias_by_cat:
        iface.messageBar().pushMessage(
            "QPANSOPY:", "Enable at least one aircraft category", level=Qgis.Warning,
        )
        return False

    elev_ft = _elev_to_ft(float(params.get("elev", 0.0)),
                          params.get("elev_unit", "ft"))
    bank_deg = float(params.get("bank_deg", 20.0))
    delta_isa = float(params.get("delta_isa", 15.0))
    prot_height_ft = float(params.get("prot_height_ft", 1000.0))

    project = QgsProject.instance()
    map_crs = iface.mapCanvas().mapSettings().destinationCrs()
    map_srid = map_crs.authid()
    if map_crs.isGeographic():
        iface.messageBar().pushMessage(
            "QPANSOPY:",
            "Map CRS is geographic; circling radii assume a projected metre CRS",
            level=Qgis.Warning,
        )

    points = _threshold_points_map_crs(selected, threshold_layer, map_crs, project)

    v_layer = QgsVectorLayer(
        "Polygon?crs={0}".format(map_srid), "Circling Protection Area", "memory",
    )
    pr = v_layer.dataProvider()
    pr.addAttributes([
        QgsField("category", QVariant.String),
        QgsField("ias_kt", QVariant.Double),
        QgsField("protected_height_ft", QVariant.Double),
        QgsField("aerodrome_elev_ft", QVariant.Double),
        QgsField("bank_deg", QVariant.Double),
        QgsField("delta_isa_c", QVariant.Double),
        QgsField("h1_ft", QVariant.Double),
        QgsField("k_factor", QVariant.Double),
        QgsField("tas_kt", QVariant.Double),
        QgsField("tas_plus_wind_kt", QVariant.Double),
        QgsField("rate_turn_calc_deg_s", QVariant.Double),
        QgsField("rate_turn_used_deg_s", QVariant.Double),
        QgsField("nominal_radius_nm", QVariant.Double),
        QgsField("straight_segment_nm", QVariant.Double),
        QgsField("circling_radius_nm", QVariant.Double),
        QgsField("parameters", QVariant.String),
    ])
    v_layer.updateFields()

    summary = {}
    features = []
    # Draw the largest categories first so the smaller ones stay visible on top.
    for cat in reversed(CATEGORIES):
        if cat not in ias_by_cat:
            continue
        ias_kt = float(ias_by_cat[cat])
        res = calc_circling_category(
            ias_kt, prot_height_ft, elev_ft, bank_deg, delta_isa, S_CONST[cat],
        )
        summary[cat] = res

        area = build_circling_area(points, res["circling_radius_nm"] * NM2M)
        if area is None or area.isEmpty():
            iface.messageBar().pushMessage(
                "QPANSOPY:", "CAT {0} area is empty -- check the map CRS".format(cat),
                level=Qgis.Warning,
            )
            continue

        row = {
            "category": cat,
            "ias_kt": round(ias_kt, 4),
            "protected_height_ft": round(prot_height_ft, 4),
            "aerodrome_elev_ft": round(elev_ft, 4),
            "bank_deg": round(bank_deg, 4),
            "delta_isa_c": round(delta_isa, 4),
            "h1_ft": round(res["h1_ft"], 4),
            "k_factor": round(res["k_factor"], 4),
            "tas_kt": round(res["tas_kt"], 4),
            "tas_plus_wind_kt": round(res["tas_plus_wind_kt"], 4),
            "rate_turn_calc_deg_s": round(res["rate_turn_calc"], 4),
            "rate_turn_used_deg_s": round(res["rate_turn_used"], 4),
            "nominal_radius_nm": round(res["nominal_radius_nm"], 4),
            "straight_segment_nm": round(res["straight_segment_nm"], 4),
            "circling_radius_nm": round(res["circling_radius_nm"], 4),
        }
        feat = QgsFeature()
        feat.setGeometry(area)
        feat.setAttributes([
            row["category"], row["ias_kt"], row["protected_height_ft"],
            row["aerodrome_elev_ft"], row["bank_deg"], row["delta_isa_c"],
            row["h1_ft"], row["k_factor"], row["tas_kt"], row["tas_plus_wind_kt"],
            row["rate_turn_calc_deg_s"], row["rate_turn_used_deg_s"],
            row["nominal_radius_nm"], row["straight_segment_nm"],
            row["circling_radius_nm"], json.dumps(row),
        ])
        features.append(feat)

    if not features:
        iface.messageBar().pushMessage(
            "QPANSOPY:", "No circling areas could be built", level=Qgis.Critical,
        )
        return False

    pr.addFeatures(features)
    v_layer.updateExtents()

    try:
        _apply_categorized_style(v_layer)
    except Exception:  # nosec B110 - cosmetic styling must not abort a good calc
        pass

    project.addMapLayer(v_layer)
    register_parameters_action(v_layer)

    kml_path = None
    if params.get("export_kml"):
        output_dir = params.get("output_dir") or ""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        kml_path = os.path.join(output_dir, "circling_area_{0}.kml".format(timestamp))
        crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        write_error = QgsVectorFileWriter.writeAsVectorFormat(
            v_layer, kml_path, "utf-8", crs_wgs84, "KML", layerOptions=["MODE=2"],
        )
        if write_error[0] == QgsVectorFileWriter.NoError:
            fix_kml_altitude_mode(kml_path)
        else:
            kml_path = None
            iface.messageBar().pushMessage(
                "QPANSOPY:", "KML export failed", level=Qgis.Warning,
            )

    try:
        v_layer.selectAll()
        iface.mapCanvas().zoomToSelected(v_layer)
        v_layer.removeSelection()
    except Exception:  # nosec B110 - zoom is a convenience, never fatal
        pass

    iface.messageBar().pushMessage(
        "QPANSOPY:", "Circling Protection Area created successfully",
        level=Qgis.Success,
    )
    return {"layer": v_layer, "summary": summary, "kml_path": kml_path}
