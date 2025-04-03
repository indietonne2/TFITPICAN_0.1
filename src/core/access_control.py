#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: access_control.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Access control and permission management for TFITPICAN
# -----------------------------------------------------------------------------

import os
import json
import logging
from typing import Dict, List, Any, Optional, Set, Union

class AccessControl:
    """Manages user permissions and access control for TFITPICAN"""
    
    # Permission levels
    PERMISSION_LEVELS = {
        "admin": 100,        # Full access
        "developer": 80,     # Can create and modify scenarios
        "operator": 60,      # Can run scenarios
        "viewer": 40,        # Can view data only
        "guest": 20          # Limited view access
    }
    
    # Default permissions by level
    DEFAULT_PERMISSIONS = {
        "admin": {
            "can_view_scenarios": True,
            "can_run_scenarios": True,
            "can_create_scenarios": True,
            "can_delete_scenarios": True,
            "can_modify_settings": True,
            "can_view_logs": True,
            "can_manage_users": True,
            "can_manage_plugins": True,
            "can_send_can": True,
            "can_receive_can": True,
            "can_manage_devices": True,
            "can_export_data": True,
            "can_access_all": True
        },
        "developer": {
            "can_view_scenarios": True,
            "can_run_scenarios": True,
            "can_create_scenarios": True,
            "can_delete_scenarios": True,
            "can_modify_settings": True,
            "can_view_logs": True,
            "can_manage_plugins": True,
            "can_send_can": True,
            "can_receive_can": True,
            "can_export_data": True
        },
        "operator": {
            "can_view_scenarios": True,
            "can_run_scenarios": True,
            "can_view_logs": True,
            "can_send_can": True,
            "can_receive_can": True,
            "can_export_data": True
        },
        "viewer": {
            "can_view_scenarios": True,
            "can_view_logs": True,
            "can_receive_can": True,
            "can_export_data": True
        },
        "guest": {
            "can_view_scenarios": True,
            "can_receive_can": True
        }
    }
    
    def __init__(self, config_path: str = "config/config.json", sqlite_db=None):
        self.logger = logging.getLogger("AccessControl")
        self.config = self._load_config(config_path)
        self.sqlite_db = sqlite_db
        
        # Custom permissions loaded from database
        self.custom_permissions = {}
        
        # Load custom permissions if database available
        if self.sqlite_db:
            self._load_custom_permissions()
            
        self.logger.info("Access control initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def _load_custom_permissions(self) -> None:
        """Load custom permissions from database"""
        try:
            if self.sqlite_db:
                # Get custom permissions from roles table
                roles = self.sqlite_db.query(
                    "SELECT name, permissions FROM roles"
                ) or []
                
                for role in roles:
                    role_name = role.get("name", "").lower()
                    
                    try:
                        perms = json.loads(role.get("permissions", "{}"))
                        self.custom_permissions[role_name] = perms
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid permissions format for role: {role_name}")
                
                self.logger.info(f"Loaded {len(self.custom_permissions)} custom permission sets")
        except Exception as e:
            self.logger.error(f"Error loading custom permissions: {e}")
    
    def get_permission_level(self, role: str) -> int:
        """Get the numeric permission level for a role
        
        Args:
            role: Role name
            
        Returns:
            int: Permission level (0 if role not recognized)
        """
        role = role.lower()
        return self.PERMISSION_LEVELS.get(role, 0)
    
    def get_permissions(self, role: str) -> Dict[str, bool]:
        """Get all permissions for a role
        
        Args:
            role: Role name
            
        Returns:
            Dict of permission name to boolean
        """
        role = role.lower()
        
        # Check if custom permissions exist for this role
        if role in self.custom_permissions:
            return self.custom_permissions[role]
            
        # Return default permissions
        return self.DEFAULT_PERMISSIONS.get(role, {})
    
    def can_execute(self, user: Dict, permission: str) -> bool:
        """Check if a user has a specific permission
        
        Args:
            user: User dictionary (must contain 'role' key)
            permission: Permission to check
            
        Returns:
            bool: True if user has permission
        """
        # Admin always has all permissions
        if user.get("role", "").lower() == "admin":
            return True
            
        # Get user's role
        role = user.get("role", "guest").lower()
        
        # Get permissions for role
        permissions = self.get_permissions(role)
        
        # Check for the specific permission
        if permission in permissions:
            return permissions[permission]
            
        # Check for wildcard permission
        if "can_access_all" in permissions and permissions["can_access_all"]:
            return True
            
        # Default to deny
        return False
    
    def get_available_roles(self) -> List[str]:
        """Get list of available roles
        
        Returns:
            List of role names
        """
        # Combine default and custom roles
        roles = set(self.PERMISSION_LEVELS.keys())
        roles.update(self.custom_permissions.keys())
        return sorted(roles)
    
    def create_custom_role(self, role_name: str, permissions: Dict[str, bool], 
                          level: Optional[int] = None) -> bool:
        """Create a custom role with specified permissions
        
        Args:
            role_name: Name of the role
            permissions: Dict of permissions
            level: Optional permission level
            
        Returns:
            bool: True if successful
        """
        role_name = role_name.lower()
        
        # Check if role already exists
        if role_name in self.PERMISSION_LEVELS and role_name not in self.custom_permissions:
            self.logger.warning(f"Cannot modify built-in role: {role_name}")
            return False
            
        # Store custom permissions
        self.custom_permissions[role_name] = permissions
        
        # Add to permission levels if level provided
        if level is not None:
            self.PERMISSION_LEVELS[role_name] = level
            
        # Save to database if available
        if self.sqlite_db:
            try:
                # Check if role exists
                existing = self.sqlite_db.query(
                    "SELECT id FROM roles WHERE name = ?",
                    (role_name,),
                    fetch_all=False
                )
                
                if existing:
                    # Update existing role
                    self.sqlite_db.update(
                        "roles",
                        {
                            "permissions": json.dumps(permissions)
                        },
                        "name = ?",
                        (role_name,)
                    )
                else:
                    # Insert new role
                    self.sqlite_db.insert(
                        "roles",
                        {
                            "name": role_name,
                            "description": f"Custom role: {role_name}",
                            "permissions": json.dumps(permissions)
                        }
                    )
                
                self.logger.info(f"Saved custom role to database: {role_name}")
                return True
            except Exception as e:
                self.logger.error(f"Error saving custom role to database: {e}")
                return False
        
        return True
    
    def delete_custom_role(self, role_name: str) -> bool:
        """Delete a custom role
        
        Args:
            role_name: Name of the role to delete
            
        Returns:
            bool: True if successful
        """
        role_name = role_name.lower()
        
        # Check if role is built-in
        if role_name in self.PERMISSION_LEVELS and role_name not in self.custom_permissions:
            self.logger.warning(f"Cannot delete built-in role: {role_name}")
            return False
            
        # Remove from custom permissions
        if role_name in self.custom_permissions:
            del self.custom_permissions[role_name]
            
        # Remove from permission levels if it was added there
        if role_name in self.PERMISSION_LEVELS and role_name not in self.DEFAULT_PERMISSIONS:
            del self.PERMISSION_LEVELS[role_name]
            
        # Delete from database if available
        if self.sqlite_db:
            try:
                self.sqlite_db.delete(
                    "roles",
                    "name = ?",
                    (role_name,)
                )
                
                self.logger.info(f"Deleted custom role from database: {role_name}")
                return True
            except Exception as e:
                self.logger.error(f"Error deleting custom role from database: {e}")
                return False
        
        return True
    
    def get_required_permission(self, action: str) -> str:
        """Get the permission required for an action
        
        Args:
            action: Action to check
            
        Returns:
            str: Permission name required
        """
        # Map of actions to required permissions
        action_map = {
            "view_scenarios": "can_view_scenarios",
            "run_scenario": "can_run_scenarios",
            "create_scenario": "can_create_scenarios",
            "edit_scenario": "can_create_scenarios",
            "delete_scenario": "can_delete_scenarios",
            "modify_settings": "can_modify_settings",
            "view_logs": "can_view_logs",
            "manage_users": "can_manage_users",
            "manage_plugins": "can_manage_plugins",
            "send_can": "can_send_can",
            "receive_can": "can_receive_can",
            "manage_devices": "can_manage_devices",
            "export_data": "can_export_data"
        }
        
        return action_map.get(action, "can_access_all")
    
    def get_all_permissions(self) -> List[str]:
        """Get list of all possible permissions
        
        Returns:
            List of permission names
        """
        # Collect all permissions from all default roles
        all_perms = set()
        for role_perms in self.DEFAULT_PERMISSIONS.values():
            all_perms.update(role_perms.keys())
            
        return sorted(all_perms)
