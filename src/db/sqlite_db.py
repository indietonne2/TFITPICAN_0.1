#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: sqlite_db.py
# Pathname: /path/to/tfitpican/src/db/
# Description: SQLite database access layer for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import sqlite3
import threading
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union

class SQLiteDB:
    """Centralized SQLite database access for TFITPICAN"""
    
    # SQL statements for table creation
    SCHEMA = {
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT,
                image_path TEXT,
                preferred_mode TEXT,
                last_login TEXT,
                settings TEXT
            );
        """,
        "can_messages": """
            CREATE TABLE IF NOT EXISTS can_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                can_id TEXT NOT NULL,
                data TEXT NOT NULL,
                direction TEXT NOT NULL,
                scenario_id TEXT,
                notes TEXT
            );
        """,
        "events": """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_id TEXT,
                description TEXT,
                data TEXT
            );
        """,
        "errors": """
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                error_code TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                metadata TEXT,
                resolved INTEGER DEFAULT 0,
                resolution_time TEXT,
                resolution_notes TEXT
            );
        """,
        "scenarios": """
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                last_run TEXT,
                run_count INTEGER DEFAULT 0,
                config_path TEXT
            );
        """,
        "test_results": """
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                status TEXT NOT NULL,
                duration REAL,
                results TEXT,
                notes TEXT
            );
        """,
        "roles": """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                permissions TEXT
            );
        """,
        "devices": """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT UNIQUE NOT NULL,
                name TEXT,
                address TEXT,
                is_primary INTEGER DEFAULT 0,
                role TEXT,
                last_seen TEXT
            );
        """,
        "translations": """
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                UNIQUE(language, key)
            );
        """,
        "settings": """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT
            );
        """
    }
    
    def __init__(self, db_path: str = "db/tfitpican.db", error_manager=None):
        self.logger = logging.getLogger("SQLiteDB")
        self.db_path = db_path
        self.error_manager = error_manager
        
        # Thread-local storage for database connections
        self.local = threading.local()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_db()
        
        # Set up scheduled backup
        self._setup_backup()
        
        self.logger.info(f"SQLite database initialized: {db_path}")
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection"""
        if not hasattr(self.local, 'connection') or self.local.connection is None:
            self.local.connection = sqlite3.connect(self.db_path)
            # Enable foreign keys
            self.local.connection.execute("PRAGMA foreign_keys = ON")
            # Return rows as dictionaries
            self.local.connection.row_factory = sqlite3.Row
            
        return self.local.connection
        
    def _init_db(self) -> None:
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for table_name, create_statement in self.SCHEMA.items():
            try:
                cursor.execute(create_statement)
                self.logger.debug(f"Table {table_name} initialized")
            except sqlite3.Error as e:
                self.logger.error(f"Error creating table {table_name}: {e}")
                if self.error_manager:
                    self.error_manager.report_error(
                        "SQLiteDB", 
                        "db_init_error", 
                        f"Error creating table {table_name}: {e}",
                        severity="error"
                    )
                    
        # Create default user if not exists
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (username, full_name, preferred_mode) VALUES (?, ?, ?)",
                ("admin", "Administrator", "default")
            )
            
        # Create default roles if not exists
        cursor.execute("SELECT COUNT(*) FROM roles")
        if cursor.fetchone()[0] == 0:
            default_roles = [
                ("admin", "Administrator", json.dumps({"all": True})),
                ("operator", "Operator", json.dumps({"scenario_run": True, "scenario_view": True})),
                ("viewer", "Viewer", json.dumps({"scenario_view": True}))
            ]
            cursor.executemany(
                "INSERT INTO roles (name, description, permissions) VALUES (?, ?, ?)",
                default_roles
            )
            
        # Commit changes
        conn.commit()
        
    def _setup_backup(self) -> None:
        """Set up scheduled database backup"""
        # This would start a background thread for periodic backups
        # For simplicity, just register the backup function to be called elsewhere
        self.logger.info("Database backup system initialized")
        
    def backup(self, backup_path: Optional[str] = None) -> bool:
        """Create a backup of the database
        
        Args:
            backup_path: Optional custom backup path
            
        Returns:
            bool: True if backup was successful
        """
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "db/backups"
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = f"{backup_dir}/tfitpican_{timestamp}.db"
            
        try:
            # Close all connections before backup
            if hasattr(self.local, 'connection') and self.local.connection:
                self.local.connection.close()
                self.local.connection = None
                
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            self.logger.info(f"Database backup created: {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "SQLiteDB", 
                    "backup_failed", 
                    f"Database backup failed: {e}",
                    severity="error"
                )
            return False
            
    def execute(self, query: str, params: Optional[Tuple] = None) -> Optional[sqlite3.Cursor]:
        """Execute a raw SQL query
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Cursor object or None if error
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            return cursor
        except sqlite3.Error as e:
            self.logger.error(f"SQL error: {e} in query: {query}")
            if self.error_manager:
                self.error_manager.report_error(
                    "SQLiteDB", 
                    "sql_error", 
                    f"SQL error: {e} in query: {query}",
                    severity="error"
                )
            return None
            
    def query(self, query: str, params: Optional[Tuple] = None, 
              fetch_all: bool = True) -> Optional[List[Dict]]:
        """Execute a query and retrieve results
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch_all: Whether to fetch all results or just one
            
        Returns:
            List of dictionaries (or single dictionary if fetch_all=False)
            None if error
        """
        cursor = self.execute(query, params)
        if not cursor:
            return None
            
        try:
            if fetch_all:
                rows = cursor.fetchall()
                if not rows:
                    return []
                    
                # Convert rows to dictionaries
                return [dict(row) for row in rows]
            else:
                row = cursor.fetchone()
                if not row:
                    return None
                return dict(row)
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching query results: {e}")
            return None
        finally:
            cursor.close()
            
    def insert(self, table: str, data: Dict) -> Optional[int]:
        """Insert data into a table
        
        Args:
            table: Table name
            data: Dictionary of column: value pairs
            
        Returns:
            ID of inserted row or None if error
        """
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        values = [data[col] for col in columns]
        
        query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            self.logger.error(f"Insert error: {e} in table {table}")
            if self.error_manager:
                self.error_manager.report_error(
                    "SQLiteDB", 
                    "insert_error", 
                    f"Insert error: {e} in table {table}",
                    severity="error"
                )
            return None
            
    def update(self, table: str, data: Dict, condition: str, 
               condition_params: Tuple) -> bool:
        """Update data in a table
        
        Args:
            table: Table name
            data: Dictionary of column: value pairs to update
            condition: WHERE condition
            condition_params: Parameters for the condition
            
        Returns:
            bool: True if successful
        """
        set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
        values = list(data.values()) + list(condition_params)
        
        query = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Update error: {e} in table {table}")
            if self.error_manager:
                self.error_manager.report_error(
                    "SQLiteDB", 
                    "update_error", 
                    f"Update error: {e} in table {table}",
                    severity="error"
                )
            return False
            
    def delete(self, table: str, condition: str, 
               condition_params: Tuple) -> bool:
        """Delete data from a table
        
        Args:
            table: Table name
            condition: WHERE condition
            condition_params: Parameters for the condition
            
        Returns:
            bool: True if successful
        """
        query = f"DELETE FROM {table} WHERE {condition}"
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, condition_params)
            conn.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Delete error: {e} in table {table}")
            if self.error_manager:
                self.error_manager.report_error(
                    "SQLiteDB", 
                    "delete_error", 
                    f"Delete error: {e} in table {table}",
                    severity="error"
                )
            return False
            
    def transaction(self, func):
        """Decorator for functions that need to run in a transaction
        
        Usage:
            @db.transaction
            def my_function(db, arg1, arg2):
                # This runs in a transaction
                db.insert(...)
                db.update(...)
        """
        def wrapper(*args, **kwargs):
            conn = self._get_connection()
            
            try:
                # Start transaction
                conn.execute("BEGIN")
                
                # Run the function
                result = func(self, *args, **kwargs)
                
                # Commit transaction
                conn.commit()
                return result
            except Exception as e:
                # Rollback on error
                conn.rollback()
                self.logger.error(f"Transaction error: {e}")
                if self.error_manager:
                    self.error_manager.report_error(
                        "SQLiteDB", 
                        "transaction_error", 
                        f"Transaction error: {e}",
                        severity="error"
                    )
                raise
                
        return wrapper
        
    # Specific domain methods
    
    def get_user_profile(self, username: str) -> Optional[Dict]:
        """Get user profile information
        
        Args:
            username: Username to retrieve
            
        Returns:
            User profile or None if not found
        """
        return self.query(
            "SELECT * FROM users WHERE username = ?", 
            (username,), 
            fetch_all=False
        )
        
    def store_profile(self, profile_data: Dict) -> bool:
        """Store user profile
        
        Args:
            profile_data: Profile data dictionary
            
        Returns:
            bool: True if successful
        """
        # Check if profile exists
        username = profile_data.get("username")
        if not username:
            return False
            
        existing = self.get_user_profile(username)
        
        if existing:
            # Update existing profile
            return self.update(
                "users", 
                {k: v for k, v in profile_data.items() if k != "username"},
                "username = ?", 
                (username,)
            )
        else:
            # Create new profile
            return self.insert("users", profile_data) is not None
            
    def get_can_messages(self, limit: int = 100, 
                        scenario_id: Optional[str] = None) -> List[Dict]:
        """Get CAN messages from the database
        
        Args:
            limit: Maximum number of messages to retrieve
            scenario_id: Optional scenario ID to filter by
            
        Returns:
            List of CAN message dictionaries
        """
        if scenario_id:
            return self.query(
                "SELECT * FROM can_messages WHERE scenario_id = ? ORDER BY timestamp DESC LIMIT ?",
                (scenario_id, limit)
            ) or []
        else:
            return self.query(
                "SELECT * FROM can_messages ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ) or []
            
    def get_scenarios(self) -> List[Dict]:
        """Get all available scenarios
        
        Returns:
            List of scenario dictionaries
        """
        return self.query("SELECT * FROM scenarios ORDER BY name") or []
        
    def get_scenario(self, scenario_id: str) -> Optional[Dict]:
        """Get a specific scenario
        
        Args:
            scenario_id: Scenario ID to retrieve
            
        Returns:
            Scenario data or None if not found
        """
        return self.query(
            "SELECT * FROM scenarios WHERE scenario_id = ?",
            (scenario_id,),
            fetch_all=False
        )
        
    def update_scenario_stats(self, scenario_id: str) -> None:
        """Update scenario run statistics
        
        Args:
            scenario_id: Scenario ID that was run
        """
        self.execute(
            """
            UPDATE scenarios 
            SET last_run = ?, run_count = run_count + 1 
            WHERE scenario_id = ?
            """,
            (datetime.now().isoformat(), scenario_id)
        )
        
    def get_translation(self, key: str, language: str = "en") -> str:
        """Get a translated string
        
        Args:
            key: Translation key
            language: Language code
            
        Returns:
            Translated string or key if not found
        """
        result = self.query(
            "SELECT value FROM translations WHERE language = ? AND key = ?",
            (language, key),
            fetch_all=False
        )
        
        if result:
            return result["value"]
        else:
            # Check if there's an English version
            if language != "en":
                en_result = self.query(
                    "SELECT value FROM translations WHERE language = 'en' AND key = ?",
                    (key,),
                    fetch_all=False
                )
                if en_result:
                    return en_result["value"]
                    
            # Return the key as fallback
            return key
            
    def get_settings(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """Get application settings
        
        Args:
            prefix: Optional key prefix to filter by
            
        Returns:
            Dictionary of settings (key -> value)
        """
        if prefix:
            rows = self.query(
                "SELECT key, value FROM settings WHERE key LIKE ?",
                (f"{prefix}%",)
            ) or []
        else:
            rows = self.query(
                "SELECT key, value FROM settings"
            ) or []
            
        # Convert to dictionary
        settings = {}
        for row in rows:
            key = row["key"]
            value = row["value"]
            
            # Try to parse JSON values
            try:
                settings[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                settings[key] = value
                
        return settings
        
    def set_setting(self, key: str, value: Any) -> bool:
        """Set an application setting
        
        Args:
            key: Setting key
            value: Setting value (will be JSON serialized if not a string)
            
        Returns:
            bool: True if successful
        """
        # Convert value to string if needed
        if not isinstance(value, str):
            value = json.dumps(value)
            
        existing = self.query(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
            fetch_all=False
        )
        
        if existing:
            # Update existing setting
            return self.update(
                "settings",
                {"value": value},
                "key = ?",
                (key,)
            )
        else:
            # Insert new setting
            return self.insert(
                "settings",
                {
                    "key": key,
                    "value": value,
                    "description": ""
                }
            ) is not None
            
    def register_device(self, device_id: str, name: str, 
                       address: str, role: Optional[str] = None) -> bool:
        """Register a Bluetooth device
        
        Args:
            device_id: Unique device identifier
            name: Device name
            address: Device address/MAC
            role: Optional assigned role
            
        Returns:
            bool: True if successful
        """
        existing = self.query(
            "SELECT id FROM devices WHERE device_id = ?",
            (device_id,),
            fetch_all=False
        )
        
        now = datetime.now().isoformat()
        
        if existing:
            # Update existing device
            return self.update(
                "devices",
                {
                    "name": name,
                    "address": address,
                    "role": role,
                    "last_seen": now
                },
                "device_id = ?",
                (device_id,)
            )
        else:
            # Insert new device
            return self.insert(
                "devices",
                {
                    "device_id": device_id,
                    "name": name,
                    "address": address,
                    "role": role,
                    "last_seen": now,
                    "is_primary": 0
                }
            ) is not None
            
    def close(self) -> None:
        """Close the database connection"""
        if hasattr(self.local, 'connection') and self.local.connection:
            self.local.connection.close()
            self.local.connection = None
            self.logger.debug("Database connection closed")
