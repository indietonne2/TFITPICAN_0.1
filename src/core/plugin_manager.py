#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: plugin_manager.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Plugin management system for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import logging
import importlib.util
import inspect
from typing import Dict, List, Any, Optional, Callable, Union

class PluginManager:
    """Manages the loading and execution of plugins for TFITPICAN"""
    
    def __init__(self, plugin_dir: str = "plugins", error_manager=None):
        self.logger = logging.getLogger("PluginManager")
        self.plugin_dir = plugin_dir
        self.error_manager = error_manager
        
        # Loaded plugins
        self.plugins = {}
        self.plugin_instances = {}
        
        # Ensure plugin directory exists
        os.makedirs(plugin_dir, exist_ok=True)
        
        # Plugin interface definition
        self.required_methods = [
            "initialize",
            "execute_action",
            "cleanup"
        ]
        
        self.logger.info("Plugin manager initialized")
    
    def discover_plugins(self) -> List[str]:
        """Discover available plugins in the plugin directory
        
        Returns:
            List of plugin names
        """
        plugin_files = []
        
        try:
            # List all Python files in the plugin directory
            for file in os.listdir(self.plugin_dir):
                if file.endswith(".py") and not file.startswith("__"):
                    plugin_name = os.path.splitext(file)[0]
                    plugin_files.append(plugin_name)
        except Exception as e:
            self.logger.error(f"Error discovering plugins: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "PluginManager", 
                    "plugin_discovery_error", 
                    f"Error discovering plugins: {e}",
                    severity="error"
                )
                
        return plugin_files
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load a plugin
        
        Args:
            plugin_name: Name of the plugin to load
            
        Returns:
            bool: True if plugin loaded successfully
        """
        # Check if plugin is already loaded
        if plugin_name in self.plugin_instances:
            self.logger.warning(f"Plugin {plugin_name} is already loaded")
            return True
            
        try:
            # Determine plugin file path
            plugin_file = os.path.join(self.plugin_dir, f"{plugin_name}.py")
            
            if not os.path.exists(plugin_file):
                self.logger.error(f"Plugin file not found: {plugin_file}")
                return False
                
            # Load module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            if not spec or not spec.loader:
                self.logger.error(f"Failed to create module spec for plugin: {plugin_name}")
                return False
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin class
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and name.endswith("Plugin"):
                    plugin_class = obj
                    break
                    
            if not plugin_class:
                self.logger.error(f"No plugin class found in {plugin_file}")
                return False
                
            # Check plugin interface
            for method in self.required_methods:
                if not hasattr(plugin_class, method) or not callable(getattr(plugin_class, method)):
                    self.logger.error(f"Plugin {plugin_name} is missing required method: {method}")
                    return False
                    
            # Create plugin instance
            plugin_instance = plugin_class()
            
            # Initialize plugin
            success = plugin_instance.initialize()
            if not success:
                self.logger.error(f"Failed to initialize plugin: {plugin_name}")
                return False
                
            # Store plugin
            self.plugins[plugin_name] = plugin_class
            self.plugin_instances[plugin_name] = plugin_instance
            
            self.logger.info(f"Plugin loaded: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading plugin {plugin_name}: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "PluginManager", 
                    "plugin_load_error", 
                    f"Error loading plugin {plugin_name}: {e}",
                    severity="error"
                )
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            bool: True if plugin unloaded successfully
        """
        if plugin_name not in self.plugin_instances:
            self.logger.warning(f"Plugin {plugin_name} is not loaded")
            return False
            
        try:
            # Clean up plugin
            plugin_instance = self.plugin_instances[plugin_name]
            plugin_instance.cleanup()
            
            # Remove plugin
            del self.plugin_instances[plugin_name]
            del self.plugins[plugin_name]
            
            self.logger.info(f"Plugin unloaded: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unloading plugin {plugin_name}: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "PluginManager", 
                    "plugin_unload_error", 
                    f"Error unloading plugin {plugin_name}: {e}",
                    severity="error"
                )
            return False
    
    def unload_all_plugins(self) -> None:
        """Unload all loaded plugins"""
        for plugin_name in list(self.plugin_instances.keys()):
            self.unload_plugin(plugin_name)
    
    def execute_action(self, plugin_name: str, action_name: str, 
                      params: Optional[Dict] = None) -> Any:
        """Execute a plugin action
        
        Args:
            plugin_name: Name of the plugin
            action_name: Name of the action to execute
            params: Optional parameters for the action
            
        Returns:
            Result of the action
        """
        if plugin_name not in self.plugin_instances:
            self.logger.error(f"Plugin {plugin_name} is not loaded")
            return None
            
        try:
            # Get plugin instance
            plugin_instance = self.plugin_instances[plugin_name]
            
            # Execute action
            result = plugin_instance.execute_action(action_name, params or {})
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing action {action_name} on plugin {plugin_name}: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "PluginManager", 
                    "plugin_action_error", 
                    f"Error executing action {action_name} on plugin {plugin_name}: {e}",
                    severity="error"
                )
            return None
    
    def get_loaded_plugins(self) -> List[str]:
        """Get list of loaded plugin names
        
        Returns:
            List of plugin names
        """
        return list(self.plugin_instances.keys())
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict]:
        """Get information about a plugin
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Dictionary with plugin information or None if not loaded
        """
        if plugin_name not in self.plugin_instances:
            return None
            
        try:
            # Get plugin instance
            plugin_instance = self.plugin_instances[plugin_name]
            
            # Get plugin class
            plugin_class = self.plugins[plugin_name]
            
            # Basic info
            info = {
                "name": plugin_name,
                "class": plugin_class.__name__,
                "file": inspect.getfile(plugin_class),
                "loaded": True
            }
            
            # Get documentation
            if plugin_class.__doc__:
                info["description"] = plugin_class.__doc__.strip()
            else:
                info["description"] = "No description available"
                
            # Get version if available
            if hasattr(plugin_instance, "version"):
                info["version"] = plugin_instance.version
                
            # Get author if available
            if hasattr(plugin_instance, "author"):
                info["author"] = plugin_instance.author
                
            # Get available actions
            if hasattr(plugin_instance, "get_actions"):
                info["actions"] = plugin_instance.get_actions()
            else:
                # Try to discover actions
                actions = []
                for name, obj in inspect.getmembers(plugin_class):
                    if name.startswith("action_") and callable(obj):
                        action_name = name[7:]  # Remove "action_" prefix
                        actions.append(action_name)
                info["actions"] = actions
                
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting plugin info for {plugin_name}: {e}")
            return {
                "name": plugin_name,
                "error": str(e),
                "loaded": True
            }
    
    def create_plugin_template(self, plugin_name: str) -> bool:
        """Create a template for a new plugin
        
        Args:
            plugin_name: Name of the new plugin
            
        Returns:
            bool: True if template created successfully
        """
        # Clean plugin name
        plugin_name = plugin_name.strip().replace(" ", "_")
        
        # Generate class name
        class_name = "".join(word.capitalize() for word in plugin_name.split("_")) + "Plugin"
        
        template = f'''#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: [Your Name]
# Version: 0.1.0
# License: MIT
# Filename: {plugin_name}.py
# Pathname: plugins/
# Description: {plugin_name} plugin for TFITPICAN application
# -----------------------------------------------------------------------------

class {class_name}:
    """
    {plugin_name} plugin for TFITPICAN
    
    This plugin provides [description of functionality].
    """
    
    def __init__(self):
        self.version = "0.1.0"
        self.author = "[Your Name]"
    
    def initialize(self):
        """Initialize the plugin
        
        Returns:
            bool: True if initialization successful
        """
        print(f"{class_name} initialized")
        return True
    
    def cleanup(self):
        """Clean up plugin resources"""
        print(f"{class_name} cleaned up")
    
    def execute_action(self, action_name, params):
        """Execute a plugin action
        
        Args:
            action_name: Name of the action to execute
            params: Parameters for the action
            
        Returns:
            Result of the action
        """
        # Check if action exists
        method_name = f"action_{action_name}"
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            # Call the action method
            return getattr(self, method_name)(params)
        else:
            print(f"Unknown action: {action_name}")
            return None
    
    def get_actions(self):
        """Get list of available actions
        
        Returns:
            List of action names
        """
        return ["example"]
    
    def action_example(self, params):
        """Example action
        
        Args:
            params: Action parameters
            
        Returns:
            Action result
        """
        message = params.get("message", "Hello World")
        return f"Example action executed with message: {message}"
'''
        
        try:
            # Create plugin file
            plugin_file = os.path.join(self.plugin_dir, f"{plugin_name}.py")
            
            # Check if file already exists
            if os.path.exists(plugin_file):
                self.logger.warning(f"Plugin file already exists: {plugin_file}")
                return False
                
            # Write template to file
            with open(plugin_file, "w") as f:
                f.write(template)
                
            self.logger.info(f"Plugin template created: {plugin_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating plugin template: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "PluginManager", 
                    "plugin_template_error", 
                    f"Error creating plugin template: {e}",
                    severity="error"
                )
            return False
            