# -*- coding: utf-8 -*-
"""
QPANSOPY Plugin for QGIS
Aviation surfaces plugin for QGIS developed by FLYGHT7
Copyright (C) 2020-2025 FLYGHT7
"""
import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox, QSizePolicy
from qgis.PyQt import QtWidgets, QtCore, sip
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
    from .dockwidgets.conv.qpansopy_vor_dockwidget import QPANSOPYVORDockWidget
    from .dockwidgets.conv.qpansopy_ndb_dockwidget import QPANSOPYNDBDockWidget
    from .dockwidgets.conv.qpansopy_conv_initial_dockwidget import QPANSOPYConvInitialDockWidget
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

        # Track a reference dock to keep geometry stable
        self.dock_anchor = None
        self.dock_anchor_name = None
        
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

        # Initialize modules dictionary
        self.modules = {}


    def initGui(self):
        try:
            # Declare available modules and their UI metadata
            self.modules = {
                "ILS": {
                    "TITLE": "ILS",
                    "TOOLBAR": "ILS",
                    "TOOLTIP": "Instrument Landing System surfaces",
                    "ICON": "ils.svg",
                    "DOCK_WIDGET": QPANSOPYILSDockWidget,
                    "GUI_INSTANCE": None,
                },
                "ILS_OAS": {
                    "TITLE": "OAS ILS Tool",
                    "TOOLBAR": "ILS",
                    "TOOLTIP": "Obstacle Assessment Surfaces for ILS",
                    "ICON": "oas_ils.svg",
                    "DOCK_WIDGET": QPANSOPYOASILSDockWidget,
                    "GUI_INSTANCE": None,
                },
                "LNAV_APCH": {
                    "TITLE": "LNAV",
                    "TOOLBAR": "PBN",
                    "TOOLTIP": "LNAV Initial, Intermediate, Final and Missed Approach Tool",
                    "ICON": os.path.join(self.icons_dir, "PBN.png"),
                    "DOCK_WIDGET": QPANSOPYLNAVDockWidget,
                    "GUI_INSTANCE": None,
                },
                "VOR_CONV": {
                    "TITLE": "VOR",
                    "TOOLBAR": "CONV",
                    "TOOLTIP": "VOR Conventional Approach Areas Tool",
                    "ICON": os.path.join(self.icons_dir, "vor.svg"),
                    "DOCK_WIDGET": QPANSOPYVORDockWidget,
                    "GUI_INSTANCE": None,
                },
                "NDB_CONV": {
                    "TITLE": "NDB",
                    "TOOLBAR": "CONV",
                    "TOOLTIP": "NDB Conventional Approach Areas Tool",
                    "ICON": os.path.join(self.icons_dir, "ndb.svg"),
                    "DOCK_WIDGET": QPANSOPYNDBDockWidget,
                    "GUI_INSTANCE": None,
                },
                "CONV_INITIAL": {
                    "TITLE": "CONV Initial",
                    "TOOLBAR": "CONV",
                    "TOOLTIP": "CONV Initial Approach Straight Areas Tool",
                    "ICON": os.path.join(self.icons_dir, "conv_corridor.svg"),
                    "DOCK_WIDGET": QPANSOPYCONVInitialDockWidget,
                    "GUI_INSTANCE": None,
                },
                "WindSpiral": {
                    "TITLE": "Wind Spiral Tool",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Calculate and visualize wind spirals",
                    "ICON": "wind_spiral.svg",
                    "DOCK_WIDGET": QPANSOPYWindSpiralDockWidget,
                    "GUI_INSTANCE": None,
                },
                "VSS": {
                    "TITLE": "VSS",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Visual Segment Surface Tool",
                    "ICON": "VSS.svg",
                    "DOCK_WIDGET": QPANSOPYVSSDockWidget,
                    "GUI_INSTANCE": None,
                },
                "ObjectSelection": {
                    "TITLE": "Object Selection",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Extract objects intersecting with surfaces",
                    "ICON": "SOO.png",
                    "DOCK_WIDGET": QPANSOPYObjectSelectionDockWidget,
                    "GUI_INSTANCE": None,
                },
                "PointFilter": {
                    "TITLE": "Point Filter",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Filter points based on THR elevation threshold",
                    "ICON": "point_filter.svg",
                    "DOCK_WIDGET": QPANSOPYPointFilterDockWidget,
                    "GUI_INSTANCE": None,
                },
                "FeatureMerge": {
                    "TITLE": "Feature Merge",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Merge multiple vector layers into a single layer",
                    "ICON": "feature_merge.svg",
                    "DOCK_WIDGET": QPANSOPYFeatureMergeDockWidget,
                    "GUI_INSTANCE": None,
                },
            }

            # If you do not want empty submenus, you can leave this empty
            self.submenus: dict = {"CONV": None, "ILS": None, "PBN": None, "UTILITIES": None}

            # Create QPANSOPY menu
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
                                    "DOCK_WIDGET": QPANSOPYConvInitialDockWidget,
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

            # Create themed toolbars
            self.toolbars['CONV'] = self.iface.addToolBar("QPANSOPY - CONV")
            self.toolbars['CONV'].setObjectName("QPANSOPYCONVToolBar")

            self.toolbars['ILS'] = self.iface.addToolBar("QPANSOPY - ILS")
            self.toolbars['ILS'].setObjectName("QPANSOPYILSToolBar")

            self.toolbars['PBN'] = self.iface.addToolBar("QPANSOPY - PBN")
            self.toolbars['PBN'].setObjectName("QPANSOPYPBNToolBar")

            self.toolbars['UTILITIES'] = self.iface.addToolBar("QPANSOPY - UTILITIES")
            self.toolbars['UTILITIES'].setObjectName("QPANSOPYUTILITIESToolBar")

            # Initialize submenus
            for category in self.submenus.keys():
                self.submenus[category] = QMenu(category, self.menu)
                self.menu.addMenu(self.submenus[category])

            # Create actions for each module
            for name, properties in self.modules.items():
                icon_path = os.path.join(self.plugin_dir, 'icons', properties["ICON"])
                if not os.path.exists(icon_path):
                    icon_path = QgsApplication.iconPath(":missing_image.svg")
                new_action = QAction(QIcon(icon_path), properties["TITLE"], self.iface.mainWindow())
                new_action.triggered.connect(lambda checked, n=name: self.toggle_dock(n, checked))
                new_action.setToolTip(properties['TOOLTIP'])
                toolbar_name = properties['TOOLBAR']
                if self.toolbars.get(toolbar_name):
                    self.toolbars[toolbar_name].addAction(new_action)
                self.actions.append(new_action)

                # Add the tool to the menu under the correct submenu
                if self.submenus.get(toolbar_name) is None:
                    self.submenus[toolbar_name] = QMenu(toolbar_name, self.menu)
                    self.menu.addMenu(self.submenus[toolbar_name])
                self.submenus[toolbar_name].addAction(new_action)

            # Add separators in toolbars
            self.toolbars['ILS'].addSeparator()
            self.toolbars['UTILITIES'].addSeparator()

            # Add About and Settings entries
            self.menu.setTearOffEnabled(True)
            self.menu.addSeparator()
            about_action = QAction("About", self.iface.mainWindow())
            about_action.triggered.connect(self.show_about_dialog)
            self.menu.addAction(about_action)
            settings_action = QAction("Settings", self.iface.mainWindow())
            settings_action.triggered.connect(self.show_settings_dialog)
            self.menu.addAction(settings_action)

        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "QPANSOPY Error", f"Error initializing plugin: {str(e)}")


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
        if hasattr(self, 'modules') and self.modules:
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
                # Ensure the log panel is actually resizable regardless of UI max heights
                try:
                    self._ensure_resizable_log(instance)
                except Exception:
                    pass
            instance.closingPlugin.connect(lambda: self.on_dock_closed(name))
            self.iface.addDockWidget(Qt.RightDockWidgetArea, instance)
            self._ensure_dock_anchor(name, instance)
            instance.show()
            instance.raise_()
            self._hide_other_docks(name)
        else:
            # Toggle visibility of existing instance; hide siblings when showing
            if instance.isVisible():
                instance.hide()
            else:
                self._ensure_dock_anchor(name, instance)
                instance.show()
                instance.raise_()
                self._hide_other_docks(name)

    def _ensure_resizable_log(self, dock_instance):
        """Make only the log box resizable (Option A).
        Adds a thin handle under the log that adjusts its height without affecting
        the other containers. The dock may grow/shrink to accommodate the change.
        """
        log_widget = getattr(dock_instance, "logTextEdit", None)
        if log_widget is None:
            # Try to find by name in case attribute binding differs
            log_widget = dock_instance.findChild(QtWidgets.QTextEdit, "logTextEdit") or \
                         dock_instance.findChild(QtWidgets.QPlainTextEdit, "logTextEdit")
        if not log_widget:
            return

        # Clear restrictive max sizes and set growth-friendly policies
        try:
            log_widget.setMaximumHeight(16777215)
            # We'll control height explicitly via a handle (Fixed vertical policy)
            log_widget.setMinimumHeight(max(60, log_widget.minimumHeight()))
            log_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # Ensure horizontal content never forces wider than the dock
            try:
                log_widget.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
            except Exception:
                pass
            try:
                # Only import when available in QGIS' Qt shim
                from qgis.PyQt import QtGui as _QtGui  # type: ignore
                log_widget.setWordWrapMode(_QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
            except Exception:
                pass
            try:
                log_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                log_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            except Exception:
                pass
        except Exception:
            pass

        # If enclosed in a group box with a capped max height, clear it too
        try:
            parent = log_widget.parentWidget()
            while parent is not None and not isinstance(parent, QtWidgets.QGroupBox):
                parent = parent.parentWidget()
            if isinstance(parent, QtWidgets.QGroupBox):
                parent.setMaximumHeight(16777215)
                parent.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        except Exception:
            pass

        # Avoid forcing stretch so default stays compact; only relax form layout growth
        try:
            layout = log_widget.parentWidget().layout() or dock_instance.layout()
            if isinstance(layout, QtWidgets.QFormLayout):
                layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        except Exception:
            pass

        # Option A: ensure no leftover splitter from an older instance
        try:
            if getattr(dock_instance, "_qpansopy_hasSplitter", False):
                splitter = getattr(dock_instance, "_qpansopy_logSplitter", None)
                if splitter is not None:
                    root = splitter.parentWidget()
                    root_layout = root.layout() if root else None
                    # Expect two widgets: top_container and log_group
                    try:
                        top_container = splitter.widget(0)
                        log_group = splitter.widget(1)
                    except Exception:
                        top_container = None
                        log_group = None
                    if root_layout and top_container and log_group:
                        # Extract children from top_container back into root_layout
                        tl = top_container.layout()
                        if tl is not None:
                            while tl.count():
                                item = tl.takeAt(0)
                                w = item.widget()
                                if w:
                                    root_layout.addWidget(w)
                        # Add log group back
                        root_layout.addWidget(log_group)
                        splitter.setParent(None)
                        splitter.deleteLater()
                        try:
                            top_container.setParent(None)
                            top_container.deleteLater()
                        except Exception:
                            pass
                dock_instance._qpansopy_hasSplitter = False
                dock_instance._qpansopy_logSplitter = None
        except Exception:
            pass

        # Build an internal resize handle that only changes the log height
        try:
            # Find the log group box
            log_group = None
            parent = log_widget.parentWidget()
            while parent is not None and not isinstance(parent, QtWidgets.QGroupBox):
                parent = parent.parentWidget()
            if isinstance(parent, QtWidgets.QGroupBox):
                log_group = parent
            else:
                log_group = log_widget.parentWidget()

            if not log_group or not log_group.layout():
                return
            lg_layout = log_group.layout()

            # Remove expanding spacers and reset stretches so the group hugs content
            try:
                for i in reversed(range(lg_layout.count())):
                    it = lg_layout.itemAt(i)
                    if it is not None and it.spacerItem() is not None:
                        lg_layout.takeAt(i)
                for i in range(lg_layout.count()):
                    try:
                        lg_layout.setStretch(i, 0)
                    except Exception:
                        pass
                # Prefer top alignment for contained widgets
                try:
                    lg_layout.setAlignment(Qt.AlignTop)
                except Exception:
                    pass
            except Exception:
                pass

            # Ensure default compact size via fixed height (user can adjust with handle)
            min_h = 60
            default_h = 80
            max_h = 260
            log_widget.setMinimumHeight(min_h)
            log_widget.setMaximumHeight(max_h)
            log_widget.setFixedHeight(default_h)
            # Prevent the log group from expanding vertically; keep it tight to content
            try:
                log_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            except Exception:
                pass

            # Add a thin handle below the log editor if not already
            handle = getattr(log_group, "_qpansopy_logHandle", None)
            if handle is None:
                handle = QtWidgets.QFrame(log_group)
                handle.setObjectName("qpansopyLogResizeHandle")
                handle.setFrameShape(QtWidgets.QFrame.NoFrame)
                handle.setFixedHeight(6)
                handle.setCursor(Qt.SizeVerCursor)
                handle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                # subtle visual cue
                handle.setStyleSheet("QFrame#qpansopyLogResizeHandle { background: rgba(0,0,0,0.08); border-radius: 2px; }")
                lg_layout.addWidget(handle)

                class _HandleFilter(QtCore.QObject):
                    def __init__(self, target, min_h, max_h):
                        super().__init__()
                        self._target = target
                        self._press_pos = None
                        self._start_h = None
                        self._min = min_h
                        self._max = max_h
                    def eventFilter(self, obj, event):
                        et = event.type()
                        if et == QtCore.QEvent.MouseButtonPress and (event.button() == Qt.LeftButton):
                            self._press_pos = event.globalPos()
                            self._start_h = self._target.height()
                            return True
                        if et == QtCore.QEvent.MouseMove and self._press_pos is not None:
                            dy = event.globalPos().y() - self._press_pos.y()
                            nh = max(self._min, min(self._max, self._start_h + dy))
                            self._target.setFixedHeight(nh)
                            try:
                                # Ask layouts to recompute sizes so group doesn't leave gray gaps
                                log_group.adjustSize()
                                log_group.updateGeometry()
                            except Exception:
                                pass
                            return True
                        if et == QtCore.QEvent.MouseButtonRelease:
                            self._press_pos = None
                            self._start_h = None
                            return True
                        return False

                hf = _HandleFilter(log_widget, min_h, max_h)
                handle.installEventFilter(hf)
                # keep references to avoid GC
                log_group._qpansopy_logHandle = handle
                log_group._qpansopy_logHandleFilter = hf
            
            # Additionally compact the entire dock layout to remove big gray gaps
            try:
                root_widget = None
                try:
                    root_widget = dock_instance.widget()
                except Exception:
                    root_widget = dock_instance
                root_layout = root_widget.layout() if root_widget else None

                def _strip_spacers(layout):
                    if not isinstance(layout, QtWidgets.QLayout):
                        return
                    for i in reversed(range(layout.count())):
                        it = layout.itemAt(i)
                        if it is None:
                            continue
                        if it.spacerItem() is not None:
                            layout.takeAt(i)
                            continue
                        cl = it.layout()
                        if cl is not None:
                            _strip_spacers(cl)
                    # reset stretch and align top
                    try:
                        for j in range(layout.count()):
                            layout.setStretch(j, 0)
                        layout.setAlignment(Qt.AlignTop)
                    except Exception:
                        pass

                if root_layout:
                    _strip_spacers(root_layout)
                    try:
                        root_layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
                    except Exception:
                        pass

                # Ensure every group box hugs its content (no vertical expansion)
                for gb in root_widget.findChildren(QtWidgets.QGroupBox):
                    try:
                        gb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                    except Exception:
                        pass

                try:
                    root_widget.adjustSize()
                    root_widget.updateGeometry()
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass


    def on_dock_closed(self,name):
        """Handle module dock widget closing
        :param str name: key name from self.module for the module to close 
        """
        self.modules[name]["GUI_INSTANCE"] = None
        if self.dock_anchor_name == name:
            self._promote_anchor()


    def _hide_other_docks(self, active_name):
        for other_name, other_properties in self.modules.items():
            if other_name == active_name:
                continue
            other_instance = other_properties["GUI_INSTANCE"]
            if other_instance and other_instance.isVisible():
                other_instance.hide()


    def _ensure_dock_anchor(self, name, instance):
        if self._is_deleted(instance):
            return

        if self._is_deleted(self.dock_anchor):
            self.dock_anchor = instance
            self.dock_anchor_name = name
            return

        if self.dock_anchor is not instance:
            try:
                self.iface.mainWindow().tabifyDockWidget(self.dock_anchor, instance)
            except Exception:
                pass

        self.dock_anchor = instance
        self.dock_anchor_name = name


    def _promote_anchor(self):
        for candidate_name, properties in self.modules.items():
            candidate = properties.get("GUI_INSTANCE")
            if candidate and not self._is_deleted(candidate):
                self.dock_anchor = candidate
                self.dock_anchor_name = candidate_name
                return
        self.dock_anchor = None
        self.dock_anchor_name = None


    @staticmethod
    def _is_deleted(widget):
        if widget is None:
            return True
        try:
            return sip.isdeleted(widget)
        except Exception:
            return False


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