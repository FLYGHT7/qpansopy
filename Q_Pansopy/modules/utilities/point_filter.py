from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

layer = iface.activeLayer()
print (layer)
if layer is None:
    print("No active layer selected.")
else:
    crs = layer.crs().authid()
    mem_layer_name = layer.name() + "_higher_than_THR_elev"
    mem_layer = QgsVectorLayer(f"Point?crs={crs}", mem_layer_name, "memory")
    mem_layer_data = mem_layer.dataProvider()

    fields = layer.fields()
    for field in fields:
        mem_layer_data.addAttributes([field])

    # Add custom fields x_dist, y_dist, z_height
    mem_layer_data.addAttributes([
        QgsField("x_dist", QVariant.Double, "double", 10, 3),
        QgsField("y_dist", QVariant.Double, "double", 10, 3),
        QgsField("z_height", QVariant.Double, "double", 10, 3)
    ])

    mem_layer.updateFields()

    lower_layer_name = layer.name() + "_lower_than_THR_elev"
    lower_layer = QgsVectorLayer(f"Point?crs={crs}", lower_layer_name, "memory")
    lower_layer_data = lower_layer.dataProvider()

    fields_lower = layer.fields()
    for field in fields_lower:
        lower_layer_data.addAttributes([field])

    # Add custom fields x_dist, y_dist, z_height
    lower_layer_data.addAttributes([
        QgsField("x_dist", QVariant.Double, "double", 10, 3),
        QgsField("y_dist", QVariant.Double, "double", 10, 3),
        QgsField("z_height", QVariant.Double, "double", 10, 3)
    ])

    lower_layer.updateFields()

    mem_layer.startEditing()
    lower_layer.startEditing()

    user_input, ok = QInputDialog.getDouble(None, "Input THR elev", "THR elev in meters:", decimals=6)

    if ok:
        try:
            idx_value = layer.fields().indexFromName("elev")
            idx_x_dist = mem_layer.fields().indexFromName("x_dist")
            idx_y_dist = mem_layer.fields().indexFromName("y_dist")
            idx_z_height = mem_layer.fields().indexFromName("z_height")

            idx_x_dist_lower = lower_layer.fields().indexFromName("x_dist")
            idx_y_dist_lower = lower_layer.fields().indexFromName("y_dist")
            idx_z_height_lower = lower_layer.fields().indexFromName("z_height")

            sym_above = QgsSymbol.defaultSymbol(mem_layer.geometryType())
            sym_above.setColor(QColor("red"))
            sym_above.setSize(0.25)
            sym_above.symbolLayer(0).setStrokeStyle(Qt.NoPen)
            mem_layer.renderer().setSymbol(sym_above)

            sym_below = QgsSymbol.defaultSymbol(lower_layer.geometryType())
            sym_below.setColor(QColor("green"))
            sym_below.setSize(0.25)
            sym_below.symbolLayer(0).setStrokeStyle(Qt.NoPen)
            lower_layer.renderer().setSymbol(sym_below)

            for feature in layer.getFeatures():
                value = feature[idx_value]
                if value >= user_input:
                    mem_layer_data.addFeature(feature)
                    z_height = value - user_input
                    mem_layer.changeAttributeValue(feature.id(), idx_z_height, z_height)

                    # Calculate x_dist and y_dist (dummy values here)
                    mem_layer.changeAttributeValue(feature.id(), idx_x_dist, 0.0)
                    mem_layer.changeAttributeValue(feature.id(), idx_y_dist, 0.0)
                else:
                    new_feature = QgsFeature()
                    new_feature.setGeometry(feature.geometry())
                    new_feature.setAttributes(feature.attributes())
                    lower_layer_data.addFeature(new_feature)

                    # Calculate z_height, x_dist, and y_dist for lower layer
                    z_height_lower = value - user_input  # Ensure z_height_lower is negative
                    lower_layer.changeAttributeValue(new_feature.id(), idx_z_height_lower, z_height_lower)
                    lower_layer.changeAttributeValue(new_feature.id(), idx_x_dist_lower, 0.0)
                    lower_layer.changeAttributeValue(new_feature.id(), idx_y_dist_lower, 0.0)

            mem_layer.commitChanges()
            lower_layer.commitChanges()
            print("New fields and calculations added to memory layers.")
            
            QgsProject.instance().addMapLayer(mem_layer)
            QgsProject.instance().addMapLayer(lower_layer)

        except Exception as e:
            mem_layer.rollBack()
            lower_layer.rollBack()
            print(f"An error occurred: {e}")
    else:
        print("User input was cancelled.")