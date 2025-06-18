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
    QgsCoordinateReferenceSystem,
    Qgis
)
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QPushButton
from PyQt5.QtGui import QColor
import os
import datetime

# Mantener la clase de diálogo, pero solo para compatibilidad
class LayerSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Object Extraction")
        self.setLayout(QVBoxLayout())

        self.point_label = QLabel("Select obstacle layer (point):")
        self.point_combo = QComboBox()
        self.surface_label = QLabel("Select Surface to analyze (polygon):")
        self.surface_combo = QComboBox()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        # Populate combos
        self.valid_layers = list(QgsProject.instance().mapLayers().values())
        self.point_layers = [lyr for lyr in self.valid_layers
                             if lyr.type() == QgsVectorLayer.VectorLayer and
                             QgsWkbTypes.geometryType(lyr.wkbType()) == QgsWkbTypes.PointGeometry]
        self.surface_layers = [lyr for lyr in self.valid_layers
                               if lyr.type() == QgsVectorLayer.VectorLayer]

        self.point_combo.addItems([lyr.name() for lyr in self.point_layers])
        self.surface_combo.addItems([lyr.name() for lyr in self.surface_layers])

        # Assemble layout
        self.layout().addWidget(self.point_label)
        self.layout().addWidget(self.point_combo)
        self.layout().addWidget(self.surface_label)
        self.layout().addWidget(self.surface_combo)
        self.layout().addWidget(self.ok_button)

    def getSelections(self):
        return (
            self.point_layers[self.point_combo.currentIndex()],
            self.surface_layers[self.surface_combo.currentIndex()]
        )

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
    
    # Usar el sistema de coordenadas del proyecto actual
    project_crs = QgsProject.instance().crs()
    
    # Verificar si las capas están en el mismo CRS
    point_crs = point_layer.crs()
    surface_crs = surface_layer.crs()
    
    # Crear transformaciones si es necesario
    transform_point_to_project = QgsCoordinateTransform(point_crs, project_crs, QgsProject.instance())
    transform_surface_to_project = QgsCoordinateTransform(surface_crs, project_crs, QgsProject.instance())
    
    # Obtener las geometrías de superficie
    if use_selection_only:
        surface_features = surface_layer.selectedFeatures()
    else:
        surface_features = surface_layer.getFeatures()
        
    surface_geom = None
    
    # Combinar todas las geometrías de superficie, transformándolas al CRS del proyecto
    for feat in surface_features:
        geom = feat.geometry()
        # Transformar al CRS del proyecto si es necesario
        if surface_crs != project_crs:
            geom.transform(transform_surface_to_project)
            
        if surface_geom is None:
            surface_geom = geom
        else:
            surface_geom = surface_geom.combine(geom)
    
    if surface_geom is None:
        return result
    
    # Crear una nueva capa para los objetos extraídos usando el CRS del proyecto
    current_date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    point_name = point_layer.name().replace(" ", "_")
    surface_name = surface_layer.name().replace(" ", "_")
    layer_name = f"Extracted_{point_name}_from_{surface_name}"
    
    extracted_layer = QgsVectorLayer(f"Point?crs={project_crs.authid()}", layer_name, "memory")
    
    # Copiar campos de la capa de puntos
    provider = extracted_layer.dataProvider()
    provider.addAttributes(point_layer.fields())
    extracted_layer.updateFields()
    
    # Verificar intersecciones y añadir características
    for feat in point_layer.getFeatures():
        geom = feat.geometry()
        # Transformar al CRS del proyecto si es necesario
        if point_crs != project_crs:
            geom = geom.clone()
            geom.transform(transform_point_to_project)
            
        if surface_geom.intersects(geom):
            # Crear nueva característica y añadirla a la capa de resultados
            new_feat = QgsFeature(feat)
            new_feat.setGeometry(geom)
            provider.addFeatures([new_feat])
            result['features'].append(new_feat)
            result['count'] += 1
    
    # Actualizar la capa
    extracted_layer.updateExtents()
    
    # Añadir al mapa
    QgsProject.instance().addMapLayer(extracted_layer)
    
    # Exportar a KML si se solicita
    if export_kml and output_dir and result['count'] > 0:
        kml_path = os.path.join(output_dir, f"{layer_name}.kml")
        # Para exportar a KML, necesitamos transformar a WGS84
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        QgsVectorFileWriter.writeAsVectorFormat(
            extracted_layer,
            kml_path,
            "utf-8",
            wgs84_crs,  # Siempre usar WGS84 para KML
            "KML",
            layerOptions=["NameField=name"],  # Usar el campo 'name' para los nombres de objetos si existe
            transformContext=QgsProject.instance().transformContext()
        )
        result['kml_path'] = kml_path
    
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