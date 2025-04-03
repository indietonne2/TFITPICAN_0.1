#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: error_manager.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Error management system for the TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union
from queue import Queue

class ErrorManager:
    """Centralized error management system for TFITPICAN"""
    
    # Error severity levels
    SEVERITY = {
        "info": 0,
        "warning": 1,
        "error": 2,
        "critical": 3,
        "emergency": 4
    }
    
    def __init__(self, config_path: str = "config/config.json"):
        self.logger = logging.getLogger("ErrorManager")
        self.config = self._load_config(config_path)
        
        # Error storage
        self.active_errors = {}  # Current active errors
        self.error_history = []  # Historical record of all errors
        self.error_counter = 0   # Unique error ID counter
        
        # Event callbacks for error notifications
        self.error_callbacks = []
        
        # Error processing queue and thread
        self.error_queue = Queue()
        self.processing_thread = None
        self.running = False
        
        # Start error processing thread
        self.start()
        
        self.logger.info("Error manager initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            # Basic default config if file can't be loaded
            return {"error_manager": {"max_active_errors": 100}}
    
    def start(self) -> None:
        """Start the error processing thread"""
        if self.running:
            return
            
        self.running = True
        self.processing_thread = threading.Thread(target=self._process_error_queue)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
    def stop(self) -> None:
        """Stop the error processing thread"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
    
    def register_callback(self, callback: Callable[[Dict], None]) -> None:
        """Register a callback function to be notified of errors
        
        Args:
            callback: Function that accepts an error dict as argument
        """
        if callback not in self.error_callbacks:
            self.error_callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[Dict], None]) -> None:
        """Unregister a callback function"""
        if callback in self.error_callbacks:
            self.error_callbacks.remove(callback)
    
    def report_error(self, source: str, error_code: str, message: str, 
                     severity: str = "warning", metadata: Optional[Dict] = None) -> int:
        """Report a new error
        
        Args:
            source: Component that reported the error
            error_code: Error code identifier
            message: Human-readable error message
            severity: Error severity (info, warning, error, critical, emergency)
            metadata: Additional error context
            
        Returns:
            int: Unique error ID
        """
        # Validate severity
        if severity not in self.SEVERITY:
            severity = "warning"
            
        # Create error record
        self.error_counter += 1
        error_id = self.error_counter
        
        error = {
            "id": error_id,
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "code": error_code,
            "message": message,
            "severity": severity,
            "severity_level": self.SEVERITY[severity],
            "metadata": metadata or {},
            "resolved": False,
            "resolution_time": None,
            "resolution_notes": None
        }
        
        # Add to queue for processing (to avoid blocking caller)
        self.error_queue.put(error)
        
        # Log error immediately
        log_message = f"Error {error_id} ({severity}): {source} - {error_code} - {message}"
        
        if severity == "info":
            self.logger.info(log_message)
        elif severity == "warning":
            self.logger.warning(log_message)
        elif severity == "error":
            self.logger.error(log_message)
        else:  # critical or emergency
            self.logger.critical(log_message)
            
        return error_id
        
    def _process_error_queue(self) -> None:
        """Process the error queue in a separate thread"""
        while self.running:
            try:
                # Get error from queue with timeout
                try:
                    error = self.error_queue.get(timeout=1.0)
                except Queue.Empty:
                    continue
                    
                # Add to active errors
                self.active_errors[error["id"]] = error
                
                # Add to history
                self.error_history.append(error)
                
                # Clean up history if too long
                max_history = self.config.get("error_manager", {}).get("max_history", 1000)
                if len(self.error_history) > max_history:
                    self.error_history = self.error_history[-max_history:]
                    
                # Notify callbacks
                for callback in self.error_callbacks:
                    try:
                        callback(error)
                    except Exception as e:
                        self.logger.error(f"Error in error callback: {e}")
                        
                # Mark as processed
                self.error_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error processing error queue: {e}")
                time.sleep(1.0)  # Avoid tight loop if there's an issue
    
    def resolve_error(self, error_id: int, resolution_notes: Optional[str] = None) -> bool:
        """Mark an error as resolved
        
        Args:
            error_id: ID of the error to resolve
            resolution_notes: Optional notes about how it was resolved
            
        Returns:
            bool: True if error was found and resolved, False otherwise
        """
        if error_id not in self.active_errors:
            return False
            
        # Update error
        error = self.active_errors[error_id]
        error["resolved"] = True
        error["resolution_time"] = datetime.now().isoformat()
        error["resolution_notes"] = resolution_notes
        
        # Remove from active errors
        del self.active_errors[error_id]
        
        # Log resolution
        self.logger.info(f"Error {error_id} resolved: {resolution_notes or 'No details provided'}")
        
        return True
    
    def get_active_errors(self, min_severity: Optional[str] = None) -> List[Dict]:
        """Get list of active errors, optionally filtered by minimum severity
        
        Args:
            min_severity: Minimum severity level to include
            
        Returns:
            List of error dictionaries
        """
        if min_severity is None:
            return list(self.active_errors.values())
            
        min_level = self.SEVERITY.get(min_severity, 0)
        return [e for e in self.active_errors.values() if e["severity_level"] >= min_level]
    
    def get_error_history(self, limit: int = 100, 
                         min_severity: Optional[str] = None) -> List[Dict]:
        """Get error history
        
        Args:
            limit: Maximum number of errors to return
            min_severity: Minimum severity level to include
            
        Returns:
            List of error dictionaries, most recent first
        """
        if min_severity is None:
            return self.error_history[-limit:]
            
        min_level = self.SEVERITY.get(min_severity, 0)
        filtered = [e for e in self.error_history if e["severity_level"] >= min_level]
        return filtered[-limit:]
    
    def clear_resolved_errors(self) -> int:
        """Clear all resolved errors from history
        
        Returns:
            int: Number of errors cleared
        """
        original_count = len(self.error_history)
        self.error_history = [e for e in self.error_history if not e["resolved"]]
        return original_count - len(self.error_history)

    def emergency_shutdown(self, reason: str) -> None:
        """Initiate emergency shutdown of system
        
        Args:
            reason: Reason for emergency shutdown
        """
        error_id = self.report_error(
            "ErrorManager", 
            "emergency_shutdown", 
            f"Emergency shutdown: {reason}", 
            severity="emergency"
        )
        
        # Notify all callbacks
        emergency_notification = {
            "id": error_id,
            "action": "emergency_shutdown",
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        for callback in self.error_callbacks:
            try:
                callback(emergency_notification)
            except Exception as e:
                self.logger.critical(f"Failed to notify callback of emergency: {e}")
                
        self.logger.critical(f"EMERGENCY SHUTDOWN INITIATED: {reason}")
