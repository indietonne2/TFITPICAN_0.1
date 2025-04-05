#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.1
# License: MIT
# Filename: grafana_adapter.py
# Pathname: /path/to/tfitpican/src/db/
# Description: Grafana integration adapter for TFITPICAN application
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
import influxdb

class GrafanaAdapter:
    """Adapter for integrating with Grafana visualization platform"""
    
    def __init__(self, config_path: str = "config/config.json", error_manager=None):
        self.logger = logging.getLogger("GrafanaAdapter")
        self.config = self._load_config(config_path)
        self.error_manager = error_manager
        
        # Grafana connection settings
        grafana_config = self.config.get("grafana", {})
        self.grafana_url = grafana_config.get("url", "http://localhost:3000")
        self.grafana_api_key = grafana_config.get("api_key", "")
        self.grafana_user = grafana_config.get("username", "admin")
        self.grafana_password = grafana_config.get("password", "admin")
        
        # InfluxDB connection settings (for time series data)
        influx_config = self.config.get("influxdb", {})
        self.influx_enabled = influx_config.get("enabled", True)
        self.influx_host = influx_config.get("host", "localhost")
        self.influx_port = influx_config.get("port", 8086)
        self.influx_database = influx_config.get("database", "canbus_data")
        self.influx_username = influx_config.get("username", "")
        self.influx_password = influx_config.get("password", "")
        
        # InfluxDB client
        self.influx_client = None
        if self.influx_enabled:
            self._connect_influxdb()
            
        self.logger.info("Grafana adapter initialized")
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
            
    def _connect_influxdb(self) -> bool:
        """Connect to InfluxDB database
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.influx_client = influxdb.InfluxDBClient(
                host=self.influx_host,
                port=self.influx_port,
                username=self.influx_username,
                password=self.influx_password,
                database=self.influx_database
            )
            
            # Test connection
            version = self.influx_client.ping()
            if not version:
                raise Exception("InfluxDB did not respond to ping")
                
            # Check if database exists, create if not
            databases = [db['name'] for db in self.influx_client.get_list_database()]
            if self.influx_database not in databases:
                self.influx_client.create_database(self.influx_database)
                self.logger.info(f"Created InfluxDB database: {self.influx_database}")
                
            # Switch to database
            self.influx_client.switch_database(self.influx_database)
            
            self.logger.info(f"Connected to InfluxDB: {self.influx_host}:{self.influx_port}/{self.influx_database}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to InfluxDB: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "GrafanaAdapter", 
                    "influxdb_connection_failed", 
                    f"Failed to connect to InfluxDB: {e}",
                    severity="error"
                )
            self.influx_client = None
            return False
            
    def _grafana_headers(self) -> Dict[str, str]:
        """Get headers for Grafana API requests"""
        if self.grafana_api_key:
            return {
                'Authorization': f'Bearer {self.grafana_api_key}',
                'Content-Type': 'application/json'
            }
        else:
            # Basic auth
            import base64
            auth = base64.b64encode(f"{self.grafana_user}:{self.grafana_password}".encode()).decode()
            return {
                'Authorization': f'Basic {auth}',
                'Content-Type': 'application/json'
            }
            
    def store_can_message(self, can_id: Union[int, str], data: List[int], 
                         timestamp: Optional[datetime] = None) -> bool:
        """Store a CAN message in InfluxDB for visualization
        
        Args:
            can_id: CAN message ID (hex or int)
            data: Data bytes
            timestamp: Optional timestamp (default: now)
            
        Returns:
            bool: True if successful
        """
        if not self.influx_client:
            if not self._connect_influxdb():
                return False
                
        # Ensure can_id is in hex format as string
        if isinstance(can_id, int):
            can_id_hex = f"0x{can_id:X}"
        else:
            # Ensure hex format has 0x prefix
            can_id_hex = can_id if can_id.startswith("0x") else f"0x{can_id}"
            
        # Format data as hex string
        data_hex = " ".join(f"{byte:02X}" for byte in data)
        
        # Prepare timestamp
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        # Create InfluxDB point
        point = {
            "measurement": "can_messages",
            "tags": {
                "can_id": can_id_hex,
                "dlc": len(data)
            },
            "time": timestamp.isoformat(),
            "fields": {
                "data": data_hex,
                "byte0": data[0] if len(data) > 0 else 0,
                "byte1": data[1] if len(data) > 1 else 0,
                "byte2": data[2] if len(data) > 2 else 0,
                "byte3": data[3] if len(data) > 3 else 0,
                "byte4": data[4] if len(data) > 4 else 0,
                "byte5": data[5] if len(data) > 5 else 0,
                "byte6": data[6] if len(data) > 6 else 0,
                "byte7": data[7] if len(data) > 7 else 0,
                # Store integer value (for easier graphing)
                "value": int.from_bytes(bytes(data), byteorder='big')
            }
        }
        
        try:
            # Write to InfluxDB
            success = self.influx_client.write_points([point])
            if not success:
                self.logger.warning("Failed to write point to InfluxDB")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing to InfluxDB: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "GrafanaAdapter", 
                    "influxdb_write_error", 
                    f"Error writing to InfluxDB: {e}",
                    severity="warning"
                )
            return False
            
    def store_signal_value(self, signal_name: str, value: Union[int, float, str], 
                         tags: Optional[Dict[str, str]] = None,
                         timestamp: Optional[datetime] = None) -> bool:
        """Store a decoded signal value in InfluxDB
        
        Args:
            signal_name: Name of the signal
            value: Signal value
            tags: Optional tags to associate with the value
            timestamp: Optional timestamp (default: now)
            
        Returns:
            bool: True if successful
        """
        if not self.influx_client:
            if not self._connect_influxdb():
                return False
                
        # Prepare timestamp
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        # Create field value based on type
        if isinstance(value, (int, float)):
            field_value = value
        else:
            field_value = str(value)
            
        # Create InfluxDB point
        point = {
            "measurement": "signals",
            "tags": tags or {},
            "time": timestamp.isoformat(),
            "fields": {
                "value": field_value
            }
        }
        
        # Add signal name as tag
        point["tags"]["name"] = signal_name
        
        try:
            # Write to InfluxDB
            success = self.influx_client.write_points([point])
            if not success:
                self.logger.warning("Failed to write signal to InfluxDB")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing signal to InfluxDB: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "GrafanaAdapter", 
                    "influxdb_write_error", 
                    f"Error writing signal to InfluxDB: {e}",
                    severity="warning"
                )
            return False
            
    def test_grafana_connection(self) -> bool:
        """Test connection to Grafana API
        
        Returns:
            bool: True if connection is working
        """
        try:
            # Make a simple API request to check connectivity
            url = f"{self.grafana_url}/api/health"
            response = requests.get(url)
            
            if response.status_code == 200:
                health_data = response.json()
                self.logger.info(f"Grafana connection successful. Version: {health_data.get('version', 'unknown')}")
                return True
            else:
                self.logger.warning(f"Grafana API returned status code {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to Grafana API: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "GrafanaAdapter", 
                    "grafana_connection_error", 
                    f"Error connecting to Grafana API: {e}",
                    severity="warning"
                )
            return False
    
    def configure_grafana_sqlite_datasource(self) -> bool:
        """Configure a Grafana datasource for the SQLite database
        
        Returns:
            bool: True if successful
        """
        # For SQLite integration with Grafana, a plugin is typically needed
        # This is a placeholder implementation that logs what would happen
        self.logger.info("Configure Grafana SQLite datasource method called")
        self.logger.warning("Direct SQLite integration with Grafana requires a plugin")
        self.logger.info("Check if the sqlite-datasource plugin is installed in Grafana")
        
        # Test basic Grafana connectivity
        if not self.test_grafana_connection():
            self.logger.error("Cannot configure datasource: Grafana connection failed")
            return False
            
        self.logger.info("Basic Grafana connection successful")
        return True
            
    def create_dashboard(self, title: str, description: str = "",
                       panels: Optional[List[Dict]] = None) -> Optional[str]:
        """Create a new Grafana dashboard
        
        Args:
            title: Dashboard title
            description: Dashboard description
            panels: List of panel configurations
            
        Returns:
            Dashboard URL if successful, None otherwise
        """
        if not panels:
            panels = []
            
        # Create dashboard JSON
        dashboard = {
            "dashboard": {
                "id": None,
                "title": title,
                "description": description,
                "tags": ["tfitpican", "canbus"],
                "timezone": "browser",
                "schemaVersion": 22,
                "version": 0,
                "refresh": "10s",
                "panels": panels
            },
            "overwrite": True
        }
        
        try:
            # Make API request to create dashboard
            url = f"{self.grafana_url}/api/dashboards/db"
            response = requests.post(
                url,
                headers=self._grafana_headers(),
                json=dashboard
            )
            
            if response.status_code in (200, 201):
                result = response.json()
                dashboard_url = result.get("url", "")
                full_url = f"{self.grafana_url}{dashboard_url}"
                self.logger.info(f"Created Grafana dashboard: {full_url}")
                return full_url
            else:
                self.logger.warning(f"Failed to create dashboard. Status: {response.status_code}, Response: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating Grafana dashboard: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "GrafanaAdapter", 
                    "dashboard_creation_error", 
                    f"Error creating Grafana dashboard: {e}",
                    severity="warning"
                )
            return None
            
    def create_can_dashboard(self, title: str = "CAN Bus Dashboard") -> Optional[str]:
        """Create a pre-configured dashboard for CAN bus data
        
        Args:
            title: Dashboard title
            
        Returns:
            Dashboard URL if successful, None otherwise
        """
        # Create panels for the dashboard
        panels = [
            # Panel 1: CAN message rate over time
            {
                "title": "CAN Messages per Second",
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
                "targets": [
                    {
                        "groupBy": [{"type": "time", "params": ["1s"]}],
                        "measurement": "can_messages",
                        "select": [[{"type": "count", "params": ["data"]}]],
                        "refId": "A"
                    }
                ]
            },
            # Panel 2: CAN IDs table
            {
                "title": "CAN IDs Activity",
                "type": "table",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
                "targets": [
                    {
                        "groupBy": [{"type": "tag", "params": ["can_id"]}],
                        "measurement": "can_messages",
                        "select": [[{"type": "count", "params": ["data"]}]],
                        "refId": "A"
                    }
                ]
            },
            # Panel 3: Raw CAN messages
            {
                "title": "Recent CAN Messages",
                "type": "table",
                "gridPos": {"x": 0, "y": 8, "w": 24, "h": 8},
                "targets": [
                    {
                        "groupBy": [{"type": "time", "params": ["$__interval"]}],
                        "measurement": "can_messages",
                        "select": [[{"type": "field", "params": ["data"]}]],
                        "limit": "50",
                        "orderByTime": "DESC",
                        "refId": "A"
                    }
                ]
            },
            # Panel 4: Signal values graph
            {
                "title": "Signal Values",
                "type": "graph",
                "gridPos": {"x": 0, "y": 16, "w": 24, "h