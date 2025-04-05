#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.2
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
        
        self.logger.info("Grafana adapter initialized")
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
            
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
        """Store a CAN message (stub implementation - no storage)
        
        Args:
            can_id: CAN message ID (hex or int)
            data: Data bytes
            timestamp: Optional timestamp (default: now)
            
        Returns:
            bool: Always returns True
        """
        # Format for debugging only
        if isinstance(can_id, int):
            can_id_hex = f"0x{can_id:X}"
        else:
            can_id_hex = can_id if can_id.startswith("0x") else f"0x{can_id}"
            
        data_hex = " ".join(f"{byte:02X}" for byte in data)
        
        # Just log the message without storing it
        self.logger.debug(f"Would store CAN message: {can_id_hex} = {data_hex}")
        return True
            
    def store_signal_value(self, signal_name: str, value: Union[int, float, str], 
                         tags: Optional[Dict[str, str]] = None,
                         timestamp: Optional[datetime] = None) -> bool:
        """Store a decoded signal value (stub implementation - no storage)
        
        Args:
            signal_name: Name of the signal
            value: Signal value
            tags: Optional tags to associate with the value
            timestamp: Optional timestamp (default: now)
            
        Returns:
            bool: Always returns True
        """
        # Just log the signal without storing it
        self.logger.debug(f"Would store signal: {signal_name} = {value}")
        return True
            
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
            bool: Always returns True (stub implementation)
        """
        # This is just a stub implementation
        self.logger.info("SQLite datasource configuration would happen here (stub method)")
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
        # Create simple dashboard with placeholder panels
        panels = [
            {
                "title": "CAN Messages per Second",
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
            },
            {
                "title": "CAN IDs Activity",
                "type": "table",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
            }
        ]
        
        return self.create_dashboard(title, "Auto-generated CAN bus monitoring dashboard", panels)
