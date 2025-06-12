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
    Qgis
)
from qgis.utils import iface
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QPushButton
from PyQt5.QtGui import QColor
import os
import datetime

# ----- Custom UI Dialog -----
class LayerSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Object Extraction")  # Updated window title
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

# ----- Show UI and get layers -----
dlg = LayerSelectionDialog()
if not dlg.exec_():
    raise Exception("User cancelled.")

opea_layer, ils_layer = dlg.getSelections()
map_crs = QgsProject.instance().crs()

def extract_objects(iface, point_layer, surface_layer, export_kml=False, output_dir=None, use_selection_only=False):
    """Extract objects that intersect with surfaces"""
    try:
        # Get surfaces to process
        if use_selection_only:
            if surface_layer.selectedFeatureCount() == 0:
                iface.messageBar().pushMessage("Error", "No features selected in surface layer", level=Qgis.Critical)
                return None
            surfaces = surface_layer.selectedFeatures()
        else:
            surfaces = surface_layer.getFeatures()
    
        # Reprojection if needed
        if point_layer.crs().authid() == 'EPSG:4326' and point_layer.crs() != map_crs:
            transform = QgsCoordinateTransform(point_layer.crs(), map_crs, QgsProject.instance())
            transformed_features = []
            for f in point_layer.getFeatures():
                geom = f.geometry()
                if geom and not geom.isEmpty():
                    geom.transform(transform)
                    f.setGeometry(geom)
                    transformed_features.append(f)

            reproj_layer = QgsVectorLayer(f"Point?crs={map_crs.authid()}", "reprojected_opea", "memory")
            reproj_layer.dataProvider().addAttributes(point_layer.fields())
            reproj_layer.updateFields()
            reproj_layer.dataProvider().addFeatures(transformed_features)
            point_layer = reproj_layer  # use internally

            iface.messageBar().pushMessage(
                "Reprojection Notice",
                f"'{point_layer.name()}' was reprojected from EPSG:4326 to match the map CRS.",
                level=Qgis.Info,
                duration=5
            )

        # Spatial Index & Intersections
        surface_index = QgsSpatialIndex(surface_layer.getFeatures())
        intersecting_features = []

        for pt in point_layer.getFeatures():
            geom = pt.geometry()
            if not geom:
                continue
            candidate_ids = surface_index.intersects(geom.boundingBox())
            for surf in surfaces:
                if geom.intersects(surf.geometry()):
                    intersecting_features.append(pt)
                    break

        # Create result layer
        extracted_layer = QgsVectorLayer(f"Point?crs={point_layer.crs().authid()}", 
                                       "extracted_objects", "memory")
        extracted_layer.dataProvider().addAttributes(point_layer.fields())
        extracted_layer.updateFields()
        extracted_layer.dataProvider().addFeatures(intersecting_features)

        # Style layer
        symbol = QgsSymbol.defaultSymbol(extracted_layer.geometryType())
        symbol_layer = QgsSimpleMarkerSymbolLayer()
        symbol_layer.setColor(QColor("red"))
        symbol_layer.setSize(3)
        symbol_layer.setStrokeColor(QColor(0, 0, 0, 0))
        symbol_layer.setStrokeWidth(0)
        symbol.changeSymbolLayer(0, symbol_layer)
        extracted_layer.renderer().setSymbol(symbol)

        # Add to project
        QgsProject.instance().addMapLayer(extracted_layer)
        
        # Export to KML if requested
        if export_kml and output_dir:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            kml_path = os.path.join(output_dir, f'extracted_objects_{timestamp}.kml')
            
            QgsVectorFileWriter.writeAsVectorFormat(
                extracted_layer,
                kml_path,
                'utf-8',
                QgsCoordinateReferenceSystem('EPSG:4326'),
                'KML'
            )

        return {"count": count, "features": extracted_features}
    except Exception as e:
        iface.messageBar().pushMessage("Error", str(e), level=Qgis.Critical)
        return None

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

# Call the extraction function
result = extract_objects(iface, opea_layer, ils_layer, export_kml=False)
print(f"{result['count']} features extracted to 'extracted' layer.")