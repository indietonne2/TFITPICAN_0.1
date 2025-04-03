#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: sqlite_logger.py
# Pathname: /path/to/tfitpican/src/db/
# Description: Database logging facility for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import json
import logging
import threading
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

class SQLiteLogger:
    """Database logging system for TFITPICAN"""
    
    def __init__(self, sqlite_db, error_manager=None):
        self.logger = logging.getLogger("SQLiteLogger")
        self.sqlite_db = sqlite_db
        self.error_manager = error_manager
        
        # Queue for log messages to be processed asynchronously
        self.log_queue = queue.Queue()
        
        # Background thread for processing logs
        self.log_thread = None
        self.running = False
        
        # Start the logging thread
        self.start()
        
        self.logger.info("SQLite logger initialized")
    
    def start(self) -> None:
        """Start the logging thread"""
        if self.running:
            return
            
        self.running = True
        self.log_thread = threading.Thread(target=self._log_worker)
        self.log_thread.daemon = True
        self.log_thread.start()
        
        self.logger.debug("SQLite logger thread started")
    
    def stop(self) -> None:
        """Stop the logging thread"""
        if not self.running:
            return
            
        self.running = False
        
        # Wait for thread to finish
        if self.log_thread:
            self.log_thread.join(timeout=2.0)
            
        self.logger.debug("SQLite logger thread stopped")
    
    def _log_worker(self) -> None:
        """Background thread for processing log messages"""
        while self.running:
            try:
                # Get log entry from queue (with timeout)
                try:
                    log_entry = self.log_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                    
                # Process log entry
                self._process_log_entry(log_entry)
                
                # Mark as done
                self.log_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in log worker thread: {e}")
                
                # Report error
                if self.error_manager:
                    self.error_manager.report_error(
                        "SQLiteLogger", 
                        "log_worker_error", 
                        f"Error in log worker thread: {e}",
                        severity="error"
                    )
                
    def _process_log_entry(self, log_entry: Dict) -> None:
        """Process a log entry
        
        Args:
            log_entry: Log entry dictionary
        """
        if not self.sqlite_db:
            return
            
        try:
            # Get log type
            log_type = log_entry.pop("type", "event")
            
            # Insert into appropriate table
            if log_type == "event":
                self.sqlite_db.insert("events", log_entry)
            elif log_type == "error":
                self.sqlite_db.insert("errors", log_entry)
            elif log_type == "can_message":
                self.sqlite_db.insert("can_messages", log_entry)
            elif log_type == "test_result":
                self.sqlite_db.insert("test_results", log_entry)
            else:
                # Unknown log type, insert as generic event
                log_entry["type"] = log_type
                self.sqlite_db.insert("events", log_entry)
                
        except Exception as e:
            self.logger.error(f"Error inserting log entry: {e}")
            
            # Report error
            if self.error_manager:
                self.error_manager.report_error(
                    "SQLiteLogger", 
                    "log_insert_error", 
                    f"Error inserting log entry: {e}",
                    severity="error"
                )
    
    def log_event(self, event_type: str, event_id: Optional[str] = None, 
                 description: Optional[str] = None, data: Optional[Dict] = None) -> None:
        """Log an event
        
        Args:
            event_type: Type of event
            event_id: Optional event identifier
            description: Optional event description
            data: Optional additional data
        """
        log_entry = {
            "type": "event",
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "event_id": event_id,
            "description": description,
            "data": json.dumps(data) if data else None
        }
        
        # Add to queue for processing
        self.log_queue.put(log_entry)
    
    def log_error(self, source: str, error_code: str, message: str, 
                 severity: str = "error", metadata: Optional[Dict] = None) -> None:
        """Log an error
        
        Args:
            source: Error source
            error_code: Error code
            message: Error message
            severity: Error severity
            metadata: Optional additional metadata
        """
        log_entry = {
            "type": "error",
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "error_code": error_code,
            "message": message,
            "severity": severity,
            "metadata": json.dumps(metadata) if metadata else None,
            "resolved": 0,
            "resolution_time": None,
            "resolution_notes": None
        }
        
        # Add to queue for processing
        self.log_queue.put(log_entry)
    
    def log_can_message(self, can_id: Union[int, str], data: Union[List[int], str], 
                      direction: str, scenario_id: Optional[str] = None, 
                      notes: Optional[str] = None) -> None:
        """Log a CAN message
        
        Args:
            can_id: CAN message ID
            data: Data bytes (list of integers or hex string)
            direction: Message direction ('incoming' or 'outgoing')
            scenario_id: Optional scenario identifier
            notes: Optional additional notes
        """
        # Format CAN ID as hex string
        if isinstance(can_id, int):
            can_id_str = f"0x{can_id:X}"
        else:
            can_id_str = can_id if can_id.startswith("0x") else f"0x{can_id}"
            
        # Format data as hex string
        if isinstance(data, list):
            data_str = " ".join(f"{b:02X}" for b in data)
        else:
            data_str = data
            
        log_entry = {
            "type": "can_message",
            "timestamp": datetime.now().isoformat(),
            "can_id": can_id_str,
            "data": data_str,
            "direction": direction,
            "scenario_id": scenario_id,
            "notes": notes
        }
        
        # Add to queue for processing
        self.log_queue.put(log_entry)
    
    def log_test_result(self, scenario_id: str, status: str, duration: float, 
                       results: Dict, notes: Optional[str] = None) -> None:
        """Log a test result
        
        Args:
            scenario_id: Scenario identifier
            status: Test status ('completed', 'failed', etc.)
            duration: Test duration in seconds
            results: Test results data
            notes: Optional additional notes
        """
        log_entry = {
            "type": "test_result",
            "timestamp": datetime.now().isoformat(),
            "scenario_id": scenario_id,
            "status": status,
            "duration": duration,
            "results": json.dumps(results) if results else None,
            "notes": notes
        }
        
        # Add to queue for processing
        self.log_queue.put(log_entry)
    
    def get_recent_events(self, limit: int = 100, 
                         event_type: Optional[str] = None) -> List[Dict]:
        """Get recent events from the database
        
        Args:
            limit: Maximum number of events to retrieve
            event_type: Optional event type filter
            
        Returns:
            List of event dictionaries
        """
        if not self.sqlite_db:
            return []
            
        try:
            if event_type:
                return self.sqlite_db.query(
                    "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                    (event_type, limit)
                ) or []
            else:
                return self.sqlite_db.query(
                    "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ) or []
                
        except Exception as e:
            self.logger.error(f"Error querying events: {e}")
            return []
    
    def get_recent_errors(self, limit: int = 100, 
                         min_severity: Optional[str] = None) -> List[Dict]:
        """Get recent errors from the database
        
        Args:
            limit: Maximum number of errors to retrieve
            min_severity: Optional minimum severity filter
            
        Returns:
            List of error dictionaries
        """
        if not self.sqlite_db:
            return []
            
        try:
            if min_severity:
                return self.sqlite_db.query(
                    "SELECT * FROM errors WHERE severity >= ? ORDER BY timestamp DESC LIMIT ?",
                    (min_severity, limit)
                ) or []
            else:
                return self.sqlite_db.query(
                    "SELECT * FROM errors ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ) or []
                
        except Exception as e:
            self.logger.error(f"Error querying errors: {e}")
            return []
    
    def get_can_messages(self, limit: int = 100, 
                        can_id: Optional[str] = None,
                        scenario_id: Optional[str] = None) -> List[Dict]:
        """Get CAN messages from the database
        
        Args:
            limit: Maximum number of messages to retrieve
            can_id: Optional CAN ID filter
            scenario_id: Optional scenario ID filter
            
        Returns:
            List of CAN message dictionaries
        """
        if not self.sqlite_db:
            return []
            
        try:
            query = "SELECT * FROM can_messages"
            params = []
            
            # Add filters
            filters = []
            if can_id:
                filters.append("can_id = ?")
                params.append(can_id)
                
            if scenario_id:
                filters.append("scenario_id = ?")
                params.append(scenario_id)
                
            # Add WHERE clause if filters exist
            if filters:
                query += " WHERE " + " AND ".join(filters)
                
            # Add ORDER BY and LIMIT
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            return self.sqlite_db.query(query, tuple(params)) or []
                
        except Exception as e:
            self.logger.error(f"Error querying CAN messages: {e}")
            return []
    
    def get_test_results(self, limit: int = 100, 
                        scenario_id: Optional[str] = None) -> List[Dict]:
        """Get test results from the database
        
        Args:
            limit: Maximum number of results to retrieve
            scenario_id: Optional scenario ID filter
            
        Returns:
            List of test result dictionaries
        """
        if not self.sqlite_db:
            return []
            
        try:
            if scenario_id:
                return self.sqlite_db.query(
                    "SELECT * FROM test_results WHERE scenario_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (scenario_id, limit)
                ) or []
            else:
                return self.sqlite_db.query(
                    "SELECT * FROM test_results ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ) or []
                
        except Exception as e:
            self.logger.error(f"Error querying test results: {e}")
            return []
    
    def mark_error_resolved(self, error_id: int, resolution_notes: Optional[str] = None) -> bool:
        """Mark an error as resolved
        
        Args:
            error_id: Error ID
            resolution_notes: Optional resolution notes
            
        Returns:
            bool: True if successful
        """
        if not self.sqlite_db:
            return False
            
        try:
            return self.sqlite_db.update(
                "errors",
                {
                    "resolved": 1,
                    "resolution_time": datetime.now().isoformat(),
                    "resolution_notes": resolution_notes
                },
                "id = ?",
                (error_id,)
            )
                
        except Exception as e:
            self.logger.error(f"Error marking error as resolved: {e}")
            return False
    
    def clear_old_logs(self, days: int = 30) -> Tuple[int, int, int, int]:
        """Clear logs older than specified days
        
        Args:
            days: Days to keep logs
            
        Returns:
            Tuple of (events_deleted, errors_deleted, can_messages_deleted, test_results_deleted)
        """
        if not self.sqlite_db:
            return (0, 0, 0, 0)
            
        try:
            # Calculate cutoff date
            cutoff_date = (datetime.now() - datetime.timedelta(days=days)).isoformat()
            
            # Delete old records from each table
            events_deleted = self._delete_old_records("events", cutoff_date)
            errors_deleted = self._delete_old_records("errors", cutoff_date)
            can_messages_deleted = self._delete_old_records("can_messages", cutoff_date)
            test_results_deleted = self._delete_old_records("test_results", cutoff_date)
            
            self.logger.info(f"Cleared old logs: {events_deleted} events, {errors_deleted} errors, "
                          f"{can_messages_deleted} CAN messages, {test_results_deleted} test results")
            
            return (events_deleted, errors_deleted, can_messages_deleted, test_results_deleted)
                
        except Exception as e:
            self.logger.error(f"Error clearing old logs: {e}")
            return (0, 0, 0, 0)
    
    def _delete_old_records(self, table: str, cutoff_date: str) -> int:
        """Delete records older than cutoff date from a table
        
        Args:
            table: Table name
            cutoff_date: Cutoff date string (ISO format)
            
        Returns:
            int: Number of records deleted
        """
        try:
            # Count records to be deleted
            count_query = f"SELECT COUNT(*) as count FROM {table} WHERE timestamp < ?"
            result = self.sqlite_db.query(count_query, (cutoff_date,), fetch_all=False)
            count = result.get("count", 0) if result else 0
            
            # Delete records
            self.sqlite_db.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff_date,))
            
            return count
                
        except Exception as e:
            self.logger.error(f"Error deleting old records from {table}: {e}")
            return 0