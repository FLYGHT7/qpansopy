# -*- coding: utf-8 -*-
"""
QPANSOPY Plugin for QGIS
"""
import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox, QSizePolicy
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsApplication


# Importar los dock widgets con manejo de errores
try:
    # Import dock widgets from new organized structure
    from .dockwidgets.utilities.qpansopy_vss_dockwidget import QPANSOPYVSSDockWidget
    from .dockwidgets.ils.qpansopy_ils_dockwidget import QPANSOPYILSDockWidget
    from .dockwidgets.utilities.qpansopy_wind_spiral_dockwidget import QPANSOPYWindSpiralDockWidget
    from .dockwidgets.ils.qpansopy_oas_ils_dockwidget import QPANSOPYOASILSDockWidget
    from .dockwidgets.utilities.qpansopy_object_selection_dockwidget import QPANSOPYObjectSelectionDockWidget
    from .dockwidgets.utilities.qpansopy_point_filter_dockwidget import QPANSOPYPointFilterDockWidget
    from .dockwidgets.utilities.qpansopy_feature_merge_dockwidget import QPANSOPYFeatureMergeDockWidget
    from .dockwidgets.pbn.qpansopy_lnav_dockwidget import QPANSOPYLNAVDockWidget
    from .dockwidgets.pbn.qpansopy_gnss_waypoint_dockwidget import QPANSOPYGNSSWaypointDockWidget
    from .dockwidgets.conv.qpansopy_vor_dockwidget import QPANSOPYVORDockWidget
    from .dockwidgets.conv.qpansopy_ndb_dockwidget import QPANSOPYNDBDockWidget
    from .dockwidgets.conv.qpansopy_conv_initial_dockwidget import QPANSOPYCONVInitialDockWidget
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
                                   "Some modules could not be imported. The plugin may not work correctly.")            #Configure Modules NAME:PROPERTIES (STR:DICT)
            self.modules:dict = {"VSS": {"TITLE":"VSS Tool","TOOLBAR":"UTILITIES","TOOLTIP":"Visual Segment Surface Tool - Analyze obstacle clearance for visual segments","ICON":"vss.svg","DOCK_WIDGET": QPANSOPYVSSDockWidget,"GUI_INSTANCE":None},
                                "ILS_BASIC": {"TITLE":"ILS Tool","TOOLBAR":"ILS","TOOLTIP":"ILS Basic Surface Tool","ICON":"basic_ils.svg","DOCK_WIDGET": QPANSOPYILSDockWidget,"GUI_INSTANCE":None},
                                "WindSpiral": {"TITLE":"Wind Spiral Tool","TOOLBAR":"UTILITIES","TOOLTIP":"Wind Spiral Tool - Calculate and visualize wind spirals for procedure design","ICON":"wind_spiral.svg","DOCK_WIDGET": QPANSOPYWindSpiralDockWidget,"GUI_INSTANCE":None},
                                "ILS_OAS": {"TITLE":"OAS ILS Tool","TOOLBAR":"ILS","TOOLTIP":"Visual Segment Surface Tool - Analyze obstacle clearance for visual segments","ICON":"oas_ils.svg","DOCK_WIDGET": QPANSOPYOASILSDockWidget,"GUI_INSTANCE":None},
                                "LNAV_APCH": {
                                    "TITLE": "LNAV",
                                    "TOOLBAR": "PBN",
                                    "TOOLTIP": "LNAV Initial, Intermediate, Final and Missed Approach Tool",
                                    "ICON": os.path.join(self.icons_dir, 'PBN.png'),
                                    "DOCK_WIDGET": QPANSOPYLNAVDockWidget,
                                    "GUI_INSTANCE": None
                                },
                                "GNSS_WAYPOINT": {
                                    "TITLE": "GNSS Waypoint",
                                    "TOOLBAR": "PBN",
                                    "TOOLTIP": "GNSS Waypoint Tolerance Tool - Create fix tolerance polygons",
                                    "ICON": os.path.join(self.icons_dir, 'gnss_waypoint.svg'),
                                    "DOCK_WIDGET": QPANSOPYGNSSWaypointDockWidget,
                                    "GUI_INSTANCE": None
                                },
                                "VOR_CONV": {
                                    "TITLE": "VOR",
                                    "TOOLBAR": "CONV",
                                    "TOOLTIP": "VOR Conventional Approach Areas Tool",
                                    "ICON": os.path.join(self.icons_dir, 'vor.svg'),
                                    "DOCK_WIDGET": QPANSOPYVORDockWidget,
                                    "GUI_INSTANCE": None
                                },
                                "NDB_CONV": {
                                    "TITLE": "NDB",
                                    "TOOLBAR": "CONV",
                                    "TOOLTIP": "NDB Conventional Approach Areas Tool",
                                    "ICON": os.path.join(self.icons_dir, 'ndb.svg'),
                                    "DOCK_WIDGET": QPANSOPYNDBDockWidget,
                                    "GUI_INSTANCE": None
                                },
                                "CONV_INITIAL": {
                                    "TITLE": "CONV Initial",
                                    "TOOLBAR": "CONV",
                                    "TOOLTIP": "CONV Initial Approach Straight Areas Tool",
                                    "ICON": os.path.join(self.icons_dir, 'conv_corridor.svg'),
                                    "DOCK_WIDGET": QPANSOPYCONVInitialDockWidget,
                                    "GUI_INSTANCE": None
                                },
                                "ObjectSelection": {
                                    "TITLE": "Object Selection",
                                    "TOOLBAR": "UTILITIES",
                                    "TOOLTIP": "Extract objects intersecting with surfaces",
                                    "ICON": "SOO.png",  # Using the SOO icon
                                    "DOCK_WIDGET": QPANSOPYObjectSelectionDockWidget,
                                    "GUI_INSTANCE": None
                                },
                                "PointFilter": {
                                    "TITLE": "Point Filter",
                                    "TOOLBAR": "UTILITIES",
                                    "TOOLTIP": "Filter points based on THR elevation threshold",
                                    "ICON": "point_filter.svg",  # Using the F icon
                                    "DOCK_WIDGET": QPANSOPYPointFilterDockWidget,
                                    "GUI_INSTANCE": None
                                },
                                "FeatureMerge": {
                                    "TITLE": "Feature Merge",
                                    "TOOLBAR": "UTILITIES",
                                    "TOOLTIP": "Merge multiple vector layers into a single layer",
                                    "ICON": "feature_merge.svg",  # Using the lightning bolt icon
                                    "DOCK_WIDGET": QPANSOPYFeatureMergeDockWidget,
                                    "GUI_INSTANCE": None
                                }}
            
            ##If you do not want empty submenus to be displayed self.submenus can be left as an empty dictionary
            #self.submenus:dict = {}
            self.submenus:dict = {"CONV":None,"ILS":None,"PBN":None,"UTILITIES":None}
            
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
    
            #Initilise the Submenus
            if self.submenus is not None:
                for category in self.submenus.keys():
                    self.submenus[category] =  QMenu(category, self.menu)
                    self.menu.addMenu(self.submenus[category])

            #Create Actions
            for name,properties in self.modules.items():
                icon_path = os.path.join(self.plugin_dir, 'icons', properties["ICON"])
                if not os.path.exists(icon_path):
                    icon_path = QgsApplication.iconPath(":missing_image.svg")
                new_action = QAction(
                QIcon(icon_path),
                properties["TITLE"], 
                self.iface.mainWindow())
                # Conectar asegurando compatibilidad con triggered(bool)
                # La ranura acepta (name, checked=False), por lo que ignoramos 'checked'
                new_action.triggered.connect(lambda checked, n=name: self.toggle_dock(n, checked))
                new_action.setToolTip(properties['TOOLTIP'])
                toolbar_name = properties['TOOLBAR']
                self.toolbars[toolbar_name].addAction(new_action)
                self.actions.append(new_action)

                #Add the tool to the menu under the correct submenu
                try:
                    #If the submenu already exists we can add the tool/action directly to it
                    menu_category = self.submenus[toolbar_name]
                except KeyError:
                    ##NOTE: is self.submenus is None, this code will only create a submenu for each Toolbar category in self.modules
                    #if it does not exist we need to first create the submenu then add that the QPANSOPY Menu
                    self.submenus[toolbar_name] = QMenu(toolbar_name, self.menu)
                    menu_category = self.submenus[toolbar_name]
                    self.menu.addMenu(menu_category)
                else:
                    ## In the event submenus is prepopulated with values, this will initilise the submenu
                    if self.submenus[toolbar_name] is None:
                        menu_category = self.submenus[toolbar_name]

                finally:
                    menu_category = self.submenus[toolbar_name]
                    #Finally we can add the action to the submenu
                    menu_category.addAction(new_action)
                

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
        # Eliminar el menú
        if self.menu:
            menuBar = self.iface.mainWindow().menuBar()
            menuBar.removeAction(self.menu.menuAction())
        
        # Eliminar barras de herramientas
        for toolbar_name, toolbar in self.toolbars.items():
            if toolbar:
                self.iface.mainWindow().removeToolBar(toolbar)
                toolbar.deleteLater()

        # Remove the actions from the Toolbar
        for name,properties in self.modules.items():
            if properties["GUI_INSTANCE"] is not None:
                self.iface.removeDockWidget(properties["GUI_INSTANCE"])
                self.modules[name]["GUI_INSTANCE"] = None


    def toggle_dock(self, name=None, checked=False):
        """Toggle the requested dock widget
        :param str name: key name from self.module for the module to toggle 
        """
        # Si name es None, simplemente retornar sin hacer nada
        if name is None:
            return
            
        instance = self.modules[name]["GUI_INSTANCE"]
        if instance is None:
            # Create and register the dock widget once; later toggles just show/hide
            dock_widget_cls = self.modules[name]["DOCK_WIDGET"]
            instance = self.modules[name]["GUI_INSTANCE"] = dock_widget_cls(self.iface)
            title = self.modules[name].get("TITLE", name)
            # Basic metadata (ignore failures silently)
            try:
                instance.setObjectName(f"QPANSOPY_{name}")
            except Exception:
                pass
            try:
                instance.setWindowTitle(f"QPANSOPY - {title}")
            except Exception:
                pass
            try:
                instance.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            except Exception:
                pass
            # Initial configuration
            try:
                instance.exportKmlCheckBox.setChecked(self.settings.value("qpansopy/enable_kml", False, type=bool))
            except AttributeError:
                QMessageBox.warning(self.iface.mainWindow(), "QPANSOPY Error", "This Widget has no KML Export Button")
            if hasattr(instance, "logTextEdit"):
                instance.logTextEdit.setVisible(self.settings.value("qpansopy/show_log", True, type=bool))
                try:
                    instance.logTextEdit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
                    if instance.logTextEdit.minimumHeight() < 80:
                        instance.logTextEdit.setMinimumHeight(80)
                except Exception:
                    pass
            instance.closingPlugin.connect(lambda: self.on_dock_closed(name))
            self.iface.addDockWidget(Qt.RightDockWidgetArea, instance)
            # Hide other docks instead of removing to reduce geometry churn
            for other_name, other_properties in self.modules.items():
                if other_name == name:
                    continue
                other_instance = other_properties["GUI_INSTANCE"]
                if other_instance and other_instance.isVisible():
                    other_instance.hide()
        else:
            # Toggle visibility of existing instance; hide siblings when showing
            if instance.isVisible():
                instance.hide()
            else:
                instance.show()
                for other_name, other_properties in self.modules.items():
                    if other_name == name:
                        continue
                    other_instance = other_properties["GUI_INSTANCE"]
                    if other_instance and other_instance.isVisible():
                        other_instance.hide()


    def on_dock_closed(self,name):
        """Handle module dock widget closing
        :param str name: key name from self.module for the module to close 
        """
        self.modules[name]["GUI_INSTANCE"] = None


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

    def create_callback(self, name):
        """Create a callback function for the given module name"""
        def callback():
            self.toggle_dock(name)
        return callback