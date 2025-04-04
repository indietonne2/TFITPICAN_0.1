#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.1
# License: MIT
# Filename: tfitpican_main.py
# Pathname: /path/to/tfitpican/
# Description: Main application entry point for TFITPICAN dashboard that 
#              integrates CAN-Bus data, processes DBC messages, and visualizes 
#              data in Grafana using SQLite as the backend
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Ensure src directory is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import components
from src.core.error_manager import ErrorManager
from src.db.sqlite_db import SQLiteDB
from src.db.grafana_adapter import GrafanaAdapter
from src.core.scenario_loader import ScenarioLoader
from src.core.role_manager import RoleManager
from src.comm.bluetooth_comm import BluetoothComm
from src.core.car_simulator import CarSimulator
from src.core.scenario_manager import ScenarioManager
from src.core.plugin_manager import PluginManager
from src.can.can_manager import CANManager

# GUI imports (conditional)
try:
    from src.gui.dashboard_ui import TFITPICANDashboard
    from PyQt5.QtWidgets import QApplication
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

class TFITPICANApp:
    """Main application class for TFITPICAN dashboard"""
    
    def __init__(self, config_path='config/config.json', headless=False):
        # Setup basic logging
        self._setup_basic_logging()
        
        self.logger = logging.getLogger("TFITPICANApp")
        self.logger.info("Starting TFITPICAN application...")
        
        # Store startup parameters
        self.config_path = config_path
        self.headless = headless
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize flag
        self.running = False
        self.gui_app = None
        self.gui_window = None
        
        # Initialize components (order matters)
        self._init_components()
        
        self.logger.info("TFITPICAN application initialized")
    
    def _setup_basic_logging(self):
        """Set up basic logging configuration"""
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"{log_dir}/tfitpican_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                self.logger.info(f"Configuration loaded from {config_path}")
                return config
            else:
                self.logger.warning(f"Configuration file {config_path} not found, using defaults")
                return self._create_default_config(config_path)
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return self._create_default_config(config_path)
    
    def _create_default_config(self, config_path: str) -> Dict:
        """Create and save default configuration"""
        # Default configuration
        config = {
            "app": {
                "name": "TFITPICAN",
                "version": "0.1.1",
                "author": "Thomas Fischer",
                "license": "MIT"
            },
            "can": {
                "interface": "socketcan" if self._is_raspberry_pi() else "virtual",
                "channel": "can0" if self._is_raspberry_pi() else "vcan0",
                "bitrate": 500000,
                "enable_auto_restart": True
            },
            "database": {
                "type": "sqlite",
                "path": "db/tfitpican.db",
                "backup_enabled": True,
                "backup_interval_hours": 24
            },
            "grafana": {
                "url": "http://localhost:3000",
                "dashboard_uid": "canbus-dashboard",
                "api_key": "",
                "username": "admin",
                "password": "admin"
            },
            "ui": {
                "fullscreen": False,
                "theme": "dark",
                "refresh_rate_ms": 500,
                "show_raw_data": True
            },
            "bluetooth": {
                "enabled": True,
                "device_name": "TFITPICAN",
                "pin": "1234"
            },
            "logging": {
                "level": "INFO",
                "file_enabled": True,
                "log_dir": "logs",
                "max_size_mb": 10,
                "backup_count": 5
            }
        }
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Save default config
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            self.logger.info(f"Default configuration saved to {config_path}")
        except Exception as e:
            self.logger.error(f"Error saving default configuration: {e}")
        
        return config
    
    def _is_raspberry_pi(self) -> bool:
        """Detect if running on a Raspberry Pi"""
        try:
            with open('/sys/firmware/devicetree/base/model', 'r') as m:
                if 'raspberry pi' in m.read().lower():
                    return True
        except:
            pass
        return False
    
    def _init_components(self):
        """Initialize all application components"""
        try:
            # First - Error Manager (needed by all other components)
            self.error_manager = ErrorManager(self.config_path)
            
            # Database components
            self.sqlite_db = SQLiteDB(
                self.config.get("database", {}).get("path", "db/tfitpican.db"),
                self.error_manager
            )
            
            # Grafana adapter for visualization (using SQLite)
            self.grafana_adapter = GrafanaAdapter(
                self.config_path, 
                self.sqlite_db,  # Pass SQLite instance
                self.error_manager
            )
            
            # Core components
            self.scenario_loader = ScenarioLoader(
                "config/scenarios", 
                self.sqlite_db, 
                self.error_manager
            )
            
            self.role_manager = RoleManager(
                self.config_path,
                self.sqlite_db,
                self.error_manager
            )
            
            # Communication
            self.bluetooth_comm = BluetoothComm(self.config_path, self.error_manager)
            
            # Plugin system
            self.plugin_manager = PluginManager(
                "plugins",
                self.error_manager
            )
            
            # CAN system
            self.can_manager = CANManager(self.config_path, self.error_manager)
            
            # Car simulator
            self.car_simulator = CarSimulator(
                self.can_manager,
                self.error_manager
            )
            
            # Scenario manager (depends on simulator, plugins, etc.)
            self.scenario_manager = ScenarioManager(
                self.scenario_loader,
                self.car_simulator,
                self.plugin_manager,
                self.sqlite_db,
                self.error_manager
            )
            
            # Register error callback to handle critical errors
            self.error_manager.register_callback(self._handle_error)
            
        except Exception as e:
            self.logger.critical(f"Error initializing components: {e}")
            raise
    
    def _handle_error(self, error: Dict):
        """Handle errors from the error manager"""
        severity = error.get("severity", "")
        
        # Handle emergency shutdown
        if severity == "emergency" or error.get("action") == "emergency_shutdown":
            self.logger.critical("Emergency shutdown triggered")
            self.stop()
    
    def _setup_gui(self):
        """Set up the GUI application"""
        if not GUI_AVAILABLE or self.headless:
            return False
        
        try:
            # Create QApplication
            self.gui_app = QApplication([])
            
            # Create main window
            self.gui_window = TFITPICANDashboard(
                self.config,
                self.error_manager,
                self.scenario_manager,
                self.can_manager,
                self.sqlite_db,
                self.bluetooth_comm,
                self.role_manager
            )
            
            # Show the window
            self.gui_window.show()
            
            return True
        except Exception as e:
            self.logger.error(f"Error setting up GUI: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "TFITPICANApp", 
                    "gui_setup_error", 
                    f"Error setting up GUI: {e}",
                    severity="error"
                )
            return False
    
    def start(self):
        """Start the application"""
        if self.running:
            self.logger.warning("Application already running")
            return
        
        self.running = True
        self.logger.info("Starting TFITPICAN components...")
        
        try:
            # Start Bluetooth if enabled
            if self.config.get("bluetooth", {}).get("enabled", True):
                self.bluetooth_comm.start_pairing()
            
            # Connect to CAN bus
            self.can_manager.connect()
            
            # Configure Grafana for SQLite if needed
            self.grafana_adapter.configure_grafana_sqlite_datasource()
            
            # Start GUI if available and not in headless mode
            gui_started = self._setup_gui()
            
            if gui_started:
                # Run the Qt event loop
                self.logger.info("Starting GUI event loop")
                self.gui_app.exec_()
                # When the event loop ends, stop the application
                self.stop()
            else:
                self.logger.info("Running in headless mode")
                # In headless mode, just keep the main thread alive
                while self.running:
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
            self.stop()
        except Exception as e:
            self.logger.critical(f"Error in main loop: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "TFITPICANApp", 
                    "main_loop_error", 
                    f"Error in main loop: {e}",
                    severity="critical"
                )
            self.stop()
    
    def stop(self):
        """Stop the application"""
        if not self.running:
            return
        
        self.running = False
        self.logger.info("Stopping TFITPICAN application...")
        
        # Stop all active scenarios
        if hasattr(self, 'scenario_manager'):
            self.scenario_manager.stop_all_scenarios()
        
        # Disconnect CAN manager
        if hasattr(self, 'can_manager'):
            self.can_manager.disconnect()
        
        # Stop Bluetooth
        if hasattr(self, 'bluetooth_comm'):
            self.bluetooth_comm.stop()
        
        # Close database connections
        if hasattr(self, 'sqlite_db'):
            self.sqlite_db.close()
        
        # Stop error manager
        if hasattr(self, 'error_manager'):
            self.error_manager.stop()
        
        self.logger.info("TFITPICAN application stopped")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="TFITPICAN - CAN Bus Monitoring Tool")
    
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/config.json",
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--headless", 
        action="store_true",
        help="Run in headless mode (no GUI)"
    )
    
    parser.add_argument(
        "--version", 
        action="version",
        version="TFITPICAN 0.1.1"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    try:
        # Create and start the application
        app = TFITPICANApp(args.config, args.headless)
        app.start()
    except Exception as e:
        logging.critical(f"Unhandled exception in main: {e}", exc_info=True)
        sys.exit(1)
