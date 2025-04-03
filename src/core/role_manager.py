#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: role_manager.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Device role management for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union, Tuple

class RoleManager:
    """Manages device roles and permissions for multi-device setups"""
    
    # Standard roles
    STANDARD_ROLES = {
        "primary": {
            "name": "Primary",
            "description": "Main control device",
            "permissions": ["can_send", "can_receive", "run_scenario", "stop_scenario"]
        },
        "secondary": {
            "name": "Secondary",
            "description": "Secondary monitoring device",
            "permissions": ["can_receive"]
        },
        "observer": {
            "name": "Observer",
            "description": "Read-only access",
            "permissions": ["can_receive"]
        },
        "simulator": {
            "name": "Simulator",
            "description": "Simulation device",
            "permissions": ["can_send", "can_receive"]
        }
    }
    
    def __init__(self, config_path: str = "config/config.json", sqlite_db=None, error_manager=None):
        self.logger = logging.getLogger("RoleManager")
        self.config = self._load_config(config_path)
        self.sqlite_db = sqlite_db
        self.error_manager = error_manager
        
        # Registered devices and their roles
        self.devices = {}
        
        # Role definitions (built-in + custom)
        self.roles = self.STANDARD_ROLES.copy()
        
        # Load custom roles from database if available
        if sqlite_db:
            self._load_custom_roles()
            
        # Load device registrations from database
        if sqlite_db:
            self._load_device_registrations()
            
        self.logger.info("Role manager initialized")
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
            
    def _load_custom_roles(self) -> None:
        """Load custom roles from database"""
        try:
            custom_roles = self.sqlite_db.query(
                "SELECT name, description, permissions FROM roles"
            ) or []
            
            for role in custom_roles:
                role_name = role["name"].lower()
                
                try:
                    permissions = json.loads(role["permissions"])
                except:
                    permissions = []
                    
                self.roles[role_name] = {
                    "name": role["name"],
                    "description": role["description"],
                    "permissions": permissions
                }
                
            self.logger.info(f"Loaded {len(custom_roles)} custom roles")
            
        except Exception as e:
            self.logger.error(f"Error loading custom roles: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "RoleManager", 
                    "role_load_error", 
                    f"Error loading custom roles: {e}",
                    severity="warning"
                )
                
    def _load_device_registrations(self) -> None:
        """Load device registrations from database"""
        try:
            device_registrations = self.sqlite_db.query(
                "SELECT device_id, name, address, role, is_primary, last_seen FROM devices"
            ) or []
            
            for device in device_registrations:
                device_id = device["device_id"]
                self.devices[device_id] = {
                    "name": device["name"],
                    "address": device["address"],
                    "role": device["role"],
                    "is_primary": bool(device["is_primary"]),
                    "last_seen": device["last_seen"]
                }
                
            self.logger.info(f"Loaded {len(device_registrations)} device registrations")
            
        except Exception as e:
            self.logger.error(f"Error loading device registrations: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "RoleManager", 
                    "device_load_error", 
                    f"Error loading device registrations: {e}",
                    severity="warning"
                )
    
    def register_device(self, device_id: str, name: str, address: str) -> Dict:
        """Register a new device or update existing device
        
        Args:
            device_id: Unique device identifier
            name: Device name
            address: Device address/MAC
            
        Returns:
            Dict with registration information including assigned role
        """
        # Check if device already registered
        if device_id in self.devices:
            # Update existing device info
            device = self.devices[device_id]
            device["name"] = name
            device["address"] = address
            device["last_seen"] = datetime.now().isoformat()
            
            role = device["role"]
            is_primary = device["is_primary"]
            
            self.logger.info(f"Updated existing device: {name} ({device_id}) with role {role}")
            
        else:
            # Determine role for new device
            # If no devices yet, make this primary
            is_primary = len(self.devices) == 0
            
            # Assign role based on primary status
            role = "primary" if is_primary else "secondary"
            
            # Register new device
            self.devices[device_id] = {
                "name": name,
                "address": address,
                "role": role,
                "is_primary": is_primary,
                "last_seen": datetime.now().isoformat(),
                "registration_time": datetime.now().isoformat()
            }
            
            self.logger.info(f"Registered new device: {name} ({device_id}) as {role}")
            
        # Save to database if available
        if self.sqlite_db:
            self._save_device_to_db(device_id)
            
        # Return registration info
        return {
            "device_id": device_id,
            "name": name,
            "role": role,
            "is_primary": is_primary,
            "permissions": self.get_role_permissions(role)
        }
        
    def _save_device_to_db(self, device_id: str) -> bool:
        """Save device registration to database
        
        Args:
            device_id: Device ID to save
            
        Returns:
            bool: True if successful
        """
        if not self.sqlite_db or device_id not in self.devices:
            return False
            
        device = self.devices[device_id]
        
        try:
            # Check if device exists in DB
            existing = self.sqlite_db.query(
                "SELECT id FROM devices WHERE device_id = ?",
                (device_id,),
                fetch_all=False
            )
            
            if existing:
                # Update existing record
                self.sqlite_db.update(
                    "devices",
                    {
                        "name": device["name"],
                        "address": device["address"],
                        "role": device["role"],
                        "is_primary": 1 if device["is_primary"] else 0,
                        "last_seen": device["last_seen"]
                    },
                    "device_id = ?",
                    (device_id,)
                )
            else:
                # Insert new record
                self.sqlite_db.insert(
                    "devices",
                    {
                        "device_id": device_id,
                        "name": device["name"],
                        "address": device["address"],
                        "role": device["role"],
                        "is_primary": 1 if device["is_primary"] else 0,
                        "last_seen": device["last_seen"]
                    }
                )
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving device to database: {e}")
            return False
            
    def assign_role(self, device_id: str, role: str) -> bool:
        """Assign a role to a device
        
        Args:
            device_id: Device ID
            role: Role to assign
            
        Returns:
            bool: True if successful
        """
        # Check if device exists
        if device_id not in self.devices:
            self.logger.warning(f"Cannot assign role to unknown device: {device_id}")
            return False
            
        # Check if role exists
        if role not in self.roles:
            self.logger.warning(f"Cannot assign unknown role: {role}")
            return False
            
        # Handle primary role changes
        if role == "primary":
            # If assigning primary role, remove from any other device
            for other_id, other_device in self.devices.items():
                if other_id != device_id and other_device["is_primary"]:
                    other_device["is_primary"] = False
                    other_device["role"] = "secondary"
                    
                    # Update in database
                    if self.sqlite_db:
                        self._save_device_to_db(other_id)
        
        # Update role
        device = self.devices[device_id]
        device["role"] = role
        device["is_primary"] = (role == "primary")
        
        # Save to database
        if self.sqlite_db:
            self._save_device_to_db(device_id)
            
        self.logger.info(f"Assigned role {role} to device {device['name']} ({device_id})")
        return True
        
    def get_device_role(self, device_id: str) -> Optional[str]:
        """Get the role assigned to a device
        
        Args:
            device_id: Device ID
            
        Returns:
            Role name or None if device not found
        """
        if device_id in self.devices:
            return self.devices[device_id]["role"]
        return None
        
    def get_role_permissions(self, role: str) -> List[str]:
        """Get permissions for a role
        
        Args:
            role: Role name
            
        Returns:
            List of permission strings
        """
        if role in self.roles:
            return self.roles[role].get("permissions", [])
        return []
        
    def has_permission(self, device_id: str, permission: str) -> bool:
        """Check if a device has a specific permission
        
        Args:
            device_id: Device ID
            permission: Permission to check
            
        Returns:
            bool: True if device has permission
        """
        # Get device role
        role = self.get_device_role(device_id)
        if not role:
            return False
            
        # Get role permissions
        permissions = self.get_role_permissions(role)
        
        # Check permission
        return permission in permissions
        
    def get_primary_device(self) -> Optional[str]:
        """Get the ID of the primary device
        
        Returns:
            Device ID or None if no primary device
        """
        for device_id, device in self.devices.items():
            if device["is_primary"]:
                return device_id
        return None
        
    def get_devices_by_role(self, role: str) -> List[Dict]:
        """Get all devices with a specific role
        
        Args:
            role: Role to filter by
            
        Returns:
            List of device dictionaries
        """
        return [
            {
                "id": device_id,
                "name": device["name"],
                "address": device["address"],
                "is_primary": device["is_primary"],
                "last_seen": device["last_seen"]
            }
            for device_id, device in self.devices.items()
            if device["role"] == role
        ]
        
    def get_all_devices(self) -> List[Dict]:
        """Get all registered devices
        
        Returns:
            List of device dictionaries
        """
        return [
            {
                "id": device_id,
                "name": device["name"],
                "address": device["address"],
                "role": device["role"],
                "is_primary": device["is_primary"],
                "last_seen": device["last_seen"]
            }
            for device_id, device in self.devices.items()
        ]
        
    def get_available_roles(self) -> List[Dict]:
        """Get list of available roles
        
        Returns:
            List of role dictionaries
        """
        return [
            {
                "id": role_id,
                "name": role["name"],
                "description": role["description"],
                "permissions": role["permissions"]
            }
            for role_id, role in self.roles.items()
        ]
        
    def create_custom_role(self, name: str, description: str, 
                         permissions: List[str]) -> Optional[str]:
        """Create a custom role
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permissions
            
        Returns:
            Role ID if successful, None otherwise
        """
        # Generate role ID
        role_id = name.lower().replace(" ", "_")
        
        # Check if role already exists
        if role_id in self.roles:
            self.logger.warning(f"Role already exists: {role_id}")
            return None
            
        # Create role
        self.roles[role_id] = {
            "name": name,
            "description": description,
            "permissions": permissions
        }
        
        # Save to database if available
        if self.sqlite_db:
            try:
                self.sqlite_db.insert(
                    "roles",
                    {
                        "name": name,
                        "description": description,
                        "permissions": json.dumps(permissions)
                    }
                )
            except Exception as e:
                self.logger.error(f"Error saving custom role to database: {e}")
                
        self.logger.info(f"Created custom role: {name} ({role_id})")
        return role_id
        
    def update_role_permissions(self, role_id: str, permissions: List[str]) -> bool:
        """Update permissions for a role
        
        Args:
            role_id: Role ID
            permissions: New permissions list
            
        Returns:
            bool: True if successful
        """
        # Check if role exists
        if role_id not in self.roles:
            self.logger.warning(f"Cannot update unknown role: {role_id}")
            return False
            
        # Update permissions
        self.roles[role_id]["permissions"] = permissions
        
        # Save to database if available
        if self.sqlite_db:
            try:
                self.sqlite_db.update(
                    "roles",
                    {
                        "permissions": json.dumps(permissions)
                    },
                    "name = ?",
                    (self.roles[role_id]["name"],)
                )
            except Exception as e:
                self.logger.error(f"Error updating role permissions in database: {e}")
                
        self.logger.info(f"Updated permissions for role: {role_id}")
        return True
        
    def delete_custom_role(self, role_id: str) -> bool:
        """Delete a custom role
        
        Args:
            role_id: Role ID
            
        Returns:
            bool: True if successful
        """
        # Check if role exists
        if role_id not in self.roles:
            self.logger.warning(f"Cannot delete unknown role: {role_id}")
            return False
            
        # Prevent deleting standard roles
        if role_id in self.STANDARD_ROLES:
            self.logger.warning(f"Cannot delete standard role: {role_id}")
            return False
            
        # Check if any devices are using this role
        for device in self.devices.values():
            if device["role"] == role_id:
                self.logger.warning(f"Cannot delete role {role_id} as it is in use")
                return False
                
        # Delete role
        role_name = self.roles[role_id]["name"]
        del self.roles[role_id]
        
        # Delete from database if available
        if self.sqlite_db:
            try:
                self.sqlite_db.delete(
                    "roles",
                    "name = ?",
                    (role_name,)
                )
            except Exception as e:
                self.logger.error(f"Error deleting role from database: {e}")
                
        self.logger.info(f"Deleted custom role: {role_id}")
        return True