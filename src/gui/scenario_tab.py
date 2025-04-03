#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: scenario_tab.py
# Pathname: src/gui/
# Description: Scenario management tab for the TFITPICAN application
# -----------------------------------------------------------------------------

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union, Callable

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QToolBar, 
                                QAction, QTableWidget, QTableWidgetItem, QPushButton, 
                                QLabel, QTextEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
                                QHeaderView, QMenu, QMessageBox, QDialog, QDialogButtonBox,
                                QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
                                QListWidget, QListWidgetItem, QGroupBox, QCheckBox,
                                QFileDialog, QInputDialog)
    from PyQt5.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QIcon, QFont, QColor, QBrush
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

class ScenarioTab(QWidget):
    """Scenario management tab for TFITPICAN"""
    
    # Signal for scenario events
    scenario_signal = pyqtSignal(str, dict)  # event_type, data
    
    def __init__(self, scenario_manager=None, scenario_loader=None, car_simulator=None, 
                sqlite_logger=None, translation_manager=None, error_manager=None):
        """Initialize the scenario tab
        
        Args:
            scenario_manager: Scenario manager instance
            scenario_loader: Scenario loader instance
            car_simulator: Car simulator instance
            sqlite_logger: SQLite logger instance
            translation_manager: Translation manager instance
            error_manager: Error manager instance
        """
        if not GUI_AVAILABLE:
            raise ImportError("PyQt5 is required for the GUI")
            
        super().__init__()
        
        self.logger = logging.getLogger("ScenarioTab")
        self.scenario_manager = scenario_manager
        self.scenario_loader = scenario_loader
        self.car_simulator = car_simulator
        self.sqlite_logger = sqlite_logger
        self.translation_manager = translation_manager
        self.error_manager = error_manager
        
        # Current scenario being edited
        self.current_scenario = None
        self.current_scenario_path = None
        self.scenario_modified = False
        
        # Setup UI
        self._setup_ui()
        
        # Load available scenarios
        self._load_scenarios()
        
        # Set up update timer
        self._setup_timer()
        
        self.logger.info("Scenario tab initialized")
    
    def _setup_ui(self):
        """Set up the tab's user interface"""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(24, 24))
        
        # New scenario button
        self.new_action = QAction("New", self)
        self.new_action.triggered.connect(self._on_new)
        if os.path.exists("assets/new.png"):
            self.new_action.setIcon(QIcon("assets/new.png"))
        self.toolbar.addAction(self.new_action)
        
        # Load scenario button
        self.load_action = QAction("Load", self)
        self.load_action.triggered.connect(self._on_load)
        if os.path.exists("assets/open.png"):
            self.load_action.setIcon(QIcon("assets/open.png"))
        self.toolbar.addAction(self.load_action)
        
        # Save scenario button
        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self._on_save)
        if os.path.exists("assets/save.png"):
            self.save_action.setIcon(QIcon("assets/save.png"))
        self.toolbar.addAction(self.save_action)
        
        self.toolbar.addSeparator()
        
        # Run scenario button
        self.run_action = QAction("Run", self)
        self.run_action.triggered.connect(self._on_run)
        if os.path.exists("assets/run.png"):
            self.run_action.setIcon(QIcon("assets/run.png"))
        self.toolbar.addAction(self.run_action)
        
        # Stop scenario button
        self.stop_action = QAction("Stop", self)
        self.stop_action.triggered.connect(self._on_stop)
        if os.path.exists("assets/stop.png"):
            self.stop_action.setIcon(QIcon("assets/stop.png"))
        self.toolbar.addAction(self.stop_action)
        
        self.toolbar.addSeparator()
        
        # Scenario selector
        self.scenario_selector = QComboBox()
        self.scenario_selector.setMinimumWidth(200)
        self.scenario_selector.currentIndexChanged.connect(self._on_scenario_selected)
        self.toolbar.addWidget(self.scenario_selector)
        
        # Add toolbar to layout
        self.layout.addWidget(self.toolbar)
        
        # Create splitter for scenario information and steps
        self.splitter = QSplitter(Qt.Vertical)
        
        # Scenario info panel
        self.info_panel = QWidget()
        self.info_layout = QFormLayout(self.info_panel)
        
        # Scenario name
        self.scenario_name = QLineEdit()
        self.scenario_name.textChanged.connect(self._on_scenario_modified)
        self.info_layout.addRow("Name:", self.scenario_name)
        
        # Scenario description
        self.scenario_description = QTextEdit()
        self.scenario_description.setMaximumHeight(80)
        self.scenario_description.textChanged.connect(self._on_scenario_modified)
        self.info_layout.addRow("Description:", self.scenario_description)
        
        # Scenario steps panel
        self.steps_panel = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_panel)
        
        # Steps table
        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(5)
        self.steps_table.setHorizontalHeaderLabels(["Type", "Details", "Parameters", "Delay", "Notes"])
        self.steps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.steps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.steps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.steps_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.steps_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.steps_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.steps_table.customContextMenuRequested.connect(self._on_steps_context_menu)
        
        self.steps_layout.addWidget(self.steps_table)
        
        # Steps buttons
        steps_buttons_layout = QHBoxLayout()
        
        self.add_step_button = QPushButton("Add Step")
        self.add_step_button.clicked.connect(self._on_add_step)
        steps_buttons_layout.addWidget(self.add_step_button)
        
        self.edit_step_button = QPushButton("Edit Step")
        self.edit_step_button.clicked.connect(self._on_edit_step)
        steps_buttons_layout.addWidget(self.edit_step_button)
        
        self.remove_step_button = QPushButton("Remove Step")
        self.remove_step_button.clicked.connect(self._on_remove_step)
        steps_buttons_layout.addWidget(self.remove_step_button)
        
        self.