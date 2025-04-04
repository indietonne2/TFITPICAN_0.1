#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.1
# License: MIT
# Filename: grafana_adapter.py
# Pathname: /path/to/tfitpican/src/db/
# Description: Grafana integration adapter for TFITPICAN application (SQLite-based)
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

class GrafanaAdapter:
    """Adapter for integrating with Grafana visualization platform using SQLite backend"""
    
    def __init__(self, config_path: str = "config/config.json", sqlite_db=None, error_manager=None):
        self.logger = logging.getLogger("GrafanaAdapter")
        self.config = self._load_config(config_path)
        self.sqlite_db = sqlite_db
        self.error_manager = error_manager
        
        # Grafana connection settings
        grafana_config = self.config.get("grafana", {})
        self.grafana_url = grafana_config.get("url", "http://localhost:3000")
        self.grafana_api_key = grafana_config.get("api_key", "")
        self.grafana_user = grafana_config.get("username", "admin")
        self.grafana_password = grafana_config.get("password", "admin")
        
        # Ensure the SQLite database has the required tables for time-series data
        if self.sqlite_db:
            self._initialize_time_series_tables()
            
        self.logger.info("Grafana adapter initialized")
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
            
    def _initialize_time_series_tables(self) -> None:
        """Initialize SQLite tables for time-series data storage"""
        if not self.sqlite_db:
            return
            
        # Create tables for time-series data if they don't exist
        try:
            # Table for CAN messages time-series data
            self.sqlite_db.execute("""
                CREATE TABLE IF NOT EXISTS can_timeseries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    can_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    value INTEGER,
                    byte0 INTEGER,
                    byte1 INTEGER,
                    byte2 INTEGER,
                    byte3 INTEGER,
                    byte4 INTEGER,
                    byte5 INTEGER,
                    byte6 INTEGER,
                    byte7 INTEGER
                )
            """)
            
            # Table for decoded signal values
            self.sqlite_db.execute("""
                CREATE TABLE IF NOT EXISTS signal_timeseries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    signal_name TEXT NOT NULL,
                    value REAL,
                    tag_key TEXT,
                    tag_value TEXT
                )
            """)
            
            # Create indices for efficient querying
            self.sqlite_db.execute("""
                CREATE INDEX IF NOT EXISTS idx_can_ts_timestamp 
                ON can_timeseries (timestamp)
            """)
            
            self.sqlite_db.execute("""
                CREATE INDEX IF NOT EXISTS idx_can_ts_can_id 
                ON can_timeseries (can_id)
            """)
            
            self.sqlite_db.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_ts_timestamp 
                ON signal_timeseries (timestamp)
            """)
            
            self.sqlite_db.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_ts_signal_name 
                ON signal_timeseries (signal_name)
            """)
            
            self.logger.info("Time-series tables initialized in SQLite database")
            
        except Exception as e:
            self.logger.error(f"Error initializing time-series tables: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "GrafanaAdapter", 
                    "sqlite_init_error", 
                    f"Error initializing time-series tables: {e}",
                    severity="error"
                )