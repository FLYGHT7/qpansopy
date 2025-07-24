# -*- coding: utf-8 -*-
"""
PBN LNAV Missed Approach (RNP APCH) Generator
"""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsCoordinateReferenceSystem, QgsPoint, QgsLineString, 
    QgsPolygon, QgsField, QgsWkbTypes, QgsVectorFileWriter
)
from qgis.PyQt.QtCore import QVariant
from qgis.core import Qgis
from qgis.utils import iface
import math
import os
import datetime

def run_missed_approach(iface_param, routing_layer, export_kml=False, output_dir=None):
    """
    Run LNAV Missed Approach calculation
    
    :param iface_param: QGIS interface
    :param routing_layer: Routing layer 
    :param export_kml: Whether to export KML
    :param output_dir: Output directory 
    :return: Result dictionary or None
    """
    try:
        # Use the passed iface parameter
        iface = iface_param
        
        iface.messageBar().pushMessage("QPANSOPY:", "Executing LNAV Missed Approach (RNP APCH)", level=Qgis.Info)

        # Get Projected Coordinate System for the QGIS Project 
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

        # Use the provided routing layer instead of searching
        if routing_layer is None:
            # Fallback: search for routing layer (original behavior)
            for layer in QgsProject.instance().mapLayers().values():
                if "routing" in layer.name():
                    routing_layer = layer
                    break

        if routing_layer is None:
            iface.messageBar().pushMessage("No Routing Selected", level=Qgis.Critical)
            return None

        # Original behavior: select all missed segments automatically
        routing_layer.selectAll()
        routing_layer.selectByExpression("segment='missed'")
        selected_features = routing_layer.selectedFeatures()

        if not selected_features:
            iface.messageBar().pushMessage("No 'missed' segment found in routing layer", level=Qgis.Critical)
            return None
            
        # Process the selected features - use the first valid missed segment found (original behavior)
        for feat in selected_features:
            try:
                geom = feat.geometry().asPolyline()
                if geom and len(geom) >= 2:
                    start_point = QgsPoint(geom[0])
                    end_point = QgsPoint(geom[-1])
                    azimuth = start_point.azimuth(end_point)
                    back_azimuth = azimuth + 180
                    length = feat.geometry().length()
                    break
            except:
                iface.messageBar().pushMessage("Invalid geometry in selected feature", level=Qgis.Warning)
                continue
        else:
            iface.messageBar().pushMessage("No valid geometry found in missed segments", level=Qgis.Critical)
            return None

        # ATT tolerance in meters (keep original logic)
        att = 0.24 * 1852  
        
        # Calculate points dictionary (keep original algorithm)
        pts = {}
        a = 0
        
        # Initial points with ATT tolerance
        pts[f"m{a}"] = end_point.project(att, azimuth)
        a += 1
        
        pts[f"m{a}"] = start_point.project(att, back_azimuth)
        a += 1
        
        # Calculate earliest points
        d = (0.475, 0.95, -0.475, -0.95)  # NM
        
        for i in d:
            bearing = azimuth + 90
            angle = 90 - bearing + 180
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = i * 1852 * math.cos(angle)
            dist_y = i * 1852 * math.sin(angle)
            
            bx1 = pts["m1"].x() + dist_x
            by2 = pts["m1"].y() + dist_y
            
            pts[f"m{a}"] = QgsPoint(bx1, by2)
            a += 1
        
        # Calculate intermediate points
        d = (-1, -2, 1, 2)  # NM
        
        lengthm = (2 - 0.95) / math.tan(math.radians(15))  # NM
        bearing = azimuth
        angle = 90 - bearing
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        dist_x = lengthm * 1852 * math.cos(angle)
        dist_y = lengthm * 1852 * math.sin(angle)
        
        xm = pts["m1"].x() + dist_x
        ym = pts["m1"].y() + dist_y
        pm = QgsPoint(xm, ym)
        
        for i in d:
            TNA_dist = i * 1852
            bearing = azimuth + 90
            angle = 90 - bearing
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = TNA_dist * math.cos(angle)
            dist_y = TNA_dist * math.sin(angle)
            
            bx1 = xm + dist_x
            by2 = ym + dist_y
            
            pts[f"mm{a}"] = QgsPoint(bx1, by2)
            a += 1
        
        # Calculate final points
        d = (-1, -2, 1, 2)  # NM
        
        if length / 1852 < 5:
            lengthm = 5.24  # 5 NM default
        else:
            lengthm = length / 1852 + 0.24
        
        bearing = azimuth
        angle = 90 - bearing
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        dist_x = lengthm * 1852 * math.cos(angle)
        dist_y = lengthm * 1852 * math.sin(angle)
        
        xm = pts["m1"].x() + dist_x
        ym = pts["m1"].y() + dist_y
        pf = QgsPoint(xm, ym)
        
        for i in d:
            TNA_dist = i * 1852
            bearing = azimuth + 90
            angle = 90 - bearing
            bearing = math.radians(bearing)
            angle = math.radians(angle)
            dist_x = TNA_dist * math.cos(angle)
            dist_y = TNA_dist * math.sin(angle)
            
            bx1 = xm + dist_x
            by2 = ym + dist_y
            
            pts[f"mm{a}"] = QgsPoint(bx1, by2)
            a += 1
        
        # Create memory layer (original name)
        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "LNAV Missed", "memory")
        myField = QgsField('Symbol', QVariant.String)
        v_layer.dataProvider().addAttributes([myField])
        v_layer.updateFields()

        # Area Definition 
        primary_area = ([pts["m2"], pts["mm6"], pts["mm10"], pf, pts["mm12"], pts["mm8"], pts["m4"], pts["m1"]], 'Primary Area')
        secondary_area_left = ([pts["m2"], pts["m3"], pts["mm7"], pts["mm11"], pts["mm10"], pts["mm6"]], 'Secondary Area')
        secondary_area_right = ([pts["m5"], pts["m4"], pts["mm8"], pts["mm12"], pts["mm13"], pts["mm9"]], 'Secondary Area')

        areas = (primary_area, secondary_area_left, secondary_area_right)

        # Creating areas
        pr = v_layer.dataProvider()
        features = []
        
        for area in areas:
            seg = QgsFeature()
            seg.setGeometry(QgsPolygon(QgsLineString(area[0]), rings=[]))
            seg.setAttributes([area[1]])
            features.append(seg)

        pr.addFeatures(features)
        v_layer.updateExtents()
        QgsProject.instance().addMapLayers([v_layer])

        # Apply style (no zoom to respect user's current view)
        style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'primary_secondary_areas.qml')
        if os.path.exists(style_path):
            v_layer.loadNamedStyle(style_path)
        
        # Export to KML if requested
        result = {'missed_layer': v_layer}
        
        if export_kml and output_dir:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            kml_export_path = os.path.join(output_dir, f'PBN_LNAV_Missed_Approach_{timestamp}.kml')
            
            crs = QgsCoordinateReferenceSystem("EPSG:4326")
            
            kml_error = QgsVectorFileWriter.writeAsVectorFormat(
                v_layer,
                kml_export_path,
                'utf-8',
                crs,
                'KML',
                layerOptions=['MODE=2']
            )
            
            if kml_error[0] == QgsVectorFileWriter.NoError:
                result['kml_path'] = kml_export_path
                iface.messageBar().pushMessage("QPANSOPY:", f"KML exported to: {kml_export_path}", level=Qgis.Success)

        iface.messageBar().pushMessage("QPANSOPY:", "Finished Intermediate RNAV1/2 <30NM", level=Qgis.Success)
        
        return result
        
    except Exception as e:
        iface.messageBar().pushMessage("Error", f"Error in missed approach: {str(e)}", level=Qgis.Critical)
        return None


# Legacy script execution (for backward compatibility when run directly)
if __name__ == "__main__":
    # This will run when the script is executed directly in QGIS console
    from qgis.utils import iface
    result = run_missed_approach(iface, None)
    if result:
        print("Missed approach calculation completed successfully")
    else:
        print("Missed approach calculation failed")
