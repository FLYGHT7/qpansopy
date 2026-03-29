# -*- coding: utf-8 -*-
"""
QPANSOPY Plugin for QGIS
Aviation surfaces plugin for QGIS developed by FLYGHT7
Copyright (C) 2020-2025 FLYGHT7
"""
import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QGuiApplication
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox, QSizePolicy
from qgis.PyQt import sip
from qgis.PyQt import QtWidgets, QtCore
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsApplication, Qgis


# Import dock widgets with error handling
try:
    # Import dock widgets from new organized structure
    from .dockwidgets.utilities.qpansopy_vss_dockwidget import QPANSOPYVSSDockWidget
    from .dockwidgets.ils.qpansopy_ils_dockwidget import QPANSOPYILSDockWidget
    from .dockwidgets.utilities.qpansopy_wind_spiral_dockwidget import QPANSOPYWindSpiralDockWidgetBase
    from .dockwidgets.ils.qpansopy_oas_ils_dockwidget import QPANSOPYOASILSDockWidgetBase
    from .dockwidgets.utilities.qpansopy_object_selection_dockwidget import QPANSOPYObjectSelectionDockWidget
    from .dockwidgets.utilities.qpansopy_point_filter_dockwidget import QPANSOPYPointFilterDockWidget
    from .dockwidgets.utilities.qpansopy_feature_merge_dockwidget import QPANSOPYFeatureMergeDockWidget
    from .dockwidgets.utilities.qpansopy_holding_dockwidget import QPANSOPYHoldingDockWidget
    from .dockwidgets.pbn.qpansopy_lnav_dockwidget import QPANSOPYLNAVDockWidget
    from .dockwidgets.pbn.qpansopy_gnss_waypoint_dockwidget import QPANSOPYGNSSWaypointDockWidget
    from .dockwidgets.conv.qpansopy_vor_dockwidget import QPANSOPYVORDockWidget
    from .dockwidgets.conv.qpansopy_ndb_dockwidget import QPANSOPYNDBDockWidget
    from .dockwidgets.conv.qpansopy_conv_initial_dockwidget import QPANSOPYConvInitialDockWidget
    from .dockwidgets.departures.qpansopy_sid_initial_dockwidget import QPANSOPYSIDInitialDockWidget
    from .dockwidgets.departures.qpansopy_omnidirectional_dockwidget import QPANSOPYOmnidirectionalDockWidget
    from .settings_dialog import SettingsDialog  # Import settings dialog
except ImportError as e:
    # Don't raise error here, will be handled in initGui
    pass

class Qpansopy:
    """
    QPANSOPY - Aviation Surfaces Plugin for QGIS
    
    Performance-Based Navigation (PBN) and Conventional procedure design tool
    for QGIS, implementing ICAO Doc 9613 and ICAO Annex 4 standards.
    
    This plugin provides comprehensive tools for designing and analyzing:
    - ILS and OAS surfaces
    - PBN LNAV/RNAV procedures (arrivals, SID, missed approaches)
    - Conventional navigation procedures (VOR, NDB)
    - Utility tools (VSS, Wind Spiral, Holding patterns)
    - Departure protection surfaces
    
    Developed by FLYGHT7
    Copyright (C) 2020-2025 FLYGHT7
    """

    def __init__(self, iface):
        """
        Initialize the QPANSOPY plugin.
        
        Sets up the plugin environment including toolbars, menus, settings,
        and dock widget management infrastructure.
        
        Args:
            iface (QgsInterface): QGIS interface instance providing access to
                the QGIS application at runtime.
        
        Attributes:
            modules (dict): Registry of all available tools and their configurations
            toolbars (dict): Collection of categorized toolbars (CONV, ILS, PBN, etc.)
            dock_anchor (QDockWidget): Reference dock widget for maintaining stable geometry
            settings (QSettings): Plugin settings storage
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        
        # Create actions
        self.actions = []
        self.menu = None  # Will be initialized in initGui

        
        # Initialize toolbars to None
        self.toolbars = {
            'CONV': None,
            'ILS': None,
            'PBN': None,
            'UTILITIES': None,
            'DEPARTURES': None
        }

        # Track a reference dock to keep geometry stable
        self.dock_anchor = None
        self.dock_anchor_name = None
        
        # Verify icons directory exists
        self.icons_dir = os.path.join(self.plugin_dir, 'icons')
        if not os.path.exists(self.icons_dir):
            try:
                os.makedirs(self.icons_dir)
            except Exception:
                # If we can't create the folder, use default icons
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
        """
        Initialize the plugin's graphical user interface.
        
        Creates and configures:
        - Module registry with all available tools
        - Themed toolbars (CONV, ILS, PBN, UTILITIES, DEPARTURES)
        - Menu structure with categorized submenus
        - Action handlers for each tool
        - Settings and About dialogs
        
        Each module is registered with metadata including title, icon,
        tooltip, toolbar assignment, and dock widget class.
        
        The dock widget system uses a single-instance pattern where each
        tool is created once and then shown/hidden on subsequent toggles
        to prevent geometry issues with QGIS main window.
        
        Raises:
            Exception: Displays critical error dialog if initialization fails
        """
        try:
            # Unified modules dictionary (single authoritative mapping)
            self.modules: dict = {
                "VSS": {
                    "TITLE": "VSS Tool",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Visual Segment Surface Tool - Analyze obstacle clearance for visual segments",
                    "ICON": "vss.svg",
                    "DOCK_WIDGET": QPANSOPYVSSDockWidget,
                    "GUI_INSTANCE": None
                },
                "ILS_BASIC": {
                    "TITLE": "ILS Tool",
                    "TOOLBAR": "ILS",
                    "TOOLTIP": "ILS Basic Surface Tool",
                    "ICON": "basic_ils.svg",
                    "DOCK_WIDGET": QPANSOPYILSDockWidget,
                    "GUI_INSTANCE": None
                },
                "WindSpiral": {
                    "TITLE": "Wind Spiral Tool",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Wind Spiral Tool - Calculate and visualize wind spirals for procedure design",
                    "ICON": "wind_spiral.svg",
                    "DOCK_WIDGET": QPANSOPYWindSpiralDockWidgetBase,
                    "GUI_INSTANCE": None
                },
                "ILS_OAS": {
                    "TITLE": "OAS ILS Tool",
                    "TOOLBAR": "ILS",
                    "TOOLTIP": "Obstacle Assessment Surfaces for ILS",
                    "ICON": "oas_ils.svg",
                    "DOCK_WIDGET": QPANSOPYOASILSDockWidgetBase,
                    "GUI_INSTANCE": None
                },
                "LNAV_APCH": {
                    "TITLE": "LNAV",
                    "TOOLBAR": "PBN",
                    "TOOLTIP": "LNAV Arrival, Initial, Intermediate, Final and Missed Approach Tool",
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
                    "DOCK_WIDGET": QPANSOPYConvInitialDockWidget,
                    "GUI_INSTANCE": None
                },
                "ObjectSelection": {
                    "TITLE": "Object Selection",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Extract objects intersecting with surfaces",
                    "ICON": "SOO.png",
                    "DOCK_WIDGET": QPANSOPYObjectSelectionDockWidget,
                    "GUI_INSTANCE": None
                },
                "PointFilter": {
                    "TITLE": "Point Filter",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Filter points based on THR elevation threshold",
                    "ICON": "point_filter.svg",
                    "DOCK_WIDGET": QPANSOPYPointFilterDockWidget,
                    "GUI_INSTANCE": None
                },
                "FeatureMerge": {
                    "TITLE": "Feature Merge",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Merge multiple vector layers into a single memory layer",
                    "ICON": "feature_merge.svg",
                    "DOCK_WIDGET": None,
                    "RUN_ACTION": self.run_feature_merge_action,
                    "GUI_INSTANCE": None
                },
                "Holding": {
                    "TITLE": "Holding",
                    "TOOLBAR": "UTILITIES",
                    "TOOLTIP": "Conventional holding (racetrack) generator",
                    "ICON": "holding.svg",
                    "DOCK_WIDGET": QPANSOPYHoldingDockWidget,
                    "GUI_INSTANCE": None
                },
                "SID_INITIAL": {
                    "TITLE": "SID Initial",
                    "TOOLBAR": "DEPARTURES",
                    "TOOLTIP": "SID Initial Climb Protection Areas Tool",
                    "ICON": os.path.join(self.icons_dir, 'sid_initial.svg'),
                    "DOCK_WIDGET": QPANSOPYSIDInitialDockWidget,
                    "GUI_INSTANCE": None
                },
                "OMNIDIRECTIONAL_SID": {
                    "TITLE": "OMNI",
                    "TOOLBAR": "DEPARTURES",
                    "TOOLTIP": "Omnidirectional SID Departure Surface Tool",
                    "ICON": os.path.join(self.icons_dir, 'omnidirectional_sid.svg'),
                    "DOCK_WIDGET": QPANSOPYOmnidirectionalDockWidget,
                    "GUI_INSTANCE": None
                }
            }
            
            # If you do not want empty submenus to be displayed self.submenus can be left as an empty dictionary
            self.submenus: dict = {"CONV": None, "ILS": None, "PBN": None, "UTILITIES": None, "DEPARTURES": None}
            
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

            
            self.toolbars['DEPARTURES'] = self.iface.addToolBar("QPANSOPY - DEPARTURES")
            self.toolbars['DEPARTURES'].setObjectName("QPANSOPYDEPARTURESToolBar")
            
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
                action = QAction(QIcon(icon_path), properties["TITLE"], self.iface.mainWindow())
                # If module provides a direct-run action, hook that instead of toggling a dock
                run_cb = properties.get("RUN_ACTION")
                if callable(run_cb) and properties.get("DOCK_WIDGET") is None:
                    # Ensure we accept the QAction's checked(bool) parameter
                    action.triggered.connect(lambda checked=False, cb=run_cb: cb(checked))
                else:
                    action.triggered.connect(lambda checked, n=name: self.toggle_dock(n, checked))
                action.setToolTip(properties['TOOLTIP'])
                toolbar_name = properties['TOOLBAR']
                if toolbar_name not in self.toolbars or self.toolbars[toolbar_name] is None:
                    tb = self.iface.addToolBar(f"QPANSOPY - {toolbar_name}")
                    try:
                        tb.setObjectName(f"QPANSOPY{toolbar_name}ToolBar")
                    except Exception:
                        pass
                    self.toolbars[toolbar_name] = tb
                self.toolbars[toolbar_name].addAction(action)
                self.actions.append(action)
                if self.submenus.get(toolbar_name) is None:
                    self.submenus[toolbar_name] = QMenu(toolbar_name, self.menu)
                    self.menu.addMenu(self.submenus[toolbar_name])
                self.submenus[toolbar_name].addAction(action)

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
        """
        Clean up and remove the plugin from QGIS interface.
        
        Performs complete teardown of all plugin components:
        - Removes menu and all menu actions
        - Removes and deletes all toolbars
        - Closes and removes all dock widgets
        - Clears module registry
        
        Called automatically when the plugin is unloaded or QGIS closes.
        """
        # Remove menu
        if self.menu:
            menuBar = self.iface.mainWindow().menuBar()
            menuBar.removeAction(self.menu.menuAction())
        # Remove toolbars
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
        """
        Toggle visibility of a tool's dock widget.
        
        Manages the lifecycle and visibility of dock widgets using a single-instance
        pattern. On first invocation, creates and configures the dock widget.
        Subsequent calls show/hide the existing instance.
        
        When showing a dock, automatically hides all other tool docks to maintain
        a clean workspace and prevent QGIS window geometry issues.
        
        Args:
            name (str, optional): Module key from self.modules dictionary.
                If None, the function returns without action.
            checked (bool, optional): Action checked state (not used, for signal compatibility).
        
        Behavior:
            - First call: Creates dock widget, configures settings, adds to QGIS interface
            - Subsequent calls: Toggles visibility (show/hide)
            - Always maintains dock_anchor reference for stable tabification
            - Hides sibling docks when showing to avoid overlap
        
        Configuration applied to new docks:
            - Object name and window title
            - Allowed dock areas (left/right)
            - KML export checkbox state (from settings)
            - Log panel visibility and resizability
            - Connection to closing signal handler
        """
        # If name is None, simply return without doing anything
        if name is None:
            return
            
        instance = self.modules[name]["GUI_INSTANCE"]
        if instance is None:
            # Create and register the dock widget once; later toggles just show/hide
            dock_widget_cls = self.modules[name]["DOCK_WIDGET"]
            # If this module is designed as a direct action, run it and return
            if dock_widget_cls is None:
                run_cb = self.modules[name].get("RUN_ACTION")
                if callable(run_cb):
                    run_cb()
                return
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
            # PointFilter is an exception - it doesn't have a KML export button by design
            if name != "PointFilter":
                try:
                    if hasattr(instance, "exportKmlCheckBox"):
                        instance.exportKmlCheckBox.setChecked(self.settings.value("qpansopy/enable_kml", False, type=bool))
                except AttributeError:
                    QMessageBox.warning(self.iface.mainWindow(), "QPANSOPY Error", "This Widget has no KML Export Button")
            try:
                instance.exportKmlCheckBox.setChecked(self.settings.value("qpansopy/enable_kml", False, type=bool))
            except AttributeError:
                pass  # Widget doesn't have KML export, silently ignore
            if hasattr(instance, "logTextEdit"):
                show_log = self.settings.value("qpansopy/show_log", True, type=bool)
                try:
                    # Hide or show the entire Log group box if present
                    log_widget = getattr(instance, "logTextEdit", None)
                    log_group = None
                    parent = log_widget.parentWidget() if log_widget else None
                    while parent is not None and not isinstance(parent, QtWidgets.QGroupBox):
                        parent = parent.parentWidget()
                    if isinstance(parent, QtWidgets.QGroupBox):
                        log_group = parent
                    # Apply visibility
                    if log_group:
                        log_group.setVisible(show_log)
                    if log_widget:
                        log_widget.setVisible(show_log)
                except Exception:
                    # Fallback to just the editor visibility
                    try:
                        instance.logTextEdit.setVisible(show_log)
                    except Exception:
                        pass
                # Ensure the log panel is actually resizable regardless of UI max heights (only when visible)
                if show_log:
                    try:
                        self._ensure_resizable_log(instance)
                    except Exception:
                        pass
            instance.closingPlugin.connect(lambda: self.on_dock_closed(name))
            
            # CRITICAL: Wrap content in scroll area if not already wrapped (issue #39)
            # Docks without scroll areas request full height of all content causing window resize
            # VSS and Wind Spiral have QScrollArea in UI and work fine
            # LNAV, GNSS, SID Initial, OMNI, Holding don't have it and fail on first opening
            self._ensure_scroll_area_wrapper(instance)
            
            # Set maximum size BEFORE adding to dock area (issue #39)
            self._apply_maximum_size_constraint(instance)
            
            # CRITICAL: Force initial conservative size (issue #39 - first-time cache)
            # On first opening, Qt calculates size based on content sizeHint which can be huge
            # By forcing a small initial size with resize(), Qt caches this instead
            # This prevents the massive initial expansion that resizes QGIS window
            self._force_initial_small_size(instance)
            
            # CRITICAL: Add dock HIDDEN first (issue #39 - first-time opening)
            # This gives Qt the context of the dock area to calculate geometry correctly
            # Without this, Qt doesn't know the available space on first opening
            instance.hide()  # Ensure it's hidden before adding
            self.iface.addDockWidget(Qt.RightDockWidgetArea, instance)
            self._ensure_dock_anchor(name, instance)
            
            # Now that dock is in the area (hidden), force geometry calculation with proper context
            self._force_initial_geometry_calculation(instance)
            
            # Hide other docks BEFORE showing this one to prevent simultaneous visibility
            self._hide_other_docks(name)
            # Additional event processing to ensure geometry updates complete (issue #39)
            self._wait_for_geometry_update()
            instance.show()
            instance.raise_()
        else:
            # Toggle visibility of existing instance; hide siblings when showing
            if instance.isVisible():
                instance.hide()
            else:
                # Hide other docks BEFORE showing this one to prevent simultaneous visibility
                self._hide_other_docks(name)
                # Additional event processing to ensure geometry updates complete (issue #39)
                self._wait_for_geometry_update()
                # Set maximum size to prevent exceeding available screen space (issue #39)
                self._apply_maximum_size_constraint(instance)
                self._ensure_dock_anchor(name, instance)
                instance.show()
                instance.raise_()

    def _ensure_resizable_log(self, dock_instance):
        """
        Configure log panel to be resizable without forcing QGIS window resize.
        
        Implements a custom resize handle for the log text edit widget that allows
        users to adjust log panel height independently. This prevents the dock widget
        from imposing strict size constraints on the QGIS main window.
        
        Args:
            dock_instance: Dock widget instance containing a logTextEdit widget.
        
        Configuration steps:
            1. Removes restrictive height constraints from log widget
            2. Sets flexible size policies
            3. Configures word wrapping to prevent horizontal overflow
            4. Adds custom resize handle below log panel
            5. Optimizes layout to prevent forced window geometry changes
        
        The resize handle allows vertical adjustment within min/max bounds while
        keeping other dock elements fixed in size.
        
        Changes from issue #39 fix:
            - Changed layout constraint from SetMinAndMaxSize to SetDefaultConstraint
            - Changed GroupBox size policy from Fixed to Minimum
            - Removed forced geometry recalculation (adjustSize/updateGeometry)
        
        These changes prevent QGIS from displaying geometry warnings and resizing
        the entire application window when switching between tool docks.
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
                        # Use SetDefaultConstraint instead of SetMinAndMaxSize to avoid forcing QGIS window resize
                        root_layout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
                    except Exception:
                        pass

                # Ensure every group box hugs its content (no vertical expansion)
                for gb in root_widget.findChildren(QtWidgets.QGroupBox):
                    try:
                        gb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
                    except Exception:
                        pass

                # Don't force geometry recalculation - let Qt handle it naturally
                # This prevents QGIS window resizing when switching between docks
            except Exception:
                pass
        except Exception:
            pass
    def on_dock_closed(self, name):
        """
        Handle dock widget closure event.
        
        Cleans up references when a tool dock is closed by the user.
        If the closed dock was the anchor dock, promotes another visible
        dock to become the new anchor.
        
        Args:
            name (str): Module key from self.modules dictionary identifying
                the dock that was closed.
        
        Side effects:
            - Clears GUI_INSTANCE reference in modules registry
            - Updates dock_anchor if necessary via _promote_anchor()
        """
        self.modules[name]["GUI_INSTANCE"] = None
        if self.dock_anchor_name == name:
            self._promote_anchor()


    def _hide_other_docks(self, active_name):
        """
        Hide all dock widgets except the specified active one.
        
        Maintains a clean workspace by ensuring only one tool dock is visible
        at a time. This prevents dock overlap and geometry conflicts.
        
        Args:
            active_name (str): Module key of the dock that should remain visible.
        """
        for other_name, other_properties in self.modules.items():
            if other_name == active_name:
                continue
            other_instance = other_properties["GUI_INSTANCE"]
            if other_instance and other_instance.isVisible():
                other_instance.hide()
        
        # Process pending events to ensure hide operations complete before showing new dock
        # This prevents geometry conflicts when switching rapidly between tools (issue #39)
        try:
            QgsApplication.processEvents()
        except Exception:
            pass

    def _ensure_scroll_area_wrapper(self, dock_instance):
        """
        Wrap dock content in QScrollArea if not already wrapped.
        
        Docks with scroll areas (VSS, Wind Spiral) work perfectly because the scroll
        area has a fixed size and content scrolls within it. Docks without scroll areas
        (LNAV, GNSS, SID Initial, OMNI, Holding) request full content height on first
        opening, forcing QGIS window resize.
        
        This method detects if content is already in a scroll area, and if not,
        wraps it in one programmatically.
        
        Args:
            dock_instance: The QDockWidget instance to check/wrap
            
        Issue #39: First-time opening of docks without scroll areas causes window
        resize because content requests its full preferred height all at once.
        """
        try:
            content_widget = dock_instance.widget()
            if not content_widget:
                return
            
            # Check if content is already a QScrollArea or has one as direct child
            if isinstance(content_widget, QtWidgets.QScrollArea):
                return  # Already has scroll area
            
            # Check if first child is a scroll area
            if content_widget.layout():
                for i in range(content_widget.layout().count()):
                    item = content_widget.layout().itemAt(i)
                    if item and item.widget() and isinstance(item.widget(), QtWidgets.QScrollArea):
                        return  # Has scroll area in layout
            
            # No scroll area found - wrap the content
            # Create new scroll area
            scroll_area = QtWidgets.QScrollArea()
            scroll_area.setWidgetResizable(True)  # CRITICAL: Allow content to resize
            scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)  # Seamless appearance
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            
            # Reparent the existing content widget into the scroll area
            scroll_area.setWidget(content_widget)
            
            # Set the scroll area as the dock's widget
            dock_instance.setWidget(scroll_area)
            
        except Exception as e:
            # If wrapping fails, continue without scroll area
            # Better to have the dock work (even with resize issue) than to crash
            pass

    def _force_initial_small_size(self, dock_instance):
        """
        Force dock to start with a small conservative size before Qt calculations.
        
        On first opening, Qt doesn't have cached size information and asks the
        content widget for its sizeHint(). For complex docks with many fields,
        this sizeHint can be enormous (sometimes taller than the screen), causing
        Qt to attempt resizing the QGIS main window.
        
        This method forces an explicit small size BEFORE Qt does any calculations,
        so Qt caches this conservative size instead of the huge sizeHint.
        
        Args:
            dock_instance: The QDockWidget instance to resize
            
        Issue #39: First-time opening of large docks (LNAV, GNSS, SID Initial,
        OMNI, Holding) causes window resize because their content sizeHint is
        larger than available space. This "pre-seeds" Qt's cache with a safe size.
        """
        try:
            # Get screen info for calculations
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                screen_height = screen_geometry.height()
                
                # Force a conservative initial size (50% of available height)
                # This is much smaller than what large docks would request
                initial_height = min(int((screen_height - 400) * 0.5), 400)
                initial_width = 300
            else:
                # Fallback to very conservative size
                initial_height = 350
                initial_width = 300
            
            # CRITICAL: Force this size on both dock and content widget
            # This makes Qt cache this size instead of calculating from sizeHint
            dock_instance.resize(initial_width, initial_height)
            
            content_widget = dock_instance.widget()
            if content_widget:
                content_widget.resize(initial_width, initial_height - 30)  # Account for title bar
            
        except Exception:
            # Fallback to hardcoded safe size
            try:
                dock_instance.resize(300, 350)
            except Exception:
                pass

    def _wait_for_geometry_update(self):
        """
        Wait for Qt to complete geometry recalculation after dock hide/show operations.
        
        Introduces a delay to allow Qt's layout system to fully process
        dock area geometry changes before showing a new dock. This prevents the
        QGIS main window from being resized when switching between tools.
        
        The delay (200ms) accounts for rapid toolbar button toggles which are
        faster than closing with the X button, ensuring Qt layout engine completes
        all geometry calculations.
        
        Issue #39: Without sufficient delay, Qt attempts to show the new dock before
        the previous dock's space is fully reclaimed, causing main window resize
        and incorrect dock positioning on subsequent openings. This is especially
        critical when toggling rapidly via toolbar buttons vs closing with X button.
        """
        try:
            # Delay to let Qt complete geometry calculations
            # 200ms ensures Qt layout engine completes even with rapid toolbar toggles
            import time
            time.sleep(0.20)  # 200 milliseconds
            # Process any remaining events after the delay
            QgsApplication.processEvents()
        except Exception:
            pass

    def _force_initial_geometry_calculation(self, dock_instance):
        """
        Force Qt to calculate initial geometry for new dock instances.
        
        On first opening, Qt doesn't have cached size information and must calculate
        the dock's geometry on-the-fly, which can cause QGIS main window to resize.
        This method forces Qt to calculate and cache the geometry while the dock
        is in the dock area but hidden, giving Qt proper context for calculations.
        
        The technique: with dock already added to dock area (but hidden), force
        complete layout and geometry calculations. Qt will cache this information
        for when the dock is actually shown.
        
        Args:
            dock_instance: The QDockWidget instance already added to dock area (hidden)
            
        Issue #39: First-time opening of docks causes window resize because Qt
        doesn't know the size until it calculates it. Subsequent openings work
        fine because Qt has cached the geometry information.
        """
        try:
            # Get the dock's content widget
            content_widget = dock_instance.widget()
            if not content_widget:
                return
            
            # Force complete style and layout calculation
            content_widget.ensurePolished()  # Force style calculation
            content_widget.updateGeometry()   # Notify layout system of size changes
            
            # Process events to let layouts calculate
            QgsApplication.processEvents()
            
            # Calculate optimal size for content
            content_widget.adjustSize()
            
            # Force the dock itself to calculate and cache its geometry
            # This is critical - dock needs to know its size in the context of the dock area
            dock_instance.updateGeometry()
            dock_instance.adjustSize()
            
            # Process all pending events to complete geometry calculations
            QgsApplication.processEvents()
            
            # Additional delay to ensure all calculations complete and are cached
            import time
            time.sleep(0.08)  # 80ms - longer than before since this is more critical
            
            # Final event processing to ensure cache is updated
            QgsApplication.processEvents()
            
        except Exception:
            pass

    def _apply_maximum_size_constraint(self, dock_instance):
        """
        Apply constraints to prevent dock from forcing QGIS main window resize.
        
        Implements multiple strategies to prevent dockwidgets from expanding beyond
        available space and triggering main window geometry changes:
        
        1. Disables features that allow dock to resize main window
        2. Sets maximum size based on available screen space
        3. Configures size policy to prefer shrinking over expanding
        
        Args:
            dock_instance: The QDockWidget instance to constrain
            
        Issue #39: Dockwidgets can force QGIS window resize when their content
        requests more space than available, causing "Unable to set geometry" error.
        """
        try:
            # CRITICAL: Disable the feature that allows dock to resize the main window
            # This is the key fix - prevents dock from requesting main window resize
            dock_instance.setFeatures(
                dock_instance.features() & ~QtWidgets.QDockWidget.DockWidgetVerticalTitleBar
            )
            
            # Get the primary screen geometry for size calculations
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                screen_height = screen_geometry.height()
                screen_width = screen_geometry.width()
                
                # Reserve space for QGIS UI elements
                # Top: toolbars, menus, navigation (~120px)
                # Bottom: statusbar (~30px)  
                # Safety margin: ~250px for various UI elements and borders
                # Very conservative for large docks (LNAV, GNSS, SID Initial, OMNI, Holding)
                reserved_height = 400
                
                # Calculate maximum available dimensions
                # Use very aggressive constraint to prevent any overflow
                max_dock_height = max(screen_height - reserved_height, 350)
                max_dock_width = int(screen_width * 0.8)
                
                # CRITICAL: Apply constraint to BOTH dock AND its content widget
                # Content widget's sizeHint can request more space than available
                # causing main window resize on first opening
                dock_instance.setMaximumSize(max_dock_width, max_dock_height)
                
                # Also constrain the content widget itself - this is CRITICAL
                content_widget = dock_instance.widget()
                if content_widget:
                    content_widget.setMaximumSize(max_dock_width, max_dock_height)
                    # Also set size policy on content widget to prevent expansion
                    content_policy = content_widget.sizePolicy()
                    content_policy.setVerticalPolicy(QSizePolicy.Preferred)
                    content_policy.setHorizontalPolicy(QSizePolicy.Preferred)
                    content_widget.setSizePolicy(content_policy)
            else:
                # Fallback if no screen info available
                dock_instance.setMaximumSize(800, 550)
                content_widget = dock_instance.widget()
                if content_widget:
                    content_widget.setMaximumSize(800, 550)
                    content_policy = content_widget.sizePolicy()
                    content_policy.setVerticalPolicy(QSizePolicy.Preferred)
                    content_policy.setHorizontalPolicy(QSizePolicy.Preferred)
                    content_widget.setSizePolicy(content_policy)
            
            # Configure size policy to prefer staying within bounds
            # Preferred = can grow/shrink, but prefers its size hint
            # This makes the dock adapt to available space rather than force resize
            size_policy = dock_instance.sizePolicy()
            size_policy.setVerticalPolicy(QSizePolicy.Preferred)
            size_policy.setHorizontalPolicy(QSizePolicy.Preferred)
            size_policy.setRetainSizeWhenHidden(False)  # Don't force size when re-showing
            dock_instance.setSizePolicy(size_policy)
            
        except Exception as e:
            # If anything fails, try basic fallback
            try:
                dock_instance.setMaximumSize(800, 600)
                size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                dock_instance.setSizePolicy(size_policy)
            except Exception:
                pass

    def _ensure_dock_anchor(self, name, instance):
        """
        Maintain a stable anchor dock for consistent tabification.
        
        Ensures all tool docks are tabified with a reference anchor dock,
        preventing geometry issues when switching between tools. The anchor
        dock provides a stable reference point for Qt's dock management.
        
        Args:
            name (str): Module key of the dock to potentially become anchor.
            instance: Dock widget instance to tabify.
        
        Behavior:
            - If no anchor exists, makes this dock the anchor
            - If anchor exists, tabifies new dock with anchor
            - Skips deleted widgets to prevent crashes
        """
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
        """
        Find and promote a new anchor dock when current anchor is closed.
        
        Searches through all open tool docks to find a suitable replacement
        anchor. If no valid candidates exist, clears the anchor reference.
        
        This ensures the tabification system continues to work correctly
        even after the user closes the current anchor dock.
        """
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
        """
        Check if a Qt widget has been deleted.
        
        Uses SIP's isdeleted() to safely check widget validity before
        attempting operations. Prevents crashes from accessing deleted
        widget references.
        
        Args:
            widget: Qt widget instance to check.
        
        Returns:
            bool: True if widget is None or has been deleted, False otherwise.
        """
        if widget is None:
            return True
        try:
            return sip.isdeleted(widget)
        except Exception:
            return False


    def show_about_dialog(self):
        """
        Display the About dialog with plugin information.
        
        Shows a modal dialog containing:
        - FLYGHT7 logo (if available)
        - Plugin title and developer information
        - GitHub repository link
        
        The dialog provides users with version information and
        access to the project's GitHub page for documentation and support.
        """
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
        """
        Display the Settings dialog for plugin configuration.
        
        Opens a modal dialog allowing users to configure:
        - KML export default state
        - Log panel visibility
        
        Settings are persisted to QSettings and applied immediately
        to all open tool docks without requiring QGIS restart.
        
        Side effects:
            - Updates self.settings_values with new configuration
            - Applies log visibility changes to all active dock widgets
        """
        # Use None as parent to avoid QWidget errors
        dlg = SettingsDialog(None, self.settings)
        if dlg.exec_():
            vals = dlg.get_values()
            self.settings.setValue("qpansopy/enable_kml", vals["enable_kml"])
            self.settings.setValue("qpansopy/show_log", vals["show_log"])
            self.settings_values = vals
            # Apply log visibility immediately to all existing docks
            try:
                self._apply_log_visibility(vals["show_log"])
            except Exception:
                pass

    def create_callback(self, name):
        """Create a callback function for the given module name"""
        def callback():
            self.toggle_dock(name)
        return callback

    def run_feature_merge_action(self, checked=False):
        """Run Feature Merge directly without opening a dock.
        Select 2+ vector layers with same geometry and CRS, merge into memory layer.
        """
        try:
            layers = [lyr for lyr in QgsProject.instance().mapLayers().values() if isinstance(lyr, QgsVectorLayer)]
        except Exception:
            layers = []
        try:
            selected_layers = self.iface.layerTreeView().selectedLayers()
        except Exception:
            selected_layers = []
        # Keep only vector layers
        selected_layers = [lyr for lyr in selected_layers if isinstance(lyr, QgsVectorLayer)]
        if len(selected_layers) < 2:
            QMessageBox.information(self.iface.mainWindow(), "Feature Merge", "Select at least two vector layers in the Layers panel.")
            return
        # Validate geometry type and CRS
        geom_type = selected_layers[0].wkbType()
        crs = selected_layers[0].crs()
        for lyr in selected_layers[1:]:
            if lyr.wkbType() != geom_type:
                QMessageBox.warning(self.iface.mainWindow(), "Feature Merge", "Selected layers must have the same geometry type.")
                return
            if lyr.crs() != crs:
                QMessageBox.warning(self.iface.mainWindow(), "Feature Merge", "Selected layers must share the same CRS.")
                return
        # Default merged layer name; user can rename in layer tree later
        base_name = "Merged_Layer"
        name = base_name
        used_names = {lyr.name() for lyr in QgsProject.instance().mapLayers().values()}
        idx = 1
        while name in used_names:
            idx += 1
            name = f"{base_name}_{idx}"
        try:
            from .modules.utilities.feature_merge import merge_selected_layers
            result = merge_selected_layers(self.iface, selected_layers, name, None)
            if result and result.get('merged_layer'):
                count = result.get('total_features', 0)
                self.iface.messageBar().pushMessage("QPANSOPY", f"Feature Merge completed: {count} features", level=Qgis.Success)
            else:
                self.iface.messageBar().pushMessage("QPANSOPY", "Feature Merge finished with no result", level=Qgis.Warning)
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "Feature Merge", f"Merge failed: {e}")
            try:
                from qgis.core import Qgis as _Q
                self.iface.messageBar().pushMessage("QPANSOPY", f"Merge failed: {e}", level=_Q.Critical)
            except Exception:
                pass

    def _apply_log_visibility(self, show_log: bool):
        """Apply log visibility setting to all instantiated docks."""
        for name, props in getattr(self, "modules", {}).items():
            inst = props.get("GUI_INSTANCE")
            if not inst:
                continue
            try:
                log_widget = getattr(inst, "logTextEdit", None)
                log_group = None
                parent = log_widget.parentWidget() if log_widget else None
                while parent is not None and not isinstance(parent, QtWidgets.QGroupBox):
                    parent = parent.parentWidget()
                if isinstance(parent, QtWidgets.QGroupBox):
                    log_group = parent
                if log_group:
                    log_group.setVisible(show_log)
                if log_widget:
                    log_widget.setVisible(show_log)
                # When re-showing, ensure resizable behavior is restored
                if show_log:
                    try:
                        self._ensure_resizable_log(inst)
                    except Exception:
                        pass
            except Exception:
                continue