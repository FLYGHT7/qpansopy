# -*- coding: utf-8 -*-
"""
QPANSOPY Plugin for QGIS
"""
import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsCoordinateReferenceSystem, QgsCoordinateTransform

# Importar los dock widgets con manejo de errores
try:
    from .qpansopy_vss_dockwidget import QPANSOPYVSSDockWidget
    from .qpansopy_ils_dockwidget import QPANSOPYILSDockWidget
    from .qpansopy_wind_spiral_dockwidget import QPANSOPYWindSpiralDockWidget
    from .qpansopy_oas_ils_dockwidget import QPANSOPYOASILSDockWidget
    from .settings_dialog import SettingsDialog  # Importar el diálogo de configuración
except ImportError as e:
    # No lanzamos el error aquí, lo manejaremos en initGui
    pass

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
        self.oas_ils_dock = None
        
        # Initialize toolbars to None
        self.toolbars = {
            'CONV': None,
            'ILS': None,
            'PBN': None,
            'UTILITIES': None
        }
        
        # Verificar que exista la carpeta de iconos
        self.icons_dir = os.path.join(self.plugin_dir, 'icons')
        if not os.path.exists(self.icons_dir):
            try:
                os.makedirs(self.icons_dir)
            except Exception:
                # Si no podemos crear la carpeta, usaremos iconos por defecto
                pass

        # Initialize settings
        self.settings = QSettings()
        self.settings_values = {
            "enable_kml": self.settings.value("qpansopy/enable_kml", False, type=bool),
            "show_log": self.settings.value("qpansopy/show_log", True, type=bool)
        }

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        try:
            # Verificar que los módulos necesarios estén disponibles
            if 'QPANSOPYVSSDockWidget' not in globals():
                QMessageBox.warning(self.iface.mainWindow(), "QPANSOPY Warning", 
                                   "Some modules could not be imported. The plugin may not work correctly.")
            
            # Crear el menú QPANSOPY
            menuBar = self.iface.mainWindow().menuBar()
            self.menu = QMenu("QPANSOPY", self.iface.mainWindow())
            menuBar.addMenu(self.menu)
            
            # Crear las barras de herramientas temáticas
            self.toolbars['CONV'] = self.iface.addToolBar("QPANSOPY - CONV")
            self.toolbars['CONV'].setObjectName("QPANSOPYCONVToolBar")
            
            self.toolbars['ILS'] = self.iface.addToolBar("QPANSOPY - ILS")
            self.toolbars['ILS'].setObjectName("QPANSOPYILSToolBar")
            
            self.toolbars['PBN'] = self.iface.addToolBar("QPANSOPY - PBN")
            self.toolbars['PBN'].setObjectName("QPANSOPYPBNToolBar")
            
            self.toolbars['UTILITIES'] = self.iface.addToolBar("QPANSOPY - UTILITIES")
            self.toolbars['UTILITIES'].setObjectName("QPANSOPYUTILITIESToolBar")
            
            # Crear submenús para cada categoría
            self.conv_menu = QMenu("CONV", self.menu)
            self.ils_menu = QMenu("ILS", self.menu)
            self.pbn_menu = QMenu("PBN", self.menu)
            self.utilities_menu = QMenu("UTILITIES", self.menu)
            
            # Añadir submenús al menú principal
            self.menu.addMenu(self.conv_menu)
            self.menu.addMenu(self.ils_menu)
            self.menu.addMenu(self.pbn_menu)
            self.menu.addMenu(self.utilities_menu)
            
            # Crear acción para la herramienta VSS (en UTILITIES)
            vss_icon_path = os.path.join(self.icons_dir, 'vss_icon.png')
            if os.path.exists(vss_icon_path):
                vss_action = QAction(QIcon(vss_icon_path), "VSS Tool", self.iface.mainWindow())
            else:
                # Usar un icono por defecto si no existe el personalizado
                vss_action = QAction(QIcon(":/images/themes/default/mActionAddRasterLayer.svg"), "VSS Tool", self.iface.mainWindow())
            
            vss_action.setToolTip("Visual Segment Surface Tool - Analyze obstacle clearance for visual segments")
            vss_action.triggered.connect(self.toggle_vss_dock)
            self.utilities_menu.addAction(vss_action)
            self.toolbars['UTILITIES'].addAction(vss_action)
            self.actions.append(vss_action)
            
            # Crear acción para la herramienta ILS (en ILS)
            ils_icon_path = os.path.join(self.icons_dir, 'ils_icon.png')
            if os.path.exists(ils_icon_path):
                ils_action = QAction(QIcon(ils_icon_path), "Basic ILS Tool", self.iface.mainWindow())
            else:
                ils_action = QAction(QIcon(":/images/themes/default/mActionAddOgrLayer.svg"), "Basic ILS Tool", self.iface.mainWindow())
            
            ils_action.setToolTip("Basic ILS Tool - Create standard ILS surfaces")
            ils_action.triggered.connect(self.toggle_ils_dock)
            self.ils_menu.addAction(ils_action)
            self.toolbars['ILS'].addAction(ils_action)
            self.actions.append(ils_action)
            
            # Crear acción para la herramienta Wind Spiral (en UTILITIES)
            wind_spiral_icon_path = os.path.join(self.icons_dir, 'wind_spiral.png')
            if os.path.exists(wind_spiral_icon_path):
                wind_spiral_action = QAction(QIcon(wind_spiral_icon_path), "Wind Spiral Tool", self.iface.mainWindow())
            else:
                wind_spiral_action = QAction(QIcon(":/images/themes/default/mActionAddCircle.svg"), "Wind Spiral Tool", self.iface.mainWindow())
            
            wind_spiral_action.setToolTip("Wind Spiral Tool - Calculate and visualize wind spirals for procedure design")
            wind_spiral_action.triggered.connect(self.toggle_wind_spiral_dock)
            self.utilities_menu.addAction(wind_spiral_action)
            self.toolbars['UTILITIES'].addAction(wind_spiral_action)
            self.actions.append(wind_spiral_action)
            
            # Crear acción para la herramienta OAS ILS (en ILS)
            oas_ils_icon_path = os.path.join(self.icons_dir, 'oas_ils.png')
            if os.path.exists(oas_ils_icon_path):
                oas_ils_action = QAction(QIcon(oas_ils_icon_path), "OAS ILS Tool", self.iface.mainWindow())
            else:
                oas_ils_action = QAction(QIcon(":/images/themes/default/mActionAddPolygon.svg"), "OAS ILS Tool", self.iface.mainWindow())
            
            oas_ils_action.setToolTip("OAS ILS Tool - Create Obstacle Assessment Surfaces for ILS approaches")
            oas_ils_action.triggered.connect(self.toggle_oas_ils_dock)
            self.ils_menu.addAction(oas_ils_action)
            self.toolbars['ILS'].addAction(oas_ils_action)
            self.actions.append(oas_ils_action)
            
            # Añadir separadores en las barras de herramientas
            self.toolbars['ILS'].addSeparator()
            self.toolbars['UTILITIES'].addSeparator()

            # Añadir menú contextual "About" y "Settings"
            self.menu.setTearOffEnabled(True)
            self.menu.addSeparator()
            about_action = QAction("About", self.iface.mainWindow())
            about_action.triggered.connect(self.show_about_dialog)
            self.menu.addAction(about_action)
            settings_action = QAction("Settings", self.iface.mainWindow())
            settings_action.triggered.connect(self.show_settings_dialog)
            self.menu.addAction(settings_action)
            
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "QPANSOPY Error", 
                               f"Error initializing plugin: {str(e)}")

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        try:
            # Eliminar el menú
            if self.menu:
                menuBar = self.iface.mainWindow().menuBar()
                menuBar.removeAction(self.menu.menuAction())
            
            # Eliminar barras de herramientas
            for toolbar_name, toolbar in self.toolbars.items():
                if toolbar:
                    self.iface.mainWindow().removeToolBar(toolbar)
                    toolbar.deleteLater()
            
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
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "QPANSOPY Error", 
                               f"Error unloading plugin: {str(e)}")

    def toggle_vss_dock(self):
        """Toggle the VSS dock widget"""
        try:
            if self.vss_dock is None:
                # Create the dock widget
                self.vss_dock = QPANSOPYVSSDockWidget(self.iface)
                # Aplicar configuración
                self.vss_dock.exportKmlCheckBox.setChecked(self.settings.value("qpansopy/enable_kml", False, type=bool))
                if hasattr(self.vss_dock, "logTextEdit"):
                    self.vss_dock.logTextEdit.setVisible(self.settings.value("qpansopy/show_log", True, type=bool))
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
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "QPANSOPY Error", 
                               f"Error toggling VSS dock: {str(e)}")
    
    def toggle_ils_dock(self):
        """Toggle the ILS dock widget"""
        try:
            if self.ils_dock is None:
                # Create the dock widget
                self.ils_dock = QPANSOPYILSDockWidget(self.iface)
                # Aplicar configuración
                self.ils_dock.exportKmlCheckBox.setChecked(self.settings.value("qpansopy/enable_kml", False, type=bool))
                if hasattr(self.ils_dock, "logTextEdit"):
                    self.ils_dock.logTextEdit.setVisible(self.settings.value("qpansopy/show_log", True, type=bool))
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
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "QPANSOPY Error", 
                               f"Error toggling ILS dock: {str(e)}")
    
    def toggle_wind_spiral_dock(self):
        """Toggle the Wind Spiral dock widget"""
        try:
            if self.wind_spiral_dock is None:
                # Create the dock widget
                self.wind_spiral_dock = QPANSOPYWindSpiralDockWidget(self.iface)
                # Aplicar configuración
                self.wind_spiral_dock.exportKmlCheckBox.setChecked(self.settings.value("qpansopy/enable_kml", False, type=bool))
                if hasattr(self.wind_spiral_dock, "logTextEdit"):
                    self.wind_spiral_dock.logTextEdit.setVisible(self.settings.value("qpansopy/show_log", True, type=bool))
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
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "QPANSOPY Error", 
                               f"Error toggling Wind Spiral dock: {str(e)}")
    
    def toggle_oas_ils_dock(self):
        """Toggle the OAS ILS dock widget"""
        try:
            if self.oas_ils_dock is None:
                # Create the dock widget
                self.oas_ils_dock = QPANSOPYOASILSDockWidget(self.iface)
                # Aplicar configuración
                self.oas_ils_dock.exportKmlCheckBox.setChecked(self.settings.value("qpansopy/enable_kml", False, type=bool))
                if hasattr(self.oas_ils_dock, "logTextEdit"):
                    self.oas_ils_dock.logTextEdit.setVisible(self.settings.value("qpansopy/show_log", True, type=bool))
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
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "QPANSOPY Error", 
                               f"Error toggling OAS ILS dock: {str(e)}")
    
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

    def show_about_dialog(self):
        """Show the About dialog"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout
        from PyQt5.QtGui import QPixmap
        dlg = QDialog()
        dlg.setWindowTitle("About QPANSOPY")
        layout = QVBoxLayout(dlg)
        hbox = QHBoxLayout()
        logo_path = os.path.join(self.plugin_dir, "icons", "flyght7_logo.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            logo = QLabel()
            logo.setPixmap(pix.scaledToHeight(48))
            hbox.addWidget(logo)
        hbox.addWidget(QLabel("<b>QPANSOPY by FLYGHT7</b>"))
        layout.addLayout(hbox)
        github_label = QLabel("Aviation surfaces plugin for QGIS.<br>Developed by FLYGHT7.<br><a href='https://github.com/FLYGHT7/qpansopy'>https://github.com/FLYGHT7/qpansopy</a>")
        github_label.setOpenExternalLinks(True)
        layout.addWidget(github_label)
        dlg.exec_()

    def show_settings_dialog(self):
        """Show the Settings dialog"""
        # Usar None como parent para evitar errores de QWidget
        dlg = SettingsDialog(None, self.settings)
        if dlg.exec_():
            vals = dlg.get_values()
            self.settings.setValue("qpansopy/enable_kml", vals["enable_kml"])
            self.settings.setValue("qpansopy/show_log", vals["show_log"])
            self.settings_values = vals