# Este archivo es un reemplazo para el diálogo de extracción que ya no es necesario
# Ya que la funcionalidad ahora se ejecuta directamente desde el dockwidget

from qgis.PyQt.QtWidgets import QDialog

class ObjectExtractionDialog(QDialog):
    """
    Clase simulacro que no hace nada, para compatibilidad con código existente
    """
    def __init__(self, iface=None, point_layer=None, surface_layer=None):
        pass
        
    def exec_(self):
        # No hacer nada, simplemente regresar como si el diálogo hubiera sido cancelado
        return False
