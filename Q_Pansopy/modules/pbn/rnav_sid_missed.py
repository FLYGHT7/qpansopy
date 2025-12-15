from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsWkbTypes, QgsCoordinateReferenceSystem
from qgis.core import QgsCoordinateTransform, QgsPointXY
from qgis.PyQt.QtGui import QColor
from qgis.core import Qgis
from math import radians


def _nm_to_m(nm: float) -> float:
    return nm * 1852.0


def run_rnav_sid_missed(iface, routing_layer, rnav_mode: str, op_mode: str,
                        export_kml: bool = False, output_dir: str | None = None):
    """
    Minimal RNAV1/2 SID or Missed template generator.
    Creates a simple buffered corridor around the selected segment as a placeholder
    for the full spec implementation.
    """
    try:
        sel = routing_layer.selectedFeatures()
        if not sel:
            iface.messageBar().pushMessage("QPANSOPY", "No features selected", level=Qgis.Critical)
            return False

        geom = sel[0].geometry()
        if geom.isEmpty() or geom.type() != QgsWkbTypes.LineGeometry:
            iface.messageBar().pushMessage("QPANSOPY", "Invalid geometry: expected line", level=Qgis.Warning)
            return False

        # Very rough placeholder widths (half-widths)
        half_width_nm = 1.0 if rnav_mode.upper() == 'RNAV1' else 2.0
        half_width_m = _nm_to_m(half_width_nm)

        # Buffer corridor around the selected segment
        corridor = geom.buffer(half_width_m, 24)

        # Memory layer for output (same CRS as project)
        crs = iface.mapCanvas().mapSettings().destinationCrs()
        vlyr = QgsVectorLayer(f"Polygon?crs={crs.authid()}", f"{rnav_mode}_{op_mode}_corridor", "memory")
        pr = vlyr.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(corridor)
        pr.addFeatures([feat])
        vlyr.updateExtents()
        QgsProject.instance().addMapLayer(vlyr)

        # Styling
        try:
            vlyr.renderer().symbol().setColor(QColor("#66c2a5"))
            vlyr.renderer().symbol().setOpacity(0.35)
            vlyr.triggerRepaint()
        except Exception:
            pass

        return {"layer": vlyr}
    except Exception as e:
        iface.messageBar().pushMessage("QPANSOPY", f"RNAV {op_mode} failed: {e}", level=Qgis.Critical)
        return False
