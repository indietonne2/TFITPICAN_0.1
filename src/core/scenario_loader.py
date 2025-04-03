#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: scenario_loader.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Scenario loading and validation for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import logging
import glob
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

class ScenarioLoader:
    """Responsible for loading and validating test scenarios"""
    
    def __init__(self, scenario_dir: str = "config/scenarios", sqlite_db=None, error_manager=None):
        self.logger = logging.getLogger("ScenarioLoader")
        self.scenario_dir = scenario_dir
        self.sqlite_db = sqlite_db
        self.error_manager = error_manager
        
        # Cache of loaded scenarios
        self.scenarios = {}
        
        # Ensure directory exists
        os.makedirs(scenario_dir, exist_ok=True)
        
        # Load scenarios
        self.load_all_scenarios()
        
    def load_all_scenarios(self) -> Dict[str, Dict]:
        """Load all scenario files from the scenario directory
        
        Returns:
            Dictionary of scenario_id -> scenario_data
        """
        self.scenarios = {}
        
        # Load from filesystem
        scenario_files = glob.glob(os.path.join(self.scenario_dir, "*.json"))
        
        for file_path in scenario_files:
            try:
                with open(file_path, 'r') as f:
                    scenario_data = json.load(f)
                    
                # Get scenario ID
                scenario_id = scenario_data.get("id")
                if not scenario_id:
                    # Use filename as ID if not specified
                    scenario_id = os.path.splitext(os.path.basename(file_path))[0]
                    scenario_data["id"] = scenario_id
                    
                # Validate scenario structure
                validation_result = self.validate_scenario(scenario_data)
                if validation_result["valid"]:
                    self.scenarios[scenario_id] = scenario_data
                    
                    # Register with database if available
                    if self.sqlite_db:
                        self._register_scenario_in_db(scenario_id, scenario_data, file_path)
                        
                else:
                    self.logger.warning(f"Invalid scenario in {file_path}: {validation_result['errors']}")
                    if self.error_manager:
                        self.error_manager.report_error(
                            "ScenarioLoader", 
                            "invalid_scenario", 
                            f"Invalid scenario in {file_path}: {validation_result['errors']}",
                            severity="warning"
                        )
                    
            except Exception as e:
                self.logger.error(f"Error loading scenario file {file_path}: {e}")
                if self.error_manager:
                    self.error_manager.report_error(
                        "ScenarioLoader", 
                        "scenario_load_error", 
                        f"Error loading scenario file {file_path}: {e}",
                        severity="error"
                    )
                    
        self.logger.info(f"Loaded {len(self.scenarios)} scenarios")
        return self.scenarios
        
    def _register_scenario_in_db(self, scenario_id: str, scenario_data: Dict, file_path: str) -> None:
        """Register a scenario in the database
        
        Args:
            scenario_id: Scenario ID
            scenario_data: Scenario data
            file_path: Path to scenario file
        """
        try:
            # Check if scenario exists in DB
            existing = self.sqlite_db.query(
                "SELECT id FROM scenarios WHERE scenario_id = ?",
                (scenario_id,),
                fetch_all=False
            )
            
            if existing:
                # Update existing record
                self.sqlite_db.update(
                    "scenarios",
                    {
                        "name": scenario_data.get("name", scenario_id),
                        "description": scenario_data.get("description", ""),
                        "config_path": file_path
                    },
                    "scenario_id = ?",
                    (scenario_id,)
                )
            else:
                # Insert new record
                self.sqlite_db.insert(
                    "scenarios",
                    {
                        "scenario_id": scenario_id,
                        "name": scenario_data.get("name", scenario_id),
                        "description": scenario_data.get("description", ""),
                        "config_path": file_path,
                        "last_run": None,
                        "run_count": 0
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Error registering scenario in database: {e}")
        
    def load_scenario(self, scenario_id: str) -> Optional[Dict]:
        """Load a specific scenario
        
        Args:
            scenario_id: ID of the scenario to load
            
        Returns:
            Scenario data dictionary or None if not found
        """
        # Check if already loaded
        if scenario_id in self.scenarios:
            return self.scenarios[scenario_id]
            
        # Try to load from file
        try:
            file_path = os.path.join(self.scenario_dir, f"{scenario_id}.json")
            if not os.path.exists(file_path):
                # Try to find by ID in other filenames
                scenario_files = glob.glob(os.path.join(self.scenario_dir, "*.json"))
                for file in scenario_files:
                    try:
                        with open(file, 'r') as f:
                            data = json.load(f)
                            if data.get("id") == scenario_id:
                                file_path = file
                                break
                    except:
                        continue
                        
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    scenario_data = json.load(f)
                    
                # Validate scenario structure
                validation_result = self.validate_scenario(scenario_data)
                if validation_result["valid"]:
                    self.scenarios[scenario_id] = scenario_data
                    return scenario_data
                else:
                    self.logger.warning(f"Invalid scenario {scenario_id}: {validation_result['errors']}")
                    if self.error_manager:
                        self.error_manager.report_error(
                            "ScenarioLoader", 
                            "invalid_scenario", 
                            f"Invalid scenario {scenario_id}: {validation_result['errors']}",
                            severity="warning"
                        )
                    return None
            else:
                # Try database
                if self.sqlite_db:
                    db_scenario = self.sqlite_db.query(
                        "SELECT * FROM scenarios WHERE scenario_id = ?",
                        (scenario_id,),
                        fetch_all=False
                    )
                    
                    if db_scenario and db_scenario.get("config_path"):
                        file_path = db_scenario["config_path"]
                        if os.path.exists(file_path):
                            with open(file_path, 'r') as f:
                                scenario_data = json.load(f)
                                
                            # Validate scenario structure
                            validation_result = self.validate_scenario(scenario_data)
                            if validation_result["valid"]:
                                self.scenarios[scenario_id] = scenario_data
                                return scenario_data
                
                self.logger.warning(f"Scenario {scenario_id} not found")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading scenario {scenario_id}: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "ScenarioLoader", 
                    "scenario_load_error", 
                    f"Error loading scenario {scenario_id}: {e}",
                    severity="error"
                )
            return None
    
    def validate_scenario(self, scenario_data: Dict) -> Dict:
        """Validate scenario structure and requirements
        
        Args:
            scenario_data: Scenario data to validate
            
        Returns:
            Dict with keys:
              - valid: Boolean indicating if scenario is valid
              - errors: List of error messages if invalid
        """
        errors = []
        
        # Check required fields
        required_fields = ["id", "name", "steps"]
        for field in required_fields:
            if field not in scenario_data:
                errors.append(f"Missing required field: {field}")
                
        # Validate steps
        if "steps" in scenario_data:
            steps = scenario_data["steps"]
            if not isinstance(steps, list):
                errors.append("Steps must be a list")
            else:
                for i, step in enumerate(steps):
                    step_errors = self._validate_step(step, i)
                    errors.extend(step_errors)
                    
        # Validate plugins
        if "plugins" in scenario_data:
            plugins = scenario_data["plugins"]
            if not isinstance(plugins, list):
                errors.append("Plugins must be a list")
                
        # Return validation result
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
        
    def _validate_step(self, step: Dict, index: int) -> List[str]:
        """Validate a scenario step
        
        Args:
            step: Step data to validate
            index: Step index for error messages
            
        Returns:
            List of error messages
        """
        errors = []
        
        # Check step type
        if "type" not in step:
            errors.append(f"Step {index}: Missing required field 'type'")
            return errors
            
        step_type = step["type"]
        
        # Validate based on step type
        if step_type == "can_message":
            # Validate CAN message step
            if "id" not in step:
                errors.append(f"Step {index}: CAN message missing required field 'id'")
                
            if "data" not in step:
                errors.append(f"Step {index}: CAN message missing required field 'data'")
            elif not isinstance(step["data"], list):
                errors.append(f"Step {index}: CAN message 'data' must be a list of bytes")
            elif len(step["data"]) > 8:
                errors.append(f"Step {index}: CAN message 'data' cannot exceed 8 bytes")
                
        elif step_type == "pause":
            # Validate pause step
            if "duration_sec" not in step:
                errors.append(f"Step {index}: Pause missing required field 'duration_sec'")
                
        elif step_type == "plugin_action":
            # Validate plugin action step
            if "plugin" not in step:
                errors.append(f"Step {index}: Plugin action missing required field 'plugin'")
                
            if "action" not in step:
                errors.append(f"Step {index}: Plugin action missing required field 'action'")
                
        # Unknown step type is allowed (for custom extensions)
        
        return errors
        
    def get_available_scenarios(self) -> List[Dict]:
        """Get list of available scenarios
        
        Returns:
            List of scenario summary dictionaries
        """
        return [
            {
                "id": scenario_id,
                "name": scenario.get("name", scenario_id),
                "description": scenario.get("description", ""),
                "steps": len(scenario.get("steps", [])),
                "has_plugins": "plugins" in scenario and len(scenario["plugins"]) > 0
            }
            for scenario_id, scenario in self.scenarios.items()
        ]
        
    def save_scenario(self, scenario_data: Dict) -> bool:
        """Save a scenario to file
        
        Args:
            scenario_data: Scenario data to save
            
        Returns:
            bool: True if successful
        """
        # Validate scenario first
        validation_result = self.validate_scenario(scenario_data)
        if not validation_result["valid"]:
            self.logger.warning(f"Cannot save invalid scenario: {validation_result['errors']}")
            return False
            
        scenario_id = scenario_data["id"]
        
        try:
            # Determine file path
            file_path = os.path.join(self.scenario_dir, f"{scenario_id}.json")
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(scenario_data, f, indent=2)
                
            # Update cache
            self.scenarios[scenario_id] = scenario_data
            
            # Register with database if available
            if self.sqlite_db:
                self._register_scenario_in_db(scenario_id, scenario_data, file_path)
                
            self.logger.info(f"Saved scenario {scenario_id} to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving scenario {scenario_id}: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "ScenarioLoader", 
                    "scenario_save_error", 
                    f"Error saving scenario {scenario_id}: {e}",
                    severity="error"
                )
            return False
            
    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario
        
        Args:
            scenario_id: ID of the scenario to delete
            
        Returns:
            bool: True if successful
        """
        try:
            # Determine file path
            file_path = os.path.join(self.scenario_dir, f"{scenario_id}.json")
            
            # Try to find by ID in other filenames if file doesn't exist
            if not os.path.exists(file_path) and scenario_id in self.scenarios:
                # Look in database
                if self.sqlite_db:
                    db_scenario = self.sqlite_db.query(
                        "SELECT config_path FROM scenarios WHERE scenario_id = ?",
                        (scenario_id,),
                        fetch_all=False
                    )
                    
                    if db_scenario and db_scenario.get("config_path"):
                        file_path = db_scenario["config_path"]
                
            # Delete file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
                
            # Remove from cache
            if scenario_id in self.scenarios:
                del self.scenarios[scenario_id]
                
            # Remove from database if available
            if self.sqlite_db:
                self.sqlite_db.delete(
                    "scenarios",
                    "scenario_id = ?",
                    (scenario_id,)
                )
                
            self.logger.info(f"Deleted scenario {scenario_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting scenario {scenario_id}: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "ScenarioLoader", 
                    "scenario_delete_error", 
                    f"Error deleting scenario {scenario_id}: {e}",
                    severity="error"
                )
            return False
            
    def create_sample_scenario(self) -> str:
        """Create a sample scenario file
        
        Returns:
            Scenario ID of created sample
        """
        scenario_id = "sample"
        
        # Check if sample already exists
        if scenario_id in self.scenarios:
            # Create a new ID
            i = 1
            while f"sample_{i}" in self.scenarios:
                i += 1
            scenario_id = f"sample_{i}"
            
        # Create sample scenario
        sample = {
            "id": scenario_id,
            "name": "Sample Scenario",
            "description": "A sample test scenario with various step types",
            "steps": [
                {"type": "can_message", "id": "0x123", "data": [0x01, 0x02, 0x03], "delay_ms": 100},
                {"type": "pause", "duration_sec": 0.5},
                {"type": "can_message", "id": "0x456", "data": [0x04, 0x05, 0x06], "delay_ms": 200},
                {"type": "pause", "duration_sec": 1.0},
                {"type": "can_message", "id": "0x789", "data": [0x07, 0x08, 0x09, 0x0A], "delay_ms": 100}
            ]
        }
        
        # Save the sample scenario
        self.save_scenario(sample)
        
        self.logger.info(f"Created sample scenario: {scenario_id}")
        return scenario_id
        
    def create_scenario(self, name: str, description: str = "", 
                       steps: Optional[List[Dict]] = None) -> Optional[str]:
        """Create a new scenario
        
        Args:
            name: Scenario name
            description: Scenario description
            steps: Initial steps (optional)
            
        Returns:
            Scenario ID if successful, None otherwise
        """
        # Generate a scenario ID from name
        scenario_id = name.lower().replace(" ", "_")
        
        # Ensure ID is unique
        i = 1
        original_id = scenario_id
        while scenario_id in self.scenarios:
            scenario_id = f"{original_id}_{i}"
            i += 1
            
        # Create scenario data
        scenario_data = {
            "id": scenario_id,
            "name": name,
            "description": description,
            "steps": steps or []
        }
        
        # Save the scenario
        if self.save_scenario(scenario_data):
            return scenario_id
        else:
            return None
            
    def update_scenario_steps(self, scenario_id: str, steps: List[Dict]) -> bool:
        """Update the steps of an existing scenario
        
        Args:
            scenario_id: ID of the scenario to update
            steps: New steps
            
        Returns:
            bool: True if successful
        """
        # Load the scenario
        scenario = self.load_scenario(scenario_id)
        if not scenario:
            self.logger.warning(f"Cannot update steps for non-existent scenario: {scenario_id}")
            return False
            
        # Update steps
        scenario["steps"] = steps
        
        # Save the updated scenario
        return self.save_scenario(scenario)
        
    def get_scenario_steps(self, scenario_id: str) -> List[Dict]:
        """Get the steps of a scenario
        
        Args:
            scenario_id: ID of the scenario
            
        Returns:
            List of step dictionaries
        """
        scenario = self.load_scenario(scenario_id)
        if not scenario:
            return []
            
        return scenario.get("steps", [])
        
    def get_step_types(self) -> Dict[str, Dict]:
        """Get available step types and their parameters
        
        Returns:
            Dictionary of step types and their parameter definitions
        """
        return {
            "can_message": {
                "description": "Send a CAN message",
                "parameters": {
                    "id": {"type": "string", "description": "CAN ID (hex)"},
                    "data": {"type": "array", "description": "Data bytes (array of integers)"},
                    "delay_ms": {"type": "integer", "description": "Delay after sending (milliseconds)"}
                }
            },
            "pause": {
                "description": "Pause execution",
                "parameters": {
                    "duration_sec": {"type": "number", "description": "Pause duration (seconds)"}
                }
            },
            "plugin_action": {
                "description": "Execute a plugin action",
                "parameters": {
                    "plugin": {"type": "string", "description": "Plugin name"},
                    "action": {"type": "string", "description": "Action name"},
                    "params": {"type": "object", "description": "Action parameters"}
                }
            }
        }