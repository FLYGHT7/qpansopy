from qgis.core import (
    QgsProject,
    QgsFeatureRequest,
    QgsSpatialIndex,
    QgsCoordinateTransform,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsFeature,
    QgsSymbol,
    QgsSimpleMarkerSymbolLayer,
    QgsVectorFileWriter,
    Qgis
)
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QPushButton
from PyQt5.QtGui import QColor
import os
import datetime

# Función extract_objects modificada para ejecutar directamente sin diálogos
def extract_objects(iface, point_layer, surface_layer, export_kml=False, output_dir=None, use_selection_only=False):
    """
    Extract objects that intersect with the surface
    
    Args:
        iface: QGIS interface
        point_layer: The layer containing obstacles/points
        surface_layer: The layer defining the extraction area (polygon)
        export_kml: Whether to export as KML
        output_dir: Directory for KML export
        use_selection_only: Whether to use only selected features
    
    Returns:
        Dictionary with extraction results
    """
    result = {'count': 0, 'features': []}
    
    if not point_layer or not surface_layer:
        return result
    
    # Get surface geometry
    surface_features = surface_layer.selectedFeatures() if use_selection_only else surface_layer.getFeatures()
    surface_geom = None
    
    # Combine all surface geometries
    for feat in surface_features:
        if surface_geom is None:
            surface_geom = feat.geometry()
        else:
            surface_geom = surface_geom.combine(feat.geometry())
    
    if surface_geom is None:
        return result
    
    # Create a new layer for the extracted objects
    crs = point_layer.crs()
    extracted_layer = QgsVectorLayer(f"Point?crs={crs.authid()}", "extracted_objects", "memory")
    
    # Copy fields from point layer
    provider = extracted_layer.dataProvider()
    provider.addAttributes(point_layer.fields())
    extracted_layer.updateFields()
    
    # Check intersections and add features
    for feat in point_layer.getFeatures():
        if surface_geom.intersects(feat.geometry()):
            # Create new feature and add it to the result layer
            new_feat = QgsFeature(feat)
            provider.addFeatures([new_feat])
            result['features'].append(new_feat)
            result['count'] += 1
    
    # Update layer
    extracted_layer.updateExtents()
    
    # Add to map
    QgsProject.instance().addMapLayer(extracted_layer)
    
    # Export to KML if requested
    if export_kml and output_dir and result['count'] > 0:
        kml_path = os.path.join(output_dir, "extracted_objects.kml")
        QgsVectorFileWriter.writeAsVectorFormat(
            extracted_layer,
            kml_path,
            "utf-8",
            crs,
            "KML"
        )
    
    return result

def copy_parameters_table(params):
    """Generate formatted table for Object Selection parameters"""
    from ..utils import format_parameters_table
    
    params_dict = {
        'visualization': {
            'marker_size': {'value': params.get('marker_size', 3), 'unit': 'px'}
        },
        'layers': {
            'point_layer': {'value': params.get('point_layer_name', ''), 'unit': ''},
            'surface_layer': {'value': params.get('surface_layer_name', ''), 'unit': ''}
        }
    }

    sections = {
        'marker_size': 'Visualization',
        'point_layer': 'Input Layers',
        'surface_layer': 'Input Layers'
    }

    return format_parameters_table(
        "QPANSOPY OBJECT SELECTION PARAMETERS",
        params_dict,
        sections
    )

# ELIMINADO: todo el código que muestra un diálogo al importar
# dlg = LayerSelectionDialog()
# if not dlg.exec_():
#     raise Exception("User cancelled.")
# opea_layer, ils_layer = dlg.getSelections()
# map_crs = QgsProject.instance().crs()
# result = extract_objects(iface, opea_layer, ils_layer, export_kml=False)
# print(f"{result['count']} features extracted to 'extracted' layer.")