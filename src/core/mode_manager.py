#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: mode_manager.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Application mode management for TFITPICAN
# -----------------------------------------------------------------------------

import os
import json
import logging
from typing import Dict, List, Any, Optional, Set, Union, Callable

class ModeManager:
    """Manages application modes and configurations for TFITPICAN"""
    
    # Predefined application modes
    DEFAULT_MODES = {
        "default": {
            "name": "Default",
            "description": "Standard application mode",
            "ui": {
                "theme": "light",
                "layout": "standard",
                "panels": ["scenarios", "logger", "can_monitor"]
            },
            "features": {
                "can_enabled": True,
                "bluetooth_enabled": False,
                "grafana_enabled": True,
                "plugins_enabled": True,
                "test_automation_enabled": True
            }
        },
        "presentation": {
            "name": "Presentation",
            "description": "Mode for demonstrations and presentations",
            "ui": {
                "theme": "dark",
                "layout": "presentation",
                "panels": ["scenarios", "car_visualization"],
                "fullscreen": True
            },
            "features": {
                "can_enabled": True,
                "bluetooth_enabled": False,
                "grafana_enabled": True,
                "plugins_enabled": False,
                "animations_enabled": True
            }
        },
        "lightweight": {
            "name": "Lightweight",
            "description": "Minimal mode for resource-constrained environments",
            "ui": {
                "theme": "light",
                "layout": "minimal",
                "panels": ["scenarios", "logger"]
            },
            "features": {
                "can_enabled": True,
                "bluetooth_enabled": False,
                "grafana_enabled": False,
                "plugins_enabled": False
            }
        }
    }
    
    def __init__(self, config_path: str = "config/config.json", sqlite_db=None, error_manager=None):
        self.logger = logging.getLogger("ModeManager")
        self.config = self._load_config(config_path)
        self.sqlite_db = sqlite_db
        self.error_manager = error_manager
        
        # Current mode
        self.current_mode = "default"
        self.current_mode_config = self.DEFAULT_MODES["default"].copy()
        
        # Custom modes loaded from database
        self.custom_modes = {}
        
        # Mode change callbacks
        self.mode_callbacks = []
        
        # Load custom modes if database available
        if self.sqlite_db:
            self._load_custom_modes()
            
        # Set initial mode from config
        mode_config = self.config.get("mode", {})
        if "current" in mode_config:
            self.load_mode(mode_config["current"])
            
        self.logger.info(f"Mode manager initialized with mode: {self.current_mode}")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def _load_custom_modes(self) -> None:
        """Load custom modes from database"""
        try:
            # Get mode settings
            mode_settings = self.sqlite_db.get_settings("mode.")
            
            for key, value in mode_settings.items():
                if key.startswith("mode.") and "." in key[5:]:
                    # Extract mode name and setting path
                    parts = key.split(".")
                    mode_name = parts[1]
                    setting_path = ".".join(parts[2:])
                    
                    # Initialize mode dictionary if needed
                    if mode_name not in self.custom_modes:
                        self.custom_modes[mode_name] = {
                            "name": mode_name.capitalize(),
                            "description": f"Custom mode: {mode_name}",
                            "ui": {},
                            "features": {}
                        }
                        
                    # Update setting
                    current = self.custom_modes[mode_name]
                    parts = setting_path.split(".")
                    
                    # Navigate to correct nested dictionary
                    for i, part in enumerate(parts[:-1]):
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                        
                    # Set value
                    current[parts[-1]] = value
            
            self.logger.info(f"Loaded {len(self.custom_modes)} custom modes")
        except Exception as e:
            self.logger.error(f"Error loading custom modes: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "ModeManager", 
                    "mode_load_error", 
                    f"Error loading custom modes: {e}",
                    severity="warning"
                )
    
    def load_mode(self, mode_name: str) -> bool:
        """Load and activate a mode
        
        Args:
            mode_name: Name of the mode to load
            
        Returns:
            bool: True if mode was loaded successfully
        """
        # Check if mode exists
        mode_config = self.get_mode_config(mode_name)
        
        if not mode_config:
            self.logger.warning(f"Mode not found: {mode_name}, using default")
            mode_name = "default"
            mode_config = self.DEFAULT_MODES["default"].copy()
            
        # Set current mode
        previous_mode = self.current_mode
        self.current_mode = mode_name
        self.current_mode_config = mode_config
        
        self.logger.info(f"Activated mode: {mode_name}")
        
        # Notify callbacks
        self._notify_mode_change(previous_mode, mode_name)
        
        return True
    
    def get_mode_config(self, mode_name: str) -> Optional[Dict]:
        """Get configuration for a mode
        
        Args:
            mode_name: Mode name
            
        Returns:
            Mode configuration dictionary or None if not found
        """
        # Check default modes
        if mode_name in self.DEFAULT_MODES:
            return self.DEFAULT_MODES[mode_name].copy()
            
        # Check custom modes
        if mode_name in self.custom_modes:
            return self.custom_modes[mode_name].copy()
            
        return None
    
    def get_current_mode(self) -> str:
        """Get the current mode name
        
        Returns:
            str: Current mode name
        """
        return self.current_mode
    
    def get_current_mode_config(self) -> Dict:
        """Get the current mode configuration
        
        Returns:
            Dict: Current mode configuration
        """
        return self.current_mode_config.copy()
    
    def get_available_modes(self) -> List[Dict]:
        """Get list of available modes
        
        Returns:
            List of mode dictionaries with name and description
        """
        modes = []
        
        # Add default modes
        for mode_name, mode_config in self.DEFAULT_MODES.items():
            modes.append({
                "id": mode_name,
                "name": mode_config.get("name", mode_name.capitalize()),
                "description": mode_config.get("description", ""),
                "is_custom": False
            })
            
        # Add custom modes
        for mode_name, mode_config in self.custom_modes.items():
            modes.append({
                "id": mode_name,
                "name": mode_config.get("name", mode_name.capitalize()),
                "description": mode_config.get("description", ""),
                "is_custom": True
            })
            
        return sorted(modes, key=lambda x: x["name"])
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled in the current mode
        
        Args:
            feature_name: Feature name to check
            
        Returns:
            bool: True if feature is enabled
        """
        features = self.current_mode_config.get("features", {})
        return features.get(feature_name, False)
    
    def get_ui_setting(self, setting_name: str, default_value: Any = None) -> Any:
        """Get a UI setting from the current mode
        
        Args:
            setting_name: Setting name
            default_value: Default value if setting not found
            
        Returns:
            Setting value
        """
        ui_settings = self.current_mode_config.get("ui", {})
        
        if "." in setting_name:
            # Handle nested settings
            parts = setting_name.split(".")
            current = ui_settings
            
            for part in parts[:-1]:
                if part not in current:
                    return default_value
                current = current[part]
                
            return current.get(parts[-1], default_value)
        else:
            # Simple setting
            return ui_settings.get(setting_name, default_value)
    
    def create_custom_mode(self, mode_name: str, mode_config: Dict) -> bool:
        """Create a custom mode
        
        Args:
            mode_name: Mode name
            mode_config: Mode configuration
            
        Returns:
            bool: True if successful
        """
        # Check if name is valid
        if not mode_name or not isinstance(mode_name, str):
            self.logger.error("Invalid mode name")
            return False
            
        mode_name = mode_name.lower()
        
        # Check if mode already exists
        if mode_name in self.DEFAULT_MODES:
            self.logger.warning(f"Cannot override default mode: {mode_name}")
            return False
            
        # Store custom mode
        self.custom_modes[mode_name] = mode_config
        
        # Save to database if available
        if self.sqlite_db:
            self._save_mode_to_db(mode_name, mode_config)
            
        self.logger.info(f"Created custom mode: {mode_name}")
        return True
    
    def _save_mode_to_db(self, mode_name: str, mode_config: Dict) -> None:
        """Save a mode configuration to the database
        
        Args:
            mode_name: Mode name
            mode_config: Mode configuration
        """
        try:
            # Flatten mode configuration for storage
            self._store_nested_settings(f"mode.{mode_name}", mode_config)
            
        except Exception as e:
            self.logger.error(f"Error saving mode to database: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "ModeManager", 
                    "mode_save_error", 
                    f"Error saving mode {mode_name} to database: {e}",
                    severity="warning"
                )
    
    def _store_nested_settings(self, prefix: str, config: Dict) -> None:
        """Recursively store nested settings in the database
        
        Args:
            prefix: Settings key prefix
            config: Configuration dictionary
        """
        for key, value in config.items():
            if isinstance(value, dict):
                # Recurse for nested dictionaries
                self._store_nested_settings(f"{prefix}.{key}", value)
            else:
                # Store leaf values
                self.sqlite_db.set_setting(f"{prefix}.{key}", value)
    
    def update_custom_mode(self, mode_name: str, mode_config: Dict) -> bool:
        """Update a custom mode
        
        Args:
            mode_name: Mode name
            mode_config: Mode configuration
            
        Returns:
            bool: True if successful
        """
        mode_name = mode_name.lower()
        
        # Check if mode exists and is custom
        if mode_name not in self.custom_modes:
            if mode_name in self.DEFAULT_MODES:
                self.logger.warning(f"Cannot modify default mode: {mode_name}")
                return False
            else:
                self.logger.warning(f"Mode not found: {mode_name}")
                return False
                
        # Update custom mode
        self.custom_modes[mode_name] = mode_config
        
        # Save to database if available
        if self.sqlite_db:
            self._save_mode_to_db(mode_name, mode_config)
            
        # Update current mode if needed
        if self.current_mode == mode_name:
            self.current_mode_config = mode_config.copy()
            
        self.logger.info(f"Updated custom mode: {mode_name}")
        return True
    
    def delete_custom_mode(self, mode_name: str) -> bool:
        """Delete a custom mode
        
        Args:
            mode_name: Mode name
            
        Returns:
            bool: True if successful
        """
        mode_name = mode_name.lower()
        
        # Check if mode exists and is custom
        if mode_name not in self.custom_modes:
            if mode_name in self.DEFAULT_MODES:
                self.logger.warning(f"Cannot delete default mode: {mode_name}")
                return False
            else:
                self.logger.warning(f"Mode not found: {mode_name}")
                return False
                
        # Delete from custom modes
        del self.custom_modes[mode_name]
        
        # Delete from database if available
        if self.sqlite_db:
            self._delete_mode_from_db(mode_name)
            
        # Switch to default mode if this was the current mode
        if self.current_mode == mode_name:
            self.load_mode("default")
            
        self.logger.info(f"Deleted custom mode: {mode_name}")
        return True
    
    def _delete_mode_from_db(self, mode_name: str) -> None:
        """Delete a mode from the database
        
        Args:
            mode_name: Mode name
        """
        try:
            # Delete settings with the mode prefix
            prefix = f"mode.{mode_name}."
            
            # Get all settings
            all_settings = self.sqlite_db.get_settings()
            
            # Delete matching settings
            for key in all_settings:
                if key.startswith(prefix):
                    self.sqlite_db.delete("settings", "key = ?", (key,))
                    
        except Exception as e:
            self.logger.error(f"Error deleting mode from database: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "ModeManager", 
                    "mode_delete_error", 
                    f"Error deleting mode {mode_name} from database: {e}",
                    severity="warning"
                )
    
    def register_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for mode changes
        
        Args:
            callback: Function to call when mode changes (old_mode, new_mode)
        """
        if callback not in self.mode_callbacks:
            self.mode_callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[str, str], None]) -> None:
        """Unregister a mode change callback
        
        Args:
            callback: Previously registered callback function
        """
        if callback in self.mode_callbacks:
            self.mode_callbacks.remove(callback)
    
    def _notify_mode_change(self, old_mode: str, new_mode: str) -> None:
        """Notify callbacks of a mode change
        
        Args:
            old_mode: Previous mode
            new_mode: New mode
        """
        for callback in self.mode_callbacks:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                self.logger.error(f"Error in mode change callback: {e}")
                
                if self.error_manager:
                    self.error_manager.report_error(
                        "ModeManager", 
                        "callback_error", 
                        f"Error in mode change callback: {e}",
                        severity="warning"
                    )
    
    def create_mode_from_current(self, new_mode_name: str, override: bool = False) -> bool:
        """Create a new mode based on current settings
        
        Args:
            new_mode_name: Name for the new mode
            override: Whether to override existing custom mode
            
        Returns:
            bool: True if successful
        """
        new_mode_name = new_mode_name.lower()
        
        # Check if mode already exists
        if new_mode_name in self.DEFAULT_MODES:
            self.logger.warning(f"Cannot override default mode: {new_mode_name}")
            return False
            
        if new_mode_name in self.custom_modes and not override:
            self.logger.warning(f"Mode already exists: {new_mode_name}")
            return False
            
        # Create new mode from current
        new_mode = self.current_mode_config.copy()
        new_mode["name"] = new_mode_name.capitalize()
        new_mode["description"] = f"Custom mode based on {self.current_mode}"
        
        # Save new mode
        return self.create_custom_mode(new_mode_name, new_mode) True,
                "grafana_enabled": True,
                "plugins_enabled": True
            }
        },
        "development": {
            "name": "Development",
            "description": "Enhanced mode for development and debugging",
            "ui": {
                "theme": "dark",
                "layout": "development",
                "panels": ["scenarios", "logger", "can_monitor", "plugins", "debug"]
            },
            "features": {
                "can_enabled": True,
                "bluetooth_enabled": True,
                "grafana_enabled": True,
                "plugins_enabled": True,
                "debug_enabled": True
            }
        },
        "testing": {
            "name": "Testing",
            "description": "Mode for automated testing",
            "ui": {
                "theme": "light",
                "layout": "testing",
                "panels": ["scenarios", "logger", "test_results"]
            },
            "features": {
                "can_enabled": True,
                "bluetooth_enabled":