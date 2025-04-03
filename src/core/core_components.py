#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: core_components.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Core component classes for the TFITPICAN dashboard application
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/tfitpican.log"),
        logging.StreamHandler()
    ]
)

class ScenarioManager:
    """Manages the execution of test scenarios"""
    
    def __init__(self, config_path: str = "config/config.json"):
        self.logger = logging.getLogger("ScenarioManager")
        self.config = self._load_config(config_path)
        self.scenarios = {}
        self.active_scenario = None
        self.car_simulator = CarSimulator()
        self.plugin_manager = PluginManager()
        self.sqlite_logger = SQLiteLogger()
        
        # Load available scenarios
        self._load_scenarios()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
            
    def _load_scenarios(self) -> None:
        """Load available scenarios from directory"""
        scenario_dir = "config/scenarios"
        if not os.path.exists(scenario_dir):
            os.makedirs(scenario_dir, exist_ok=True)
            # Create sample scenario file
            sample = {
                "id": "sample",
                "name": "Sample Scenario",
                "description": "A sample test scenario",
                "steps": [
                    {"type": "can_message", "id": "0x123", "data": [0x01, 0x02, 0x03], "delay_ms": 100},
                    {"type": "can_message", "id": "0x456", "data": [0x04, 0x05, 0x06], "delay_ms": 200},
                ]
            }
            with open(os.path.join(scenario_dir, "sample.json"), 'w') as f:
                json.dump(sample, f, indent=2)
        
        # Load all scenario files
        try:
            for filename in os.listdir(scenario_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(scenario_dir, filename), 'r') as f:
                        scenario = json.load(f)
                        self.scenarios[scenario.get("id")] = scenario
            
            self.logger.info(f"Loaded {len(self.scenarios)} scenarios")
        except Exception as e:
            self.logger.error(f"Error loading scenarios: {e}")
            
    def get_available_scenarios(self) -> List[Dict]:
        """Get list of available scenarios"""
        return [
            {"id": s_id, "name": s.get("name"), "description": s.get("description")}
            for s_id, s in self.scenarios.items()
        ]
        
    def get_available_roles(self) -> List[str]:
        """Get list of available roles for the active scenario"""
        if not self.active_scenario:
            return []
            
        # Extract unique roles from scenario
        roles = set()
        scenario = self.scenarios.get(self.active_scenario, {})
        
        for step in scenario.get("steps", []):
            if "role" in step:
                roles.add(step["role"])
                
        return list(roles)
        
    def run_scenario(self, scenario_id: str) -> bool:
        """Run a specific scenario"""
        if scenario_id not in self.scenarios:
            self.logger.error(f"Scenario '{scenario_id}' not found")
            return False
            
        scenario = self.scenarios[scenario_id]
        self.active_scenario = scenario_id
        
        self.logger.info(f"Starting scenario: {scenario['name']}")
        self.sqlite_logger.log_event("scenario_start", scenario_id, scenario['name'])
        
        # Start car simulator
        self.car_simulator.start()
        
        # Load plugins for scenario
        if "plugins" in scenario:
            for plugin in scenario["plugins"]:
                self.plugin_manager.load_plugin(plugin)
                
        # Execute scenario steps
        try:
            for step in scenario.get("steps", []):
                step_type = step.get("type")
                
                if step_type == "can_message":
                    # Send CAN message
                    can_id = int(step["id"], 16) if isinstance(step["id"], str) else step["id"]
                    self.car_simulator.can_manager.send_message(can_id, step["data"])
                    
                    # Log step
                    self.sqlite_logger.log_can_message(can_id, step["data"], "outgoing", scenario_id)
                    
                    # Optional delay
                    if "delay_ms" in step:
                        time.sleep(step["delay_ms"] / 1000.0)
                        
                elif step_type == "pause":
                    # Simple pause
                    time.sleep(step.get("duration_sec", 1))
                    
                elif step_type == "plugin_action":
                    # Execute plugin action
                    plugin_name = step.get("plugin")
                    action = step.get("action")
                    params = step.get("params", {})
                    
                    self.plugin_manager.execute_action(plugin_name, action, params)
                    
                else:
                    self.logger.warning(f"Unknown step type: {step_type}")
                    
            self.logger.info(f"Scenario '{scenario['name']}' completed successfully")
            self.sqlite_logger.log_event("scenario_complete", scenario_id, scenario['name'])
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing scenario: {e}")
            self.sqlite_logger.log_error("scenario_error", str(e), scenario_id)
            self.stop_scenario()
            return False
            
    def stop_scenario(self) -> None:
        """Stop the active scenario"""
        if not self.active_scenario:
            return
            
        scenario_id = self.active_scenario
        self.active_scenario = None
        
        # Stop car simulator
        self.car_simulator.stop()
        
        # Unload plugins
        self.plugin_manager.unload_all_plugins()
        
        self.logger.info(f"Scenario '{scenario_id}' stopped")
        self.sqlite_logger.log_event("scenario_stop", scenario_id)


class CarSimulator:
    """Simulates vehicle behavior and manages CAN communication"""
    
    def __init__(self):
        self.logger = logging.getLogger("CarSimulator")
        self.running = False
        self.can_manager = CANManager()
        self.error_manager = ErrorManager()
        self.simulation_thread = None
        
    def start(self) -> bool:
        """Start the car simulator"""
        if self.running:
            self.logger.warning("Car simulator already running")
            return False
            
        self.running = True
        self.can_manager.connect()
        
        # Start simulation in a separate thread
        self.simulation_thread = threading.Thread(target=self._simulation_loop)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        
        self.logger.info("Car simulator started")
        return True
        
    def stop(self) -> None:
        """Stop the car simulator"""
        if not self.running:
            return
            
        self.running = False
        
        # Wait for simulation thread to end
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
            
        # Disconnect CAN
        self.can_manager.disconnect()
        
        self.logger.info("Car simulator stopped")
        
    def emergency_stop(self) -> None:
        """Emergency stop - immediately halt all operations"""
        self.logger.warning("EMERGENCY STOP triggered")
        
        # Set emergency error
        self.error_manager.report_error("emergency_stop", "Emergency stop triggered", severity="critical")
        
        # Stop simulator
        self.stop()
        
    def _simulation_loop(self) -> None:
        """Main simulation loop"""
        self.logger.info("Simulation loop started")
        
        while self.running:
            try:
                # Process incoming CAN messages
                messages = self.can_manager.receive_messages()
                for msg in messages:
                    self._process_message(msg)
                    
                # Sleep to prevent CPU overload
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"Error in simulation loop: {e}")
                self.error_manager.report_error("simulation_error", str(e))
                time.sleep(1.0)  # Delay before retry
                
        self.logger.info("Simulation loop ended")
        
    def _process_message(self, message: Dict) -> None:
        """Process an incoming CAN message"""
        # This would implement vehicle behavior logic based on CAN messages
        pass


class CANManager:
    """Manages CAN bus communication"""
    
    def __init__(self, config_path: str = "config/config.json"):
        self.logger = logging.getLogger("CANManager")
        self.config = self._load_config(config_path)
        self.can_interface = None
        self.connected = False
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
            
    def connect(self) -> bool:
        """Connect to CAN interface"""
        if self.connected:
            return True
            
        can_config = self.config.get("can", {})
        interface_type = can_config.get("interface", "socketcan")
        
        try:
            # Create appropriate CAN interface
            if interface_type == "virtual":
                self.can_interface = VirtualCAN()
            else:
                self.can_interface = HardwareCAN(
                    interface=interface_type,
                    channel=can_config.get("channel", "can0"),
                    bitrate=can_config.get("bitrate", 500000)
                )
                
            # Connect to interface
            result = self.can_interface.connect()
            