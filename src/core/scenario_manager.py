#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: scenario_manager.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Scenario management for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Set

class ScenarioManager:
    """Manages the execution of test scenarios"""
    
    def __init__(self, scenario_loader, car_simulator, plugin_manager, sqlite_db=None, error_manager=None):
        self.logger = logging.getLogger("ScenarioManager")
        self.scenario_loader = scenario_loader
        self.car_simulator = car_simulator
        self.plugin_manager = plugin_manager
        self.sqlite_db = sqlite_db
        self.error_manager = error_manager
        
        # Active scenarios
        self.active_scenarios = {}  # scenario_id -> thread
        self.scenario_states = {}   # scenario_id -> state dict
        
        # Lock for thread-safe operations
        self.lock = threading.Lock()
        
        self.logger.info("Scenario manager initialized")
    
    def get_available_scenarios(self) -> List[Dict]:
        """Get list of available scenarios
        
        Returns:
            List of scenario dictionaries
        """
        return self.scenario_loader.get_available_scenarios()
    
    def run_scenario(self, scenario_id: str) -> bool:
        """Run a scenario
        
        Args:
            scenario_id: ID of the scenario to run
            
        Returns:
            bool: True if scenario started successfully
        """
        with self.lock:
            # Check if scenario is already running
            if scenario_id in self.active_scenarios:
                self.logger.warning(f"Scenario {scenario_id} is already running")
                return False
                
            # Load scenario
            scenario_data = self.scenario_loader.load_scenario(scenario_id)
            if not scenario_data:
                self.logger.error(f"Failed to load scenario: {scenario_id}")
                return False
                
            # Initialize scenario state
            self.scenario_states[scenario_id] = {
                "id": scenario_id,
                "name": scenario_data.get("name", scenario_id),
                "start_time": datetime.now().isoformat(),
                "status": "starting",
                "current_step": 0,
                "total_steps": len(scenario_data.get("steps", [])),
                "errors": []
            }
            
            # Log event
            if self.sqlite_db:
                self.sqlite_db.insert(
                    "events",
                    {
                        "timestamp": datetime.now().isoformat(),
                        "event_type": "scenario_start",
                        "event_id": scenario_id,
                        "description": f"Started scenario: {scenario_data.get('name', scenario_id)}"
                    }
                )
                
                # Update scenario stats
                self.sqlite_db.update_scenario_stats(scenario_id)
                
            # Create and start scenario thread
            scenario_thread = threading.Thread(
                target=self._run_scenario_thread,
                args=(scenario_id, scenario_data)
            )
            scenario_thread.daemon = True
            
            self.active_scenarios[scenario_id] = scenario_thread
            scenario_thread.start()
            
            self.logger.info(f"Started scenario: {scenario_id}")
            return True
    
    def _run_scenario_thread(self, scenario_id: str, scenario_data: Dict) -> None:
        """Thread function to run a scenario
        
        Args:
            scenario_id: Scenario ID
            scenario_data: Scenario data dictionary
        """
        try:
            # Start car simulator if it's not already running
            if not self.car_simulator.running:
                self.car_simulator.start()
                
            # Load plugins for this scenario
            loaded_plugins = set()
            if "plugins" in scenario_data:
                for plugin_name in scenario_data["plugins"]:
                    if self.plugin_manager.load_plugin(plugin_name):
                        loaded_plugins.add(plugin_name)
                    else:
                        self._add_scenario_error(
                            scenario_id, 
                            f"Failed to load plugin: {plugin_name}"
                        )
                        
            # Update status
            self._update_scenario_status(scenario_id, "running")
            
            # Get scenario steps
            steps = scenario_data.get("steps", [])
            
            # Execute each step
            for i, step in enumerate(steps):
                # Check if scenario should continue
                if not self._is_scenario_active(scenario_id):
                    break
                    
                # Update current step
                self._update_scenario_step(scenario_id, i)
                
                # Execute step
                try:
                    self._execute_step(scenario_id, step)
                except Exception as e:
                    self._add_scenario_error(
                        scenario_id, 
                        f"Error executing step {i}: {e}"
                    )
                    
                    # Log error
                    self.logger.error(f"Error executing step {i} in scenario {scenario_id}: {e}")
                    if self.error_manager:
                        self.error_manager.report_error(
                            "ScenarioManager", 
                            "step_execution_error", 
                            f"Error executing step {i} in scenario {scenario_id}: {e}",
                            severity="error"
                        )
                    
                    # Stop scenario on error
                    break
                    
            # Set status based on whether all steps completed
            if self._is_scenario_active(scenario_id) and self.scenario_states[scenario_id]["current_step"] >= len(steps):
                self._update_scenario_status(scenario_id, "completed")
            else:
                self._update_scenario_status(scenario_id, "stopped")
                
            # Unload plugins
            for plugin_name in loaded_plugins:
                self.plugin_manager.unload_plugin(plugin_name)
                
            # Log event
            if self.sqlite_db:
                self.sqlite_db.insert(
                    "events",
                    {
                        "timestamp": datetime.now().isoformat(),
                        "event_type": "scenario_end",
                        "event_id": scenario_id,
                        "description": f"Ended scenario: {scenario_data.get('name', scenario_id)}"
                    }
                )
                
                # Log test result
                scenario_state = self.scenario_states.get(scenario_id, {})
                status = scenario_state.get("status", "unknown")
                errors = scenario_state.get("errors", [])
                
                # Calculate duration
                start_time = scenario_state.get("start_time")
                if start_time:
                    start_dt = datetime.fromisoformat(start_time)
                    end_dt = datetime.now()
                    duration = (end_dt - start_dt).total_seconds()
                else:
                    duration = 0
                    
                # Insert test result
                self.sqlite_db.insert(
                    "test_results",
                    {
                        "timestamp": datetime.now().isoformat(),
                        "scenario_id": scenario_id,
                        "status": status,
                        "duration": duration,
                        "results": json.dumps({"errors": errors}),
                        "notes": ""
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Error running scenario {scenario_id}: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "ScenarioManager", 
                    "scenario_execution_error", 
                    f"Error running scenario {scenario_id}: {e}",
                    severity="error"
                )
                
            self._update_scenario_status(scenario_id, "error")
            
        finally:
            # Clean up
            with self.lock:
                if scenario_id in self.active_scenarios:
                    del self.active_scenarios[scenario_id]
    
    def _execute_step(self, scenario_id: str, step: Dict) -> None:
        """Execute a scenario step
        
        Args:
            scenario_id: Scenario ID
            step: Step dictionary
        """
        step_type = step.get("type")
        
        if step_type == "can_message":
            # Send CAN message
            can_id = step.get("id")
            if isinstance(can_id, str):
                can_id = int(can_id, 16) if can_id.startswith("0x") else int(can_id)
                
            data = step.get("data", [])
            extended = step.get("extended", False)
            
            # Send the message
            self.car_simulator.can_manager.send_message(can_id, data, extended)
            
            # Log the message
            if self.sqlite_db:
                self.sqlite_db.insert(
                    "can_messages",
                    {
                        "timestamp": datetime.now().isoformat(),
                        "can_id": hex(can_id) if isinstance(can_id, int) else can_id,
                        "data": " ".join(f"{b:02X}" for b in data),
                        "direction": "outgoing",
                        "scenario_id": scenario_id,
                        "notes": "Scenario step"
                    }
                )
                
            # Optional delay after sending
            if "delay_ms" in step:
                time.sleep(step["delay_ms"] / 1000.0)
                
        elif step_type == "pause":
            # Simple pause
            duration_sec = step.get("duration_sec", 1.0)
            time.sleep(duration_sec)
            
        elif step_type == "plugin_action":
            # Execute plugin action
            plugin_name = step.get("plugin")
            action = step.get("action")
            params = step.get("params", {})
            
            if not plugin_name or not action:
                raise ValueError("Plugin action step missing plugin name or action")
                
            # Execute the action
            result = self.plugin_manager.execute_action(plugin_name, action, params)
            
            # Check result
            if result is None:
                self._add_scenario_error(
                    scenario_id, 
                    f"Plugin action {plugin_name}.{action} failed"
                )
                
        elif step_type == "vehicle_control":
            # Control vehicle state
            control_type = step.get("control")
            value = step.get("value")
            
            if control_type == "engine":
                if value:
                    self.car_simulator.start_engine()
                else:
                    self.car_simulator.stop_engine()
            elif control_type == "throttle":
                self.car_simulator.set_throttle(value)
            elif control_type == "brake":
                self.car_simulator.set_brake(value)
            elif control_type == "gear":
                self.car_simulator.set_gear(value)
            elif control_type == "headlights":
                self.car_simulator.toggle_headlights()
            elif control_type == "indicator_left":
                self.car_simulator.toggle_left_indicator()
            elif control_type == "indicator_right":
                self.car_simulator.toggle_right_indicator()
                
        else:
            self.logger.warning(f"Unknown step type: {step_type}")
    
    def stop_scenario(self, scenario_id: str) -> bool:
        """Stop a running scenario
        
        Args:
            scenario_id: ID of the scenario to stop
            
        Returns:
            bool: True if scenario was stopped
        """
        with self.lock:
            if scenario_id not in self.active_scenarios:
                self.logger.warning(f"Scenario {scenario_id} is not running")
                return False
                
            # Update status
            self._update_scenario_status(scenario_id, "stopping")
            
        # Log event
        if self.sqlite_db:
            self.sqlite_db.insert(
                "events",
                {
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "scenario_stop",
                    "event_id": scenario_id,
                    "description": f"Stopped scenario: {scenario_id}"
                }
            )
            
        self.logger.info(f"Stopping scenario: {scenario_id}")
        return True
    
    def stop_all_scenarios(self) -> None:
        """Stop all running scenarios"""
        with self.lock:
            for scenario_id in list(self.active_scenarios.keys()):
                self.stop_scenario(scenario_id)
    
    def get_scenario_status(self, scenario_id: str) -> Optional[Dict]:
        """Get the current status of a scenario
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            Status dictionary or None if scenario not found
        """
        with self.lock:
            return self.scenario_states.get(scenario_id)
    
    def get_active_scenarios(self) -> List[Dict]:
        """Get list of active scenarios
        
        Returns:
            List of active scenario dictionaries
        """
        with self.lock:
            return [
                self.scenario_states.get(scenario_id, {"id": scenario_id, "status": "unknown"})
                for scenario_id in self.active_scenarios.keys()
            ]
    
    def _update_scenario_status(self, scenario_id: str, status: str) -> None:
        """Update the status of a scenario
        
        Args:
            scenario_id: Scenario ID
            status: New status
        """
        with self.lock:
            if scenario_id in self.scenario_states:
                self.scenario_states[scenario_id]["status"] = status
                
                if status in ("completed", "stopped", "error"):
                    self.scenario_states[scenario_id]["end_time"] = datetime.now().isoformat()
    
    def _update_scenario_step(self, scenario_id: str, step: int) -> None:
        """Update the current step of a scenario
        
        Args:
            scenario_id: Scenario ID
            step: Current step index
        """
        with self.lock:
            if scenario_id in self.scenario_states:
                self.scenario_states[scenario_id]["current_step"] = step
    
    def _add_scenario_error(self, scenario_id: str, error: str) -> None:
        """Add an error to a scenario
        
        Args:
            scenario_id: Scenario ID
            error: Error message
        """
        with self.lock:
            if scenario_id in self.scenario_states:
                if "errors" not in self.scenario_states[scenario_id]:
                    self.scenario_states[scenario_id]["errors"] = []
                    
                self.scenario_states[scenario_id]["errors"].append({
                    "time": datetime.now().isoformat(),
                    "message": error
                })
    
    def _is_scenario_active(self, scenario_id: str) -> bool:
        """Check if a scenario is still active
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            bool: True if scenario is active
        """
        with self.lock:
            if scenario_id not in self.scenario_states:
                return False
                
            status = self.scenario_states[scenario_id]["status"]
            return status in ("starting", "running") and scenario_id in self.active_scenarios