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

# ----- Reprojection if needed -----
if opea_layer.crs().authid() == 'EPSG:4326' and opea_layer.crs() != map_crs:
    transform = QgsCoordinateTransform(opea_layer.crs(), map_crs, QgsProject.instance())
    transformed_features = []
    for f in opea_layer.getFeatures():
        geom = f.geometry()
        if geom and not geom.isEmpty():
            geom.transform(transform)
            f.setGeometry(geom)
            transformed_features.append(f)

    reproj_layer = QgsVectorLayer(f"Point?crs={map_crs.authid()}", "reprojected_opea", "memory")
    reproj_layer.dataProvider().addAttributes(opea_layer.fields())
    reproj_layer.updateFields()
    reproj_layer.dataProvider().addFeatures(transformed_features)
    opea_layer = reproj_layer  # use internally

    iface.messageBar().pushMessage(
        "Reprojection Notice",
        f"'{opea_layer.name()}' was reprojected from EPSG:4326 to match the map CRS.",
        level=Qgis.Info,
        duration=5
    )

# ----- Spatial Index & Intersections -----
ils_index = QgsSpatialIndex(ils_layer.getFeatures())
intersecting_features = []

for pt in opea_layer.getFeatures():
    geom = pt.geometry()
    if not geom:
        continue
    candidate_ids = ils_index.intersects(geom.boundingBox())
    for surf in ils_layer.getFeatures(QgsFeatureRequest().setFilterFids(candidate_ids)):
        if geom.intersects(surf.geometry()):
            intersecting_features.append(pt)
            break

# ----- Create and Style Result Layer -----
extracted_layer = QgsVectorLayer(f"Point?crs={opea_layer.crs().authid()}", "extracted", "memory")
extracted_layer.dataProvider().addAttributes(opea_layer.fields())
extracted_layer.updateFields()
extracted_layer.dataProvider().addFeatures(intersecting_features)

# Style: red dots, size 3, no stroke
symbol = QgsSymbol.defaultSymbol(extracted_layer.geometryType())
symbol_layer = QgsSimpleMarkerSymbolLayer()
symbol_layer.setColor(QColor("red"))
symbol_layer.setSize(3)
symbol_layer.setStrokeColor(QColor(0, 0, 0, 0))  # Transparent stroke
symbol_layer.setStrokeWidth(0)
symbol.changeSymbolLayer(0, symbol_layer)
extracted_layer.renderer().setSymbol(symbol)

# ----- Add to project -----
QgsProject.instance().addMapLayer(extracted_layer)
print(f"{len(intersecting_features)} features extracted to 'extracted' layer.")
