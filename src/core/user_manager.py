#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: user_manager.py
# Pathname: /path/to/tfitpican/src/core/
# Description: User management for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import json
import logging
import hashlib
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

class UserManager:
    """Manages users, profiles, and authentication for TFITPICAN"""
    
    def __init__(self, config_path: str = "config/config.json", sqlite_db=None, 
                access_control=None, error_manager=None):
        self.logger = logging.getLogger("UserManager")
        self.config = self._load_config(config_path)
        self.sqlite_db = sqlite_db
        self.access_control = access_control
        self.error_manager = error_manager
        
        # Current user
        self.current_user = None
        
        # Cache of user profiles
        self.user_cache = {}
        
        # Create default user if needed
        self._ensure_default_user()
        
        # Try to load last user
        self._load_last_user()
        
        self.logger.info("User manager initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def _ensure_default_user(self) -> None:
        """Ensure a default admin user exists"""
        if not self.sqlite_db:
            return
            
        try:
            # Check if any users exist
            user_count = self.sqlite_db.query(
                "SELECT COUNT(*) as count FROM users",
                fetch_all=False
            )
            
            if not user_count or user_count.get("count", 0) == 0:
                # Create default admin user
                self.sqlite_db.insert(
                    "users",
                    {
                        "username": "admin",
                        "full_name": "Administrator",
                        "image_path": "",
                        "preferred_mode": "default",
                        "last_login": datetime.now().isoformat(),
                        "settings": json.dumps({
                            "role": "admin",
                            "language": "en",
                            "theme": "dark"
                        })
                    }
                )
                
                self.logger.info("Created default admin user")
        except Exception as e:
            self.logger.error(f"Error ensuring default user: {e}")
    
    def _load_last_user(self) -> None:
        """Load the last logged in user"""
        if not self.sqlite_db:
            return
            
        try:
            # Try to get user from config
            last_username = self.config.get("user", {}).get("last_username")
            
            if last_username:
                user = self.get_user_profile(last_username)
                if user:
                    self.current_user = user
                    self.logger.info(f"Loaded last user: {last_username}")
            
            # If no user loaded, use default
            if not self.current_user:
                user = self.get_user_profile("admin")
                if user:
                    self.current_user = user
                    self.logger.info("Loaded default admin user")
        except Exception as e:
            self.logger.error(f"Error loading last user: {e}")
    
    def get_user_profile(self, username: str) -> Optional[Dict]:
        """Get a user profile
        
        Args:
            username: Username to retrieve
            
        Returns:
            User profile dictionary or None if not found
        """
        # Check cache first
        if username in self.user_cache:
            return self.user_cache[username]
            
        if not self.sqlite_db:
            return None
            
        try:
            # Query user from database
            user = self.sqlite_db.query(
                "SELECT * FROM users WHERE username = ?",
                (username,),
                fetch_all=False
            )
            
            if not user:
                return None
                
            # Parse settings
            if "settings" in user and user["settings"]:
                try:
                    user["settings"] = json.loads(user["settings"])
                except json.JSONDecodeError:
                    user["settings"] = {}
            else:
                user["settings"] = {}
                
            # Add to cache
            self.user_cache[username] = user
            
            return user
        except Exception as e:
            self.logger.error(f"Error getting user profile: {e}")
            return None
    
    def get_current_user(self) -> Optional[Dict]:
        """Get the current user profile
        
        Returns:
            Current user profile or None if no user logged in
        """
        return self.current_user
    
    def login(self, username: str) -> Dict:
        """Log in a user
        
        Args:
            username: Username to log in
            
        Returns:
            Dict with login result (success, message, user)
        """
        user = self.get_user_profile(username)
        
        if not user:
            return {
                "success": False,
                "message": f"User {username} not found",
                "user": None
            }
            
        # Update last login time
        if self.sqlite_db:
            self.sqlite_db.update(
                "users",
                {"last_login": datetime.now().isoformat()},
                "username = ?",
                (username,)
            )
            
        # Set current user
        self.current_user = user
        
        # Clear cache for this user to ensure fresh data on next get
        if username in self.user_cache:
            del self.user_cache[username]
            
        self.logger.info(f"User {username} logged in")
        
        return {
            "success": True,
            "message": f"User {username} logged in successfully",
            "user": user
        }
    
    def logout(self) -> Dict:
        """Log out the current user
        
        Returns:
            Dict with logout result (success, message)
        """
        if not self.current_user:
            return {
                "success": False,
                "message": "No user currently logged in"
            }
            
        username = self.current_user.get("username")
        self.current_user = None
        
        self.logger.info(f"User {username} logged out")
        
        return {
            "success": True,
            "message": f"User {username} logged out successfully"
        }
    
    def create_user(self, username: str, full_name: str, role: str = "viewer", 
                   settings: Optional[Dict] = None) -> Dict:
        """Create a new user
        
        Args:
            username: Username
            full_name: Full name
            role: User role
            settings: User settings
            
        Returns:
            Dict with creation result (success, message, user)
        """
        if not self.sqlite_db:
            return {
                "success": False,
                "message": "Database not available",
                "user": None
            }
            
        # Check if username already exists
        existing = self.get_user_profile(username)
        if existing:
            return {
                "success": False,
                "message": f"Username {username} already exists",
                "user": None
            }
            
        # Prepare user settings
        user_settings = settings or {}
        user_settings["role"] = role
        
        try:
            # Insert user into database
            self.sqlite_db.insert(
                "users",
                {
                    "username": username,
                    "full_name": full_name,
                    "image_path": "",
                    "preferred_mode": "default",
                    "last_login": datetime.now().isoformat(),
                    "settings": json.dumps(user_settings)
                }
            )
            
            # Get the new user profile
            user = self.get_user_profile(username)
            
            self.logger.info(f"Created new user: {username}")
            
            return {
                "success": True,
                "message": f"User {username} created successfully",
                "user": user
            }
        except Exception as e:
            self.logger.error(f"Error creating user: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "UserManager", 
                    "user_creation_error", 
                    f"Error creating user {username}: {e}",
                    severity="error"
                )
                
            return {
                "success": False,
                "message": f"Error creating user: {str(e)}",
                "user": None
            }
    
    def update_user(self, username: str, update_data: Dict) -> Dict:
        """Update a user profile
        
        Args:
            username: Username to update
            update_data: Dictionary of fields to update
            
        Returns:
            Dict with update result (success, message, user)
        """
        if not self.sqlite_db:
            return {
                "success": False,
                "message": "Database not available",
                "user": None
            }
            
        # Get existing user
        user = self.get_user_profile(username)
        if not user:
            return {
                "success": False,
                "message": f"User {username} not found",
                "user": None
            }
            
        # Prepare update data
        db_update = {}
        
        # Handle basic fields
        for field in ["full_name", "image_path", "preferred_mode"]:
            if field in update_data:
                db_update[field] = update_data[field]
                
        # Handle settings
        if "settings" in update_data:
            # Merge existing settings with updates
            settings = user.get("settings", {}).copy()
            settings.update(update_data["settings"])
            db_update["settings"] = json.dumps(settings)
            
        try:
            # Update user in database
            if db_update:
                self.sqlite_db.update(
                    "users",
                    db_update,
                    "username = ?",
                    (username,)
                )
                
            # Clear cache for this user
            if username in self.user_cache:
                del self.user_cache[username]
                
            # Update current user if this is the current user
            if self.current_user and self.current_user.get("username") == username:
                self.current_user = self.get_user_profile(username)
                
            # Get updated user profile
            updated_user = self.get_user_profile(username)
            
            self.logger.info(f"Updated user: {username}")
            
            return {
                "success": True,
                "message": f"User {username} updated successfully",
                "user": updated_user
            }
        except Exception as e:
            self.logger.error(f"Error updating user: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "UserManager", 
                    "user_update_error", 
                    f"Error updating user {username}: {e}",
                    severity="error"
                )
                
            return {
                "success": False,
                "message": f"Error updating user: {str(e)}",
                "user": None
            }
    
    def delete_user(self, username: str) -> Dict:
        """Delete a user
        
        Args:
            username: Username to delete
            
        Returns:
            Dict with deletion result (success, message)
        """
        if not self.sqlite_db:
            return {
                "success": False,
                "message": "Database not available"
            }
            
        # Prevent deleting the admin user
        if username == "admin":
            return {
                "success": False,
                "message": "Cannot delete the admin user"
            }
            
        # Check if user exists
        user = self.get_user_profile(username)
        if not user:
            return {
                "success": False,
                "message": f"User {username} not found"
            }
            
        try:
            # Delete user from database
            self.sqlite_db.delete(
                "users",
                "username = ?",
                (username,)
            )
            
            # Clear cache for this user
            if username in self.user_cache:
                del self.user_cache[username]
                
            # If this was the current user, reset to admin
            if self.current_user and self.current_user.get("username") == username:
                self.current_user = self.get_user_profile("admin")
                
            self.logger.info(f"Deleted user: {username}")
            
            return {
                "success": True,
                "message": f"User {username} deleted successfully"
            }
        except Exception as e:
            self.logger.error(f"Error deleting user: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "UserManager", 
                    "user_deletion_error", 
                    f"Error deleting user {username}: {e}",
                    severity="error"
                )
                
            return {
                "success": False,
                "message": f"Error deleting user: {str(e)}"
            }
    
    def get_all_users(self) -> List[Dict]:
        """Get all users
        
        Returns:
            List of user profile dictionaries
        """
        if not self.sqlite_db:
            return []
            
        try:
            # Query all users from database
            users = self.sqlite_db.query("SELECT * FROM users") or []
            
            # Parse settings for each user
            for user in users:
                if "settings" in user and user["settings"]:
                    try:
                        user["settings"] = json.loads(user["settings"])
                    except json.JSONDecodeError:
                        user["settings"] = {}
                else:
                    user["settings"] = {}
                    
            return users
        except Exception as e:
            self.logger.error(f"Error getting all users: {e}")
            return []
    
    def can_execute(self, permission: str) -> bool:
        """Check if current user has a specific permission
        
        Args:
            permission: Permission to check
            
        Returns:
            bool: True if user has permission
        """
        if not self.current_user or not self.access_control:
            return False
            
        return self.access_control.can_execute(self.current_user, permission)
    
    def set_user_role(self, username: str, role: str) -> Dict:
        """Set a user's role
        
        Args:
            username: Username to update
            role: New role
            
        Returns:
            Dict with update result (success, message, user)
        """
        # Get existing user
        user = self.get_user_profile(username)
        if not user:
            return {
                "success": False,
                "message": f"User {username} not found",
                "user": None
            }
            
        # Update settings with new role
        return self.update_user(username, {
            "settings": {
                "role": role
            }
        })
    
    def get_user_settings(self, username: str, key: Optional[str] = None,
                         default: Any = None) -> Any:
        """Get user settings
        
        Args:
            username: Username
            key: Optional settings key to retrieve
            default: Default value if key not found
            
        Returns:
            Settings value or dictionary
        """
        user = self.get_user_profile(username)
        if not user:
            return {} if key is None else default
            
        settings = user.get("settings", {})
        
        if key is not None:
            return settings.get(key, default)
            
        return settings
    
    def set_user_setting(self, username: str, key: str, value: Any) -> Dict:
        """Set a user setting
        
        Args:
            username: Username
            key: Settings key
            value: Settings value
            
        Returns:
            Dict with update result (success, message, user)
        """
        # Update user with new setting
        return self.update_user(username, {
            "settings": {
                key: value
            }
        })
