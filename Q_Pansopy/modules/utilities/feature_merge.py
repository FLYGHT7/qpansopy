from qgis.core import (
    QgsProject, QgsVectorLayer, QgsWkbTypes, QgsFeature,
    QgsFields, QgsField, QgsFeatureRequest
)
from PyQt5.QtCore import QVariant

# Use iface to get selected layers from Layer Panel
selected_layers = iface.layerTreeView().selectedLayers()

# Filter to only vector layers
selected_layers = [layer for layer in selected_layers if isinstance(layer, QgsVectorLayer)]

if len(selected_layers) < 2:
    raise Exception("Select at least two vector layers.")

# Check geometry and CRS compatibility
geom_type = selected_layers[0].wkbType()
crs = selected_layers[0].crs()
for layer in selected_layers[1:]:
    if layer.wkbType() != geom_type:
        raise Exception("Geometry types differ.")
    if layer.crs() != crs:
        raise Exception("CRS differ.")

# Build union of all fields
all_fields = QgsFields()
field_names = {}

for layer in selected_layers:
    for field in layer.fields():
        if field.name() not in field_names:
            all_fields.append(QgsField(field.name(), field.type()))
            field_names[field.name()] = field.type()

# Create memory layer
merged_layer = QgsVectorLayer(f"{QgsWkbTypes.displayString(geom_type)}?crs={crs.authid()}", "Merged_Layer", "memory")
merged_provider = merged_layer.dataProvider()
merged_provider.addAttributes(all_fields)
merged_layer.updateFields()

# Add features from each layer
for layer in selected_layers:
    for feature in layer.getFeatures():
        new_feat = QgsFeature(merged_layer.fields())
        new_feat.setGeometry(feature.geometry())
        for field in layer.fields():
            if field.name() in field_names:
                new_feat.setAttribute(field.name(), feature[field.name()])
        merged_provider.addFeature(new_feat)

merged_layer.updateExtents()
QgsProject.instance().addMapLayer(merged_layer)
