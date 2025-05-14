# -*- coding: utf-8 -*-
"""
QPANSOPY Plugin for QGIS
"""
import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsCoordinateReferenceSystem, QgsCoordinateTransform

# Import the dock widgets
from .qpansopy_vss_dockwidget import QPANSOPYVSSDockWidget
from .qpansopy_ils_dockwidget import QPANSOPYILSDockWidget
from .qpansopy_wind_spiral_dockwidget import QPANSOPYWindSpiralDockWidget
from .qpansopy_oas_ils_dockwidget import QPANSOPYOASILSDockWidget

class Qpansopy:
    """QPANSOPY Plugin Implementation"""

    def __init__(self, iface):
        """Constructor.
        
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        
        # Create actions
        self.actions = []
        self.menu = None  # Será inicializado en initGui
        
        # Initialize dock widgets to None
        self.vss_dock = None
        self.ils_dock = None
        self.wind_spiral_dock = None
        self.oas_ils_dock = None  # Añadir nuevo dock widget para OAS ILS

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        
        # Crear el menú QPANSOPY antes del menú de Ayuda
        menuBar = self.iface.mainWindow().menuBar()
        helpMenu = None
        
        # Buscar el menú de Ayuda
        for action in menuBar.actions():
            if action.text() == "Help" or action.text() == "Ayuda":
                helpMenu = action
                break
        
        # Crear nuestro menú
        self.menu = QMenu("QPANSOPY", self.iface.mainWindow())
        
        # Insertar antes del menú de Ayuda si se encuentra, de lo contrario añadir al final
        if helpMenu:
            menuBar.insertMenu(helpMenu, self.menu)
        else:
            menuBar.addMenu(self.menu)
        
        # Crear acción para la herramienta VSS
        vss_action = QAction(
            QIcon(os.path.join(self.plugin_dir, 'icons', 'vss_icon.png')),
            "QPANSOPY VSS Tool", 
            self.iface.mainWindow())
        vss_action.triggered.connect(self.toggle_vss_dock)
        self.menu.addAction(vss_action)
        self.iface.addToolBarIcon(vss_action)
        self.actions.append(vss_action)
        
        # Crear acción para la herramienta ILS
        ils_action = QAction(
            QIcon(os.path.join(self.plugin_dir, 'icons', 'ils_icon.png')),
            "QPANSOPY ILS Tool", 
            self.iface.mainWindow())
        ils_action.triggered.connect(self.toggle_ils_dock)
        self.menu.addAction(ils_action)
        self.iface.addToolBarIcon(ils_action)
        self.actions.append(ils_action)
        
        # Crear acción para la herramienta Wind Spiral
        wind_spiral_action = QAction(
            QIcon(os.path.join(self.plugin_dir, 'icons', 'wind_spiral.png')),
            "QPANSOPY Wind Spiral Tool", 
            self.iface.mainWindow())
        wind_spiral_action.triggered.connect(self.toggle_wind_spiral_dock)
        self.menu.addAction(wind_spiral_action)
        self.iface.addToolBarIcon(wind_spiral_action)
        self.actions.append(wind_spiral_action)
        
        # Crear acción para la herramienta OAS ILS
        oas_ils_action = QAction(
            QIcon(os.path.join(self.plugin_dir, 'icons', 'oas_ils.png')),
            "QPANSOPY OAS ILS Tool", 
            self.iface.mainWindow())
        oas_ils_action.triggered.connect(self.toggle_oas_ils_dock)
        self.menu.addAction(oas_ils_action)
        self.iface.addToolBarIcon(oas_ils_action)
        self.actions.append(oas_ils_action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        # Eliminar el menú
        if self.menu:
            menuBar = self.iface.mainWindow().menuBar()
            menuBar.removeAction(self.menu.menuAction())
        
        # Eliminar iconos de la barra de herramientas
        for action in self.actions:
            self.iface.removeToolBarIcon(action)
        
        # Cerrar widgets si existen
        if self.vss_dock:
            self.iface.removeDockWidget(self.vss_dock)
            self.vss_dock = None
            
        if self.ils_dock:
            self.iface.removeDockWidget(self.ils_dock)
            self.ils_dock = None
            
        if self.wind_spiral_dock:
            self.iface.removeDockWidget(self.wind_spiral_dock)
            self.wind_spiral_dock = None
            
        if self.oas_ils_dock:
            self.iface.removeDockWidget(self.oas_ils_dock)
            self.oas_ils_dock = None

    def toggle_vss_dock(self):
        """Toggle the VSS dock widget"""
        if self.vss_dock is None:
            # Create the dock widget
            self.vss_dock = QPANSOPYVSSDockWidget(self.iface)
            # Connect the closing signal
            self.vss_dock.closingPlugin.connect(self.on_vss_dock_closed)
            # Add the dock widget to the interface
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.vss_dock)
            
            # Close other docks if they're open
            if self.ils_dock:
                self.iface.removeDockWidget(self.ils_dock)
                self.ils_dock = None
                
            if self.wind_spiral_dock:
                self.iface.removeDockWidget(self.wind_spiral_dock)
                self.wind_spiral_dock = None
                
            if self.oas_ils_dock:
                self.iface.removeDockWidget(self.oas_ils_dock)
                self.oas_ils_dock = None
        else:
            # If the dock widget exists, remove it
            self.iface.removeDockWidget(self.vss_dock)
            self.vss_dock = None
    
    def toggle_ils_dock(self):
        """Toggle the ILS dock widget"""
        if self.ils_dock is None:
            # Create the dock widget
            self.ils_dock = QPANSOPYILSDockWidget(self.iface)
            # Connect the closing signal
            self.ils_dock.closingPlugin.connect(self.on_ils_dock_closed)
            # Add the dock widget to the interface
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.ils_dock)
            
            # Close other docks if they're open
            if self.vss_dock:
                self.iface.removeDockWidget(self.vss_dock)
                self.vss_dock = None
                
            if self.wind_spiral_dock:
                self.iface.removeDockWidget(self.wind_spiral_dock)
                self.wind_spiral_dock = None
                
            if self.oas_ils_dock:
                self.iface.removeDockWidget(self.oas_ils_dock)
                self.oas_ils_dock = None
        else:
            # If the dock widget exists, remove it
            self.iface.removeDockWidget(self.ils_dock)
            self.ils_dock = None
    
    def toggle_wind_spiral_dock(self):
        """Toggle the Wind Spiral dock widget"""
        if self.wind_spiral_dock is None:
            # Create the dock widget
            self.wind_spiral_dock = QPANSOPYWindSpiralDockWidget(self.iface)
            # Connect the closing signal
            self.wind_spiral_dock.closingPlugin.connect(self.on_wind_spiral_dock_closed)
            # Add the dock widget to the interface
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.wind_spiral_dock)
            
            # Close other docks if they're open
            if self.vss_dock:
                self.iface.removeDockWidget(self.vss_dock)
                self.vss_dock = None
                
            if self.ils_dock:
                self.iface.removeDockWidget(self.ils_dock)
                self.ils_dock = None
                
            if self.oas_ils_dock:
                self.iface.removeDockWidget(self.oas_ils_dock)
                self.oas_ils_dock = None
        else:
            # If the dock widget exists, remove it
            self.iface.removeDockWidget(self.wind_spiral_dock)
            self.wind_spiral_dock = None
    
    def toggle_oas_ils_dock(self):
        """Toggle the OAS ILS dock widget"""
        if self.oas_ils_dock is None:
            # Create the dock widget
            self.oas_ils_dock = QPANSOPYOASILSDockWidget(self.iface)
            # Connect the closing signal
            self.oas_ils_dock.closingPlugin.connect(self.on_oas_ils_dock_closed)
            # Add the dock widget to the interface
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.oas_ils_dock)
            
            # Close other docks if they're open
            if self.vss_dock:
                self.iface.removeDockWidget(self.vss_dock)
                self.vss_dock = None
                
            if self.ils_dock:
                self.iface.removeDockWidget(self.ils_dock)
                self.ils_dock = None
                
            if self.wind_spiral_dock:
                self.iface.removeDockWidget(self.wind_spiral_dock)
                self.wind_spiral_dock = None
        else:
            # If the dock widget exists, remove it
            self.iface.removeDockWidget(self.oas_ils_dock)
            self.oas_ils_dock = None
    
    def on_vss_dock_closed(self):
        """Handle VSS dock widget closing"""
        self.vss_dock = None
    
    def on_ils_dock_closed(self):
        """Handle ILS dock widget closing"""
        self.ils_dock = None
        
    def on_wind_spiral_dock_closed(self):
        """Handle Wind Spiral dock widget closing"""
        self.wind_spiral_dock = None
        
    def on_oas_ils_dock_closed(self):
        """Handle OAS ILS dock widget closing"""
        self.oas_ils_dock = None