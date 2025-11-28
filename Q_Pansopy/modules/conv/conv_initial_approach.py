'''
CONV Initial Approach Segment Straight
'''

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *
import os

def run_conv_initial_approach(iface, routing_layer, params=None):
    """
    Generate CONV Initial Approach areas (primary and secondary) with true 3D Z values.

    Parameters (via params dict):
    - procedure_altitude_ft (float): Procedure altitude in feet. Default 1000.
    - moc_value (float): MOC value numeric. Default 300.
    - moc_unit (str): 'ft' or 'm'. Default 'ft'.

    Z calculation rules:
    - Primary area Z (meters) = Procedure Altitude (ft) -> m - MOC (converted to m)
    - Secondary areas: inner edge Z = Primary Z; outer edge Z = Primary Z + MOC (i.e., equals Procedure Altitude in meters)
    """
    try:
        params = params or {}
        # Inputs and conversions
        procedure_altitude_ft = float(params.get('procedure_altitude_ft', 1000))
        moc_value = float(params.get('moc_value', 300))
        moc_unit = str(params.get('moc_unit', 'ft')).lower()

        ft_to_m = 0.3048
        proc_alt_m = procedure_altitude_ft * ft_to_m
        moc_m = moc_value * ft_to_m if moc_unit == 'ft' else moc_value
        z_primary = proc_alt_m - moc_m
        z_outer = z_primary + moc_m  # equals proc_alt_m

        # Get Projected Coordinate System for the QGIS Project 
        map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
        
        # Verify routing layer is provided and has correct name
        if not routing_layer:
            iface.messageBar().pushMessage("No routing layer provided", level=Qgis.Critical)
            return False
            
        # Check if the layer name contains "routing" (like original script)
        if "routing" not in routing_layer.name().lower():
            iface.messageBar().pushMessage(f"Selected layer '{routing_layer.name()}' does not appear to be a routing layer", level=Qgis.Warning)
        
        # Check if there are selected features
        selection = routing_layer.selectedFeatures()
        if not selection:
            iface.messageBar().pushMessage("No features selected in routing layer", level=Qgis.Critical)
            return False
            
        iface.messageBar().pushMessage("QPANSOPY:", "Executing CONV Initial Approach Segment Straight", level=Qgis.Info)
        
        features_processed = 0
        for feat in selection:
            geom = feat.geometry().asPolyline()
            if len(geom) < 2:
                iface.messageBar().pushMessage("Invalid geometry - need at least 2 points", level=Qgis.Warning)
                continue
                
            # Note: Using the original logic with start_point as geom[-1] and end_point as geom[0]
            start_point = QgsPoint(geom[-1])
            end_point = QgsPoint(geom[0])
            angle0 = start_point.azimuth(end_point) + 180
            length0 = feat.geometry().length()
            
            # Debug information
            iface.messageBar().pushMessage("Debug:", f"Length: {length0/1852:.2f} NM, Azimuth: {angle0:.1f}°", level=Qgis.Info)
                
            azimuth = angle0
            
            pts = {}
            a = 0

            # routine 1 FAF determination
            bearing = azimuth
            angle = 90 - bearing
            bearing = radians(bearing)
            angle = radians(angle)
            dist_x, dist_y = (length0 * cos(angle), length0 * sin(angle))
            
            pts["m"+str(a)] = QgsPoint(end_point.x() + dist_x, end_point.y() + dist_y)
            a += 1
            
            pts["m"+str(a)] = QgsPoint(end_point.x(), end_point.y())
            a += 1

            # calculating bottom points
            d = (2.5, 5, -2.5, -5)  # NM

            for i in d:
                TNA_dist = i * 1852
                bearing = azimuth + 90
                angle = 90 - bearing
                bearing = radians(bearing)
                angle = radians(angle)
                dist_x, dist_y = (TNA_dist * cos(angle), TNA_dist * sin(angle))
                bx1, by2 = (start_point.x() + dist_x, start_point.y() + dist_y)

                line_start = QgsPoint(bx1, by2)
                pts["m"+str(a)] = line_start
                a += 1
                
            # calculating top points
            d = (2.5, 5, -2.5, -5)  # NM

            for i in d:
                TNA_dist = i * 1852
                bearing = azimuth + 90
                angle = 90 - bearing
                bearing = radians(bearing)
                angle = radians(angle)
                dist_x, dist_y = (TNA_dist * cos(angle), TNA_dist * sin(angle))
                bx1, by2 = (end_point.x() + dist_x, end_point.y() + dist_y)

                line_start = QgsPoint(bx1, by2)
                pts["m"+str(a)] = line_start
                a += 1

            # Debug: Check if we have all required points
            required_points = ["m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9"]
            missing_points = [p for p in required_points if p not in pts]
            if missing_points:
                iface.messageBar().pushMessage("Error:", f"Missing points: {missing_points}", level=Qgis.Critical)
                return False

            # Create memory layer
            v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "CONV Initial Approach Areas", "memory")
            fields = [
                QgsField('Symbol', QVariant.String),
                QgsField('proc_alt_ft', QVariant.Double),
                QgsField('moc', QVariant.Double),
                QgsField('moc_unit', QVariant.String),
                QgsField('z_primary_m', QVariant.Double),
                QgsField('z_outer_m', QVariant.Double)
            ]
            v_layer.dataProvider().addAttributes(fields)
            v_layer.updateFields()

            # Define areas as polygons exactly as in the original code
            # Primary Area
            primary_ring = [pts["m2"], pts["m0"], pts["m4"], pts["m8"], pts["m1"], pts["m6"]]
            primary_area = (primary_ring, 'Primary Area')
            
            # Secondary Area Left
            sec_left_ring = [pts["m3"], pts["m2"], pts["m6"], pts["m7"]]
            secondary_area_left = (sec_left_ring, 'Secondary Area (Left)')
            
            # Secondary Area Right
            sec_right_ring = [pts["m4"], pts["m5"], pts["m9"], pts["m8"]]
            secondary_area_right = (sec_right_ring, 'Secondary Area (Right)')
            
            areas = (primary_area, secondary_area_left, secondary_area_right)

            # Create polygon features
            pr = v_layer.dataProvider()
            features_created = 0

            def create_polygon_with_z(ring_points, z_values):
                """
                Create a 3D polygon with proper Z values.
                
                :param ring_points: List of QgsPoint (2D or 3D)
                :param z_values: Single value or list of Z values for each vertex
                :return: QgsGeometry of the polygon with Z values
                """
                # Ensure z_values is a list matching ring_points length
                if not isinstance(z_values, (list, tuple)):
                    z_values = [z_values] * len(ring_points)
                
                # Create 3D points with explicit Z values
                points_3d = []
                for i, pt in enumerate(ring_points):
                    z = z_values[i] if i < len(z_values) else z_values[-1]
                    points_3d.append(QgsPoint(pt.x(), pt.y(), float(z)))
                
                # Close the ring by adding the first point at the end if not already closed
                if len(points_3d) > 0:
                    first_pt = points_3d[0]
                    last_pt = points_3d[-1]
                    if first_pt.x() != last_pt.x() or first_pt.y() != last_pt.y():
                        points_3d.append(QgsPoint(first_pt.x(), first_pt.y(), first_pt.z()))
                
                # Create the polygon geometry
                line_string = QgsLineString(points_3d)
                polygon = QgsPolygon()
                polygon.setExteriorRing(line_string)
                
                return QgsGeometry(polygon)

            try:
                # Primary area: all vertices at z_primary
                geom = create_polygon_with_z(primary_area[0], z_primary)
                f = QgsFeature()
                f.setGeometry(geom)
                f.setAttributes([
                    primary_area[1],
                    procedure_altitude_ft,
                    moc_value,
                    moc_unit,
                    round(z_primary, 2),
                    round(z_outer, 2)
                ])
                pr.addFeatures([f])
                features_created += 1
            except Exception as area_error:
                iface.messageBar().pushMessage("Error creating primary area:", str(area_error), level=Qgis.Warning)

            try:
                # Secondary left: [outer(+5), inner(+2.5), inner(+2.5), outer(+5)]
                # Points order: m3(outer), m2(inner), m6(inner), m7(outer)
                geom = create_polygon_with_z(secondary_area_left[0], [z_outer, z_primary, z_primary, z_outer])
                f = QgsFeature()
                f.setGeometry(geom)
                f.setAttributes([
                    secondary_area_left[1],
                    procedure_altitude_ft,
                    moc_value,
                    moc_unit,
                    round(z_primary, 2),
                    round(z_outer, 2)
                ])
                pr.addFeatures([f])
                features_created += 1
            except Exception as area_error:
                iface.messageBar().pushMessage("Error creating secondary left area:", str(area_error), level=Qgis.Warning)

            try:
                # Secondary right: [inner(-2.5), outer(-5), outer(-5), inner(-2.5)]
                # Points order: m4(inner), m5(outer), m9(outer), m8(inner)
                geom = create_polygon_with_z(secondary_area_right[0], [z_primary, z_outer, z_outer, z_primary])
                f = QgsFeature()
                f.setGeometry(geom)
                f.setAttributes([
                    secondary_area_right[1],
                    procedure_altitude_ft,
                    moc_value,
                    moc_unit,
                    round(z_primary, 2),
                    round(z_outer, 2)
                ])
                pr.addFeatures([f])
                features_created += 1
            except Exception as area_error:
                iface.messageBar().pushMessage("Error creating secondary right area:", str(area_error), level=Qgis.Warning)

            v_layer.updateExtents()
            QgsProject.instance().addMapLayers([v_layer])

            # Apply style
            style_path = os.path.join(os.path.dirname(__file__), '..', '..', 'styles', 'primary_secondary_areas.qml')
            if os.path.exists(style_path):
                v_layer.loadNamedStyle(style_path)
            else:
                iface.messageBar().pushMessage("Warning:", f"Style file not found at {style_path}", level=Qgis.Warning)

            # Zoom to layer
            v_layer.selectAll()
            canvas = iface.mapCanvas()
            canvas.zoomToSelected(v_layer)
            v_layer.removeSelection()

            iface.messageBar().pushMessage(
                "QPANSOPY:",
                f"Finished CONV Initial Approach Segment - {features_created} areas created for {features_processed} features (Z_primary={z_primary:.2f} m, Z_outer={z_outer:.2f} m)",
                level=Qgis.Success
            )
            features_processed += 1
            
        return True
        
    except Exception as e:
        iface.messageBar().pushMessage("Error creating CONV Initial Approach areas", str(e), level=Qgis.Critical)
        import traceback
        iface.messageBar().pushMessage("Traceback:", traceback.format_exc(), level=Qgis.Critical)
        return False
