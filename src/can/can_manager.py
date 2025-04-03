#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: can_manager.py
# Pathname: /path/to/tfitpican/src/can/
# Description: CAN bus communication manager for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, Callable

# Try to import python-can
try:
    import can
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False

# Local imports
from src.can.can_interface import CANInterface
from src.can.virtual_can import VirtualCAN
from src.can.hardware_can import HardwareCAN

class CANManager:
    """Manages CAN bus communication for the TFITPICAN application"""
    
    def __init__(self, config_path: str = "config/config.json", error_manager=None):
        self.logger = logging.getLogger("CANManager")
        self.config = self._load_config(config_path)
        self.error_manager = error_manager
        
        # CAN interface and connection state
        self.can_interface = None
        self.connected = False
        
        # Message queue for incoming messages
        self.receive_queue = queue.Queue()
        
        # Callbacks for message reception
        self.message_callbacks = []
        
        # Receiver thread
        self.receiver_thread = None
        self.running = False
        
        # Check if CAN is available
        if not CAN_AVAILABLE:
            self.logger.warning("python-can library not available, using virtual CAN only")
            if self.error_manager:
                self.error_manager.report_error(
                    "CANManager", 
                    "can_unavailable", 
                    "python-can library not available, using virtual CAN only",
                    severity="warning"
                )
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def connect(self) -> bool:
        """Connect to CAN interface
        
        Returns:
            bool: True if connection successful
        """
        if self.connected:
            return True
            
        can_config = self.config.get("can", {})
        interface_type = can_config.get("interface", "virtual")
        
        try:
            # Create appropriate CAN interface
            if interface_type == "virtual":
                self.can_interface = VirtualCAN()
                self.logger.info("Using Virtual CAN interface")
            else:
                # Create hardware CAN interface
                self.can_interface = HardwareCAN(
                    interface=interface_type,
                    channel=can_config.get("channel", "can0"),
                    bitrate=can_config.get("bitrate", 500000)
                )
                self.logger.info(f"Using Hardware CAN interface: {interface_type}:{can_config.get('channel', 'can0')}")
                
            # Connect to interface
            success = self.can_interface.connect()
            
            if not success:
                self.logger.error("Failed to connect to CAN interface")
                if self.error_manager:
                    self.error_manager.report_error(
                        "CANManager", 
                        "can_connection_failed", 
                        f"Failed to connect to CAN interface: {interface_type}",
                        severity="error"
                    )
                return False
                
            # Start receiver thread
            self.running = True
            self.receiver_thread = threading.Thread(target=self._receiver_loop)
            self.receiver_thread.daemon = True
            self.receiver_thread.start()
            
            self.connected = True
            self.logger.info("Connected to CAN interface")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to CAN interface: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "CANManager", 
                    "can_connection_error", 
                    f"Error connecting to CAN interface: {e}",
                    severity="error"
                )
            return False
    
    def disconnect(self) -> None:
        """Disconnect from CAN interface"""
        if not self.connected:
            return
            
        # Stop receiver thread
        self.running = False
        if self.receiver_thread:
            self.receiver_thread.join(timeout=2.0)
            
        # Disconnect interface
        if self.can_interface:
            self.can_interface.disconnect()
            
        self.connected = False
        self.logger.info("Disconnected from CAN interface")
    
    def _receiver_loop(self) -> None:
        """Background thread for receiving CAN messages"""
        self.logger.info("CAN receiver thread started")
        
        while self.running:
            try:
                # Try to receive message from interface
                if self.can_interface:
                    message = self.can_interface.receive(timeout=0.1)
                    
                    if message:
                        # Add to queue
                        self.receive_queue.put(message)
                        
                        # Notify callbacks
                        for callback in self.message_callbacks:
                            try:
                                callback(message)
                            except Exception as e:
                                self.logger.error(f"Error in CAN message callback: {e}")
                else:
                    # No interface, just sleep
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error in CAN receiver thread: {e}")
                if self.error_manager:
                    self.error_manager.report_error(
                        "CANManager", 
                        "can_receiver_error", 
                        f"Error in CAN receiver thread: {e}",
                        severity="error"
                    )
                time.sleep(1.0)  # Delay before retry
                
        self.logger.info("CAN receiver thread stopped")
    
    def send_message(self, can_id: Union[int, str], data: List[int], 
                    extended: bool = False) -> bool:
        """Send a CAN message
        
        Args:
            can_id: CAN ID (integer or hex string)
            data: Data bytes (list of integers)
            extended: Whether to use extended frame format
            
        Returns:
            bool: True if message sent successfully
        """
        if not self.connected:
            if not self.connect():
                return False
                
        # Convert can_id to integer if it's a string
        if isinstance(can_id, str):
            try:
                can_id = int(can_id, 16) if can_id.startswith("0x") else int(can_id)
            except ValueError:
                self.logger.error(f"Invalid CAN ID format: {can_id}")
                return False
                
        # Ensure data is valid
        if len(data) > 8:
            self.logger.error(f"CAN data too long: {len(data)} bytes (max 8)")
            return False
            
        try:
            # Send message through interface
            success = self.can_interface.send(can_id, data, extended)
            
            if not success:
                self.logger.warning(f"Failed to send CAN message with ID: {hex(can_id)}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending CAN message: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "CANManager", 
                    "can_send_error", 
                    f"Error sending CAN message: {e}",
                    severity="error"
                )
            return False
    
    def receive_messages(self, max_messages: int = 10) -> List[Dict]:
        """Receive CAN messages from the queue
        
        Args:
            max_messages: Maximum number of messages to retrieve
            
        Returns:
            List of CAN message dictionaries
        """
        messages = []
        
        # Get messages from queue
        for _ in range(max_messages):
            try:
                message = self.receive_queue.get_nowait()
                messages.append(message)
                self.receive_queue.task_done()
            except queue.Empty:
                break
                
        return messages
    
    def register_callback(self, callback: Callable[[Dict], None]) -> None:
        """Register a callback for message reception
        
        Args:
            callback: Function that takes a CAN message dictionary
        """
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[Dict], None]) -> None:
        """Unregister a callback
        
        Args:
            callback: Previously registered callback function
        """
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)
    
    def clear_receive_queue(self) -> None:
        """Clear the receive queue"""
        while not self.receive_queue.empty():
            try:
                self.receive_queue.get_nowait()
                self.receive_queue.task_done()
            except queue.Empty:
                break
