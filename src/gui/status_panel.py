#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: status_panel.py
# Pathname: src/gui/
# Description: Status panel for displaying system status information
# -----------------------------------------------------------------------------

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                QLabel, QFrame, QPushButton, QProgressBar,
                                QGroupBox, QToolButton, QTabWidget, QScrollArea,
                                QSpacerItem, QSizePolicy, QMenu, QAction)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize
    from PyQt5.QtGui import QIcon, QFont, QColor, QPalette, QPixmap
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

class StatusWidget(QWidget):
    """Status indicator widget"""
    
    def __init__(self, title: str, parent=None):
        """Initialize the status widget
        
        Args:
            title: Widget title
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(3)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("", 10, QFont.Bold))
        self.layout.addWidget(self.title_label)
        
        # Value
        self.value_label = QLabel("--")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("", 12))
        self.layout.addWidget(self.value_label)
        
        # Status
        self.status_label = QLabel("Unknown")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.status_label)
        
        # Set widget styling
        self.setFrameStyle()
        
        # Initialize to unknown state
        self.set_status("unknown")
        
    def setFrameStyle(self, color=None):
        """Set the frame style
        
        Args:
            color: Optional color for the frame
        """
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        
        if color:
            palette = self.palette()
            palette.setColor(QPalette.Window, color)
            self.setPalette(palette)
            self.setAutoFillBackground(True)
    
    def set_value(self, value):
        """Set the value text
        
        Args:
            value: Value to display
        """
        self.value_label.setText(str(value))
    
    def set_status(self, status: str):
        """Set the status
        
        Args:
            status: Status text
        """
        self.status_label.setText(status.capitalize())
        
        # Set color based on status
        if status == "ok" or status == "active" or status == "connected":
            color = QColor(200, 255, 200)  # Light green
            self.status_label.setStyleSheet("color: green;")
        elif status == "warning":
            color = QColor(255, 255, 200)  # Light yellow
            self.status_label.setStyleSheet("color: orange;")
        elif status == "error" or status == "critical":
            color = QColor(255, 200, 200)  # Light red
            self.status_label.setStyleSheet("color: red;")
        elif status == "inactive" or status == "disabled":
            color = QColor(230, 230, 230)  # Light gray
            self.status_label.setStyleSheet("color: gray;")
        else:
            color = QColor(240, 240, 240)  # Default color
            self.status_label.setStyleSheet("color: black;")
            
        self.setFrameStyle(color)

class StatusPanel(QWidget):
    """Status panel for displaying system status information"""
    
    # Signal for status clicks
    status_clicked = pyqtSignal(str, str)  # component, action
    
    def __init__(self, can_manager=None, car_simulator=None, scenario_manager=None,
                bluetooth_comm=None, sqlite_db=None, error_manager=None,
                translation_manager=None):
        """Initialize the status panel
        
        Args:
            can_manager: CAN manager instance
            car_simulator: Car simulator instance
            scenario_manager: Scenario manager instance
            bluetooth_comm: Bluetooth communication instance
            sqlite_db: SQLite database instance
            error_manager: Error manager instance
            translation_manager: Translation manager instance
        """
        if not GUI_AVAILABLE:
            raise ImportError("PyQt5 is required for the GUI")
            
        super().__init__()
        
        self.logger = logging.getLogger("StatusPanel")
        self.can_manager = can_manager
        self.car_simulator = car_simulator
        self.scenario_manager = scenario_manager
        self.bluetooth_comm = bluetooth_comm
        self.sqlite_db = sqlite_db
        self.error_manager = error_manager
        self.translation_manager = translation_manager
        
        # Status blocks for each component
        self.status_blocks = {}
        
        # Set up UI
        self._setup_ui()
        
        # Set up timer for periodic updates
        self._setup_timer()
        
        self.logger.info("Status panel initialized")
    
    def _setup_ui(self):
        """Set up the user interface"""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Scroll container widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        
        # System status group
        system_group = QGroupBox("System Status")
        system_layout = QGridLayout(system_group)
        system_layout.setSpacing(10)
        
        # Add system status widgets
        # CAN status
        self.status_blocks["can"] = StatusWidget("CAN")
        system_layout.addWidget(self.status_blocks["can"], 0, 0)
        
        # Database status
        self.status_blocks["database"] = StatusWidget("Database")
        system_layout.addWidget(self.status_blocks["database"], 0, 1)
        
        # Bluetooth status
        self.status_blocks["bluetooth"] = StatusWidget("Bluetooth")
        system_layout.addWidget(self.status_blocks["bluetooth"], 0, 2)
        
        # Add system group to layout
        scroll_layout.addWidget(system_group)
        
        # Vehicle status group
        vehicle_group = QGroupBox("Vehicle Status")
        vehicle_layout = QGridLayout(vehicle_group)
        vehicle_layout.setSpacing(10)
        
        # Add vehicle status widgets
        # Engine status
        self.status_blocks["engine"] = StatusWidget("Engine")
        vehicle_layout.addWidget(self.status_blocks["engine"], 0, 0)
        
        # Speed
        self.status_blocks["speed"] = StatusWidget("Speed")
        vehicle_layout.addWidget(self.status_blocks["speed"], 0, 1)
        
        # RPM
        self.status_blocks["rpm"] = StatusWidget("RPM")
        vehicle_layout.addWidget(self.status_blocks["rpm"], 0, 2)
        
        # Gear
        self.status_blocks["gear"] = StatusWidget("Gear")
        vehicle_layout.addWidget(self.status_blocks["gear"], 1, 0)
        
        # Throttle
        self.status_blocks["throttle"] = StatusWidget("Throttle")
        vehicle_layout.addWidget(self.status_blocks["throttle"], 1, 1)
        
        # Brake
        self.status_blocks["brake"] = StatusWidget("Brake")
        vehicle_layout.addWidget(self.status_blocks["brake"], 1, 2)
        
        # Add vehicle group to layout
        scroll_layout.addWidget(vehicle_group)
        
        # Scenario status group
        scenario_group = QGroupBox("Scenario Status")
        scenario_layout = QGridLayout(scenario_group)
        scenario_layout.setSpacing(10)
        
        # Add scenario status widgets
        # Current scenario
        self.status_blocks["scenario"] = StatusWidget("Current Scenario")
        scenario_layout.addWidget(self.status_blocks["scenario"], 0, 0)
        
        # Scenario status
        self.status_blocks["scenario_status"] = StatusWidget("Status")
        scenario_layout.addWidget(self.status_blocks["scenario_status"], 0, 1)
        
        # Progress
        self.status_blocks["progress"] = StatusWidget("Progress")
        scenario_layout.addWidget(self.status_blocks["progress"], 0, 2)
        
        # Add scenario group to layout
        scroll_layout.addWidget(scenario_group)
        
        # Error status group
        error_group = QGroupBox("Error Status")
        error_layout = QGridLayout(error_group)
        error_layout.setSpacing(10)
        
        # Add error status widgets
        # Active errors
        self.status_blocks["errors"] = StatusWidget("Active Errors")
        error_layout.addWidget(self.status_blocks["errors"], 0, 0)
        
        # Last error
        self.status_blocks["last_error"] = StatusWidget("Last Error")
        error_layout.addWidget(self.status_blocks["last_error"], 0, 1)
        
        # Add error group to layout
        scroll_layout.addWidget(error_group)
        
        # Add spacer at the bottom
        scroll_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Set scroll widget to scroll area
        scroll_area.setWidget(scroll_widget)
        
        # Add scroll area to main layout
        self.layout.addWidget(scroll_area)
        
        # Enable context menu for all status widgets
        for block_id, widget in self.status_blocks.items():
            widget.setContextMenuPolicy(Qt.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, b=block_id: self._show_context_menu(pos, b)
            )
            
            # Make clickable
            widget.mousePressEvent = lambda event, b=block_id: self._handle_click(event, b)
    
    def _setup_timer(self):
        """Set up timer for periodic updates"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(1000)  # Update every second
    
    def _update_status(self):
        """Update status information"""
        # Update system status
        self._update_system_status()
        
        # Update vehicle status
        self._update_vehicle_status()
        
        # Update scenario status
        self._update_scenario_status()
        
        # Update error status
        self._update_error_status()
    
    def _update_system_status(self):
        """Update system component status"""
        # CAN status
        if self.can_manager:
            connected = self.can_manager.connected
            if connected:
                self.status_blocks["can"].set_value("Connected")
                self.status_blocks["can"].set_status("ok")
            else:
                self.status_blocks["can"].set_value("Disconnected")
                self.status_blocks["can"].set_status("inactive")
        else:
            self.status_blocks["can"].set_value("Not Available")
            self.status_blocks["can"].set_status("unknown")
            
        # Database status
        if self.sqlite_db:
            self.status_blocks["database"].set_value("Connected")
            self.status_blocks["database"].set_status("ok")
        else:
            self.status_blocks["database"].set_value("Not Available")
            self.status_blocks["database"].set_status("unknown")
            
        # Bluetooth status
        if self.bluetooth_comm:
            devices = len(self.bluetooth_comm.get_connected_devices())
            if devices > 0:
                self.status_blocks["bluetooth"].set_value(f"{devices} Device(s)")
                self.status_blocks["bluetooth"].set_status("connected")
            else:
                self.status_blocks["bluetooth"].set_value("No Devices")
                self.status_blocks["bluetooth"].set_status("inactive")
        else:
            self.status_blocks["bluetooth"].set_value("Not Available")
            self.status_blocks["bluetooth"].set_status("unknown")
    
    def _update_vehicle_status(self):
        """Update vehicle status information"""
        if self.car_simulator:
            # Get vehicle state
            vehicle_state = self.car_simulator.get_vehicle_state()
            
            # Engine status
            engine_running = vehicle_state.get("engine_running", False)
            if engine_running:
                self.status_blocks["engine"].set_value("Running")
                self.status_blocks["engine"].set_status("active")
            else:
                self.status_blocks["engine"].set_value("Off")
                self.status_blocks["engine"].set_status("inactive")
                
            # Speed
            speed = vehicle_state.get("vehicle_speed", 0)
            self.status_blocks["speed"].set_value(f"{speed:.1f} km/h")
            if speed > 0:
                self.status_blocks["speed"].set_status("active")
            else:
                self.status_blocks["speed"].set_status("inactive")
                
            # RPM
            rpm = vehicle_state.get("engine_rpm", 0)
            self.status_blocks["rpm"].set_value(f"{rpm}")
            if rpm > 0:
                self.status_blocks["rpm"].set_status("active")
            else:
                self.status_blocks["rpm"].set_status("inactive")
                
            # Gear
            gear = vehicle_state.get("gear", 0)
            gear_labels = {0: "P", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "R"}
            self.status_blocks["gear"].set_value(gear_labels.get(gear, "?"))
            self.status_blocks["gear"].set_status("ok")
                
            # Throttle
            throttle = vehicle_state.get("throttle_position", 0)
            self.status_blocks["throttle"].set_value(f"{throttle}%")
            if throttle > 0:
                self.status_blocks["throttle"].set_status("active")
            else:
                self.status_blocks["throttle"].set_status("inactive")
                
            # Brake
            brake = vehicle_state.get("brake_pressure", 0)
            self.status_blocks["brake"].set_value(f"{brake}%")
            if brake > 0:
                self.status_blocks["brake"].set_status("active")
            else:
                self.status_blocks["brake"].set_status("inactive")
        else:
            # No simulator available, set default values
            for block in ["engine", "speed", "rpm", "gear", "throttle", "brake"]:
                self.status_blocks[block].set_value("--")
                self.status_blocks[block].set_status("unknown")
    
    def _update_scenario_status