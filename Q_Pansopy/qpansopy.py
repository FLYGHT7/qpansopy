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
        self.menu = "QPANSOPY"
        
        # Initialize dock widgets to None
        self.vss_dock = None
        self.ils_dock = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar."""

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Añadir a la barra de herramientas principal de QGIS
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        
        # Create action for VSS tool
        self.add_action(
            os.path.join(self.plugin_dir, 'icons', 'vss_icon.png'),
            text="QPANSOPY VSS Tool",
            callback=self.toggle_vss_dock,
            parent=self.iface.mainWindow())
            
        # Create action for ILS tool
        self.add_action(
            os.path.join(self.plugin_dir, 'icons', 'ils_icon.png'),
            text="QPANSOPY ILS Tool",
            callback=self.toggle_ils_dock,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                "QPANSOPY",
                action)
            self.iface.removeToolBarIcon(action)
        
        # Close dock widgets if they exist
        if self.vss_dock:
            self.iface.removeDockWidget(self.vss_dock)
            self.vss_dock = None
            
        if self.ils_dock:
            self.iface.removeDockWidget(self.ils_dock)
            self.ils_dock = None

    def toggle_vss_dock(self):
        """Toggle the VSS dock widget"""
        if self.vss_dock is None:
            # Create the dock widget
            self.vss_dock = QPANSOPYVSSDockWidget(self.iface)
            # Connect the closing signal
            self.vss_dock.closingPlugin.connect(self.on_vss_dock_closed)
            # Add the dock widget to the interface
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.vss_dock)
            
            # Close ILS dock if it's open
            if self.ils_dock:
                self.iface.removeDockWidget(self.ils_dock)
                self.ils_dock = None
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
            
            # Close VSS dock if it's open
            if self.vss_dock:
                self.iface.removeDockWidget(self.vss_dock)
                self.vss_dock = None
        else:
            # If the dock widget exists, remove it
            self.iface.removeDockWidget(self.ils_dock)
            self.ils_dock = None
    
    def on_vss_dock_closed(self):
        """Handle VSS dock widget closing"""
        self.vss_dock = None
    
    def on_ils_dock_closed(self):
        """Handle ILS dock widget closing"""
        self.ils_dock = None