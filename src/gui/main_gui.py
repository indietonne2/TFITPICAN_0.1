#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.1
# License: MIT
# Filename: main_gui.py
# Pathname: src/gui/
# Description: Main GUI controller for the TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable

try:
    from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                QTabWidget, QSplitter, QLabel, QStatusBar, QToolBar, QAction,
                                QMessageBox, QFileDialog, QMenu, QDockWidget)
    from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QIcon, QPixmap, QPalette, QColor, QFont
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

class MainGUI(QMainWindow):
    """Main GUI controller for TFITPICAN application"""
    
    # Signal for errors
    error_signal = pyqtSignal(dict)
    
    # Signal for status updates
    status_signal = pyqtSignal(str, int)  # message, timeout
    
    def __init__(self, config=None, user_manager=None, mode_manager=None,
                error_manager=None, translation_manager=None):
        """Initialize the main GUI
        
        Args:
            config: Application configuration
            user_manager: User manager instance
            mode_manager: Mode manager instance
            error_manager: Error manager instance
            translation_manager: Translation manager instance
        """
        if not GUI_AVAILABLE:
            raise ImportError("PyQt5 is required for the GUI")
            
        super().__init__()
        
        self.logger = logging.getLogger("MainGUI")
        self.config = config or {}
        self.user_manager = user_manager
        self.mode_manager = mode_manager
        self.error_manager = error_manager
        self.translation_manager = translation_manager
        
        # Child panels and components
        self.tabs = {}
        self.panels = {}
        self.dock_widgets = {}
        
        # Set up UI
        self._setup_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Set up error handler
        if self.error_manager:
            self.error_manager.register_callback(self._handle_error)
            
        # Set up mode handler
        if self.mode_manager:
            self.mode_manager.register_callback(self._handle_mode_change)
            
        # Set up translation handler
        if self.translation_manager:
            self._apply_translations()
            
        # Update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
        
        self.logger.info("Main GUI initialized")
        
    def _setup_ui(self):
        """Set up the main UI components"""
        # Set window properties
        self.setWindowTitle("TFITPICAN")
        self.resize(1024, 768)
        
        # Set application icon if available
        icon_path = "assets/icon.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        # Create central widget with tab container
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.main_layout.addWidget(self.tab_widget)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Status bar components
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # User info widget
        self.user_info = QLabel()
        self.status_bar.addPermanentWidget(self.user_info)
        
        # Create menus
        self._create_menus()
        
        # Create toolbars
        self._create_toolbars()
        
        # Set up docks
        self._setup_docks()
        
        # Set window theme
        self._apply_theme()
        
    def _create_menus(self):
        """Create application menus"""
        # Main menu bar
        self.menu_bar = self.menuBar()
        
        # File menu
        self.file_menu = self.menu_bar.addMenu("&File")
        
        # File > New Scenario
        new_scenario_action = QAction("&New Scenario", self)
        new_scenario_action.setShortcut("Ctrl+N")
        new_scenario_action.triggered.connect(self._on_new_scenario)
        self.file_menu.addAction(new_scenario_action)
        
        # File > Open
        open_action = QAction("&Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)
        self.file_menu.addAction(open_action)
        
        # File > Save
        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save)
        self.file_menu.addAction(save_action)
        
        # File > Export
        export_action = QAction("&Export...", self)
        export_action.triggered.connect(self._on_export)
        self.file_menu.addAction(export_action)
        
        self.file_menu.addSeparator()
        
        # File > Exit
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
        
        # Edit menu
        self.edit_menu = self.menu_bar.addMenu("&Edit")
        
        # Edit > Settings
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self._on_settings)
        self.edit_menu.addAction(settings_action)
        
        # View menu
        self.view_menu = self.menu_bar.addMenu("&View")
        
        # View > Fullscreen
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setCheckable(True)
        fullscreen_action.triggered.connect(self._on_toggle_fullscreen)
        self.view_menu.addAction(fullscreen_action)
        
        self.view_menu.addSeparator()
        
        # View > Dock widgets will be added dynamically
        
        # Tools menu
        self.tools_menu = self.menu_bar.addMenu("&Tools")
        
        # Tools > CAN Monitor
        can_monitor_action = QAction("&CAN Monitor", self)
        can_monitor_action.triggered.connect(self._on_can_monitor)
        self.tools_menu.addAction(can_monitor_action)
        
        # Tools > Log Viewer
        log_viewer_action = QAction("&Log Viewer", self)
        log_viewer_action.triggered.connect(self._on_log_viewer)
        self.tools_menu.addAction(log_viewer_action)
        
        # Help menu
        self.help_menu = self.menu_bar.addMenu("&Help")
        
        # Help > About
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        self.help_menu.addAction(about_action)
        
    def _create_toolbars(self):
        """Create application toolbars"""
        # Main toolbar
        self.main_toolbar = QToolBar("Main Toolbar")
        self.main_toolbar.setIconSize(QSize(24, 24))
        self.main_toolbar.setMovable(True)
        self.addToolBar(self.main_toolbar)
        
        # Run button
        run_action = QAction("Run", self)
        run_action.triggered.connect(self._on_run)
        if os.path.exists("assets/run.png"):
            run_action.setIcon(QIcon("assets/run.png"))
        self.main_toolbar.addAction(run_action)
        
        # Stop button
        stop_action = QAction("Stop", self)
        stop_action.triggered.connect(self._on_stop)
        if os.path.exists("assets/stop.png"):
            stop_action.setIcon(QIcon("assets/stop.png"))
        self.main_toolbar.addAction(stop_action)
        
        self.main_toolbar.addSeparator()
        
        # Load DBC button
        load_dbc_action = QAction("Load DBC", self)
        load_dbc_action.triggered.connect(self._on_load_dbc)
        if os.path.exists("assets/dbc.png"):
            load_dbc_action.setIcon(QIcon("assets/dbc.png"))
        self.main_toolbar.addAction(load_dbc_action)
        
    def _setup_docks(self):
        """Set up dock widgets"""
        # Logger dock
        logger_dock = QDockWidget("Log", self)
        logger_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Create logger widget (placeholder)
        logger_widget = QWidget()
        logger_layout = QVBoxLayout(logger_widget)
        logger_layout.addWidget(QLabel("Logger output will appear here"))
        
        logger_dock.setWidget(logger_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, logger_dock)
        
        # Store dock widget
        self.dock_widgets["logger"] = logger_dock
        
        # Add to View menu
        self.view_menu.addAction(logger_dock.toggleViewAction())
        
    def _apply_theme(self):
        """Apply UI theme based on mode settings"""
        if not self.mode_manager:
            return
            
        # Get theme from mode manager
        theme = self.mode_manager.get_ui_setting("theme", "light")
        
        if theme == "dark":
            # Dark theme
            palette = QPalette()
            
            # Set window background to dark gray
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            
            # Set button colors
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            
            # Set highlight color
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            
            # Set base colors
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            
            # Set text colors
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            
            # Apply palette
            QApplication.setPalette(palette)
            
            # Set stylesheet for additional customization
            QApplication.setStyleSheet("""
                QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }
                QTabWidget::pane { border: 1px solid #444; }
                QTabBar::tab { background-color: #353535; color: #ffffff; padding: 6px 10px; }
                QTabBar::tab:selected { background-color: #2a82da; }
            """)
        else:
            # Light theme (default)
            QApplication.setPalette(QApplication.style().standardPalette())
            QApplication.setStyleSheet("")
    
    def _apply_translations(self):
        """Apply translations to UI elements"""
        if not self.translation_manager:
            return
            
        # Update window title
        self.setWindowTitle(self.translation_manager.get_string("app.title", "TFITPICAN"))
        
        # Update menus
        self.file_menu.setTitle(self.translation_manager.get_string("menu.file", "&File"))
        self.edit_menu.setTitle(self.translation_manager.get_string("menu.edit", "&Edit"))
        self.view_menu.setTitle(self.translation_manager.get_string("menu.view", "&View"))
        self.tools_menu.setTitle(self.translation_manager.get_string("menu.tools", "&Tools"))
        self.help_menu.setTitle(self.translation_manager.get_string("menu.help", "&Help"))
        
        # Update status bar
        self.status_label.setText(self.translation_manager.get_string("status.ready", "Ready"))
        
        # Update dock titles
        if "logger" in self.dock_widgets:
            self.dock_widgets["logger"].setWindowTitle(
                self.translation_manager.get_string("dock.logger", "Log")
            )
    
    def _connect_signals(self):
        """Connect internal signals and slots"""
        # Connect error signal to error handler
        self.error_signal.connect(self._on_error)
        
        # Connect status signal
        self.status_signal.connect(self._on_status_update)
    
    def add_tab(self, widget, name, icon=None, closable=True):
        """Add a new tab to the main tab widget
        
        Args:
            widget: Widget to add as tab content
            name: Tab name
            icon: Optional tab icon
            closable: Whether the tab can be closed
            
        Returns:
            int: Index of the added tab
        """
        # Create a wrapper widget to allow adding close button
        if closable:
            # Create close button logic if needed
            pass
            
        # Add the tab
        if icon:
            index = self.tab_widget.addTab(widget, icon, name)
        else:
            index = self.tab_widget.addTab(widget, name)
            
        # Store reference
        self.tabs[name] = {
            "widget": widget,
            "index": index,
            "closable": closable
        }
        
        # Select the new tab
        self.tab_widget.setCurrentIndex(index)
        
        return index
    
    def remove_tab(self, name_or_index):
        """Remove a tab
        
        Args:
            name_or_index: Tab name or index
            
        Returns:
            bool: True if tab was removed
        """
        if isinstance(name_or_index, str):
            # Find by name
            if name_or_index not in self.tabs:
                return False
                
            index = self.tabs[name_or_index]["index"]
        else:
            # Use provided index
            index = name_or_index
            
            # Find tab name to remove from dictionary
            tab_name = None
            for name, tab_info in self.tabs.items():
                if tab_info["index"] == index:
                    tab_name = name
                    break
                    
            if tab_name is None:
                return False
                
            # Remove from tabs dictionary
            del self.tabs[tab_name]
            
        # Remove from tab widget
        self.tab_widget.removeTab(index)
        
        # Update indices of remaining tabs
        for name, tab_info in self.tabs.items():
            if tab_info["index"] > index:
                tab_info["index"] -= 1
                
        return True
    
    def add_dock_widget(self, widget, name, area=Qt.RightDockWidgetArea):
        """Add a dock widget
        
        Args:
            widget: Widget to add as dock content
            name: Dock name
            area: Dock area
            
        Returns:
            QDockWidget: The created dock widget
        """
        # Create dock widget
        dock = QDockWidget(name, self)
        dock.setWidget(widget)
        
        # Add to main window
        self.addDockWidget(area, dock)
        
        # Store reference
        self.dock_widgets[name] = dock
        
        # Add to View menu
        self.view_menu.addAction(dock.toggleViewAction())
        
        return dock
    
    def _handle_error(self, error):
        """Handle error notifications from error manager
        
        Args:
            error: Error information dictionary
        """
        # Emit signal to ensure UI updates happen on the UI thread
        self.error_signal.emit(error)
    
    def _on_error(self, error):
        """Handle error signal (called on UI thread)
        
        Args:
            error: Error information dictionary
        """
        severity = error.get("severity", "error")
        message = error.get("message", "Unknown error")
        source = error.get("source", "")
        
        # Show different icon depending on severity
        if severity == "critical" or severity == "emergency":
            icon = QMessageBox.Critical
        elif severity == "error":
            icon = QMessageBox.Warning
        else:
            icon = QMessageBox.Information
            
        # For emergency errors, show a modal dialog
        if severity == "emergency":
            QMessageBox.critical(self, "Emergency Error", f"{source}: {message}")
        else:
            # Update status bar
            self.status_signal.emit(f"Error: {message}", 5000)
            
            # Log to logger panel if available
            if "logger" in self.panels:
                self.panels["logger"].add_log(f"{severity.upper()}: {source}: {message}")
    
    def _handle_mode_change(self, old_mode, new_mode):
        """Handle mode change notifications
        
        Args:
            old_mode: Previous mode name
            new_mode: New mode name
        """
        # Apply new theme
        self._apply_theme()
        
        # Update status bar
        self.status_signal.emit(f"Switched to {new_mode} mode", 3000)
        
        # Additional mode-specific adjustments can be added here
    
    def update_status(self):
        """Update status information (called periodically)"""
        # Update user info if available
        if self.user_manager:
            user = self.user_manager.get_current_user()
            if user:
                self.user_info.setText(f"User: {user.get('full_name', user.get('username', 'Unknown'))}")
        
        # Other periodic updates can be added here
    
    @pyqtSlot(str, int)
    def _on_status_update(self, message, timeout):
        """Handle status update signal
        
        Args:
            message: Status message
            timeout: Message timeout in milliseconds
        """
        self.status_bar.showMessage(message, timeout)
    
    def _on_new_scenario(self):
        """Handle New Scenario action"""
        # Implementation depends on ScenarioTab
        self.status_signal.emit("Creating new scenario...", 2000)
        
    def _on_open_file(self):
        """Handle Open action"""
        # Show file dialog
        file_types = "All Files (*);;DBC Files (*.dbc);;Scenarios (*.json)"
        file_path, selected_filter = QFileDialog.getOpenFileName(
            self, "Open File", "", file_types
        )
        
        if file_path:
            # Handle based on file type
            if file_path.endswith(".dbc"):
                self._on_load_dbc(file_path)
            elif file_path.endswith(".json"):
                # Handle scenario files
                pass
                
            self.status_signal.emit(f"Opened {os.path.basename(file_path)}", 2000)
    
    def _on_save(self):
        """Handle Save action"""
        # Implementation depends on active tab
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            # Get tab info
            for name, tab_info in self.tabs.items():
                if tab_info["index"] == current_index:
                    # Check if tab widget has save method
                    if hasattr(tab_info["widget"], "save"):
                        tab_info["widget"].save()
                        self.status_signal.emit(f"Saved {name}", 2000)
                    break
    
    def _on_export(self):
        """Handle Export action"""
        # Implementation depends on active tab
        self.status_signal.emit("Export not implemented", 2000)
    
    def _on_settings(self):
        """Handle Settings action"""
        # Show settings dialog
        self.status_signal.emit("Settings not implemented", 2000)
    
    def _on_toggle_fullscreen(self, checked):
        """Handle Fullscreen toggle
        
        Args:
            checked: Whether fullscreen is enabled
        """
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()
    
    def _on_can_monitor(self):
        """Handle CAN Monitor action"""
        # Show CAN monitor tab or dock
        self.status_signal.emit("CAN Monitor not implemented", 2000)
    
    def _on_log_viewer(self):
        """Handle Log Viewer action"""
        # Show log viewer tab or dock
        self.status_signal.emit("Log Viewer not implemented", 2000)
    
    def _on_about(self):
        """Handle About action"""
        # Show about dialog
        app_name = "TFITPICAN"
        version = "0.1.0"
        
        if self.config:
            app_config = self.config.get("app", {})
            app_name = app_config.get("name", app_name)
            version = app_config.get("version", version)
            
        about_text = f"""
        <h1>{app_name}</h1>
        <p>Version: {version}</p>
        <p>Author: Thomas Fischer</p>
        <p>License: MIT</p>
        <p>A CAN bus monitoring and visualization tool.</p>
        """
        
        QMessageBox.about(self, f"About {app_name}", about_text)
    
    def _on_run(self):
        """Handle Run action"""
        # Implementation depends on ScenarioTab
        self.status_signal.emit("Run not implemented", 2000)
    
    def _on_stop(self):
        """Handle Stop action"""
        # Implementation depends on ScenarioTab
        self.status_signal.emit("Stop not implemented", 2000)
    
    def _on_load_dbc(self, file_path=None):
        """Handle Load DBC action
        
        Args:
            file_path: Optional file path (if None, show dialog)
        """
        if file_path is None:
            # Show file dialog
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open DBC File", "", "DBC Files (*.dbc)"
            )
            
        if file_path:
            # Implementation depends on CAN modules
            self.status_signal.emit(f"Loading DBC file: {os.path.basename(file_path)}", 2000)
            
    def closeEvent(self, event):
        """Handle window close event
        
        Args:
            event: Close event
        """
        # Show confirmation dialog
        reply = QMessageBox.question(
            self, 
            "Confirm Exit", 
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clean up resources
            if self.error_manager:
                self.error_manager.unregister_callback(self._handle_error)
                
            if self.mode_manager:
                self.mode_manager.unregister_callback(self._handle_mode_change)
                
            # Stop update timer
            self.update_timer.stop()
            
            event.accept()
        else:
            event.ignore()
        