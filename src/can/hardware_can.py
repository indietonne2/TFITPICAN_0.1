#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: hardware_can.py
# Pathname: /path/to/tfitpican/src/can/
# Description: Hardware CAN interface implementation for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import time
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Try to import python-can
try:
    import can
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False

from src.can.can_interface import CANInterface

class HardwareCAN(CANInterface):
    """Hardware CAN interface using python-can library"""
    
    def __init__(self, interface: str = "socketcan", channel: str = "can0", bitrate: int = 500000):
        super().__init__()
        self.logger = logging.getLogger("HardwareCAN")
        
        # Interface settings
        self.interface_type = interface
        self.channel = channel
        self.bitrate = bitrate
        
        # CAN bus instance
        self.bus = None
        
        # Check if python-can is available
        if not CAN_AVAILABLE:
            self.logger.error("python-can library not available, hardware CAN interface cannot be used")
    
    def connect(self) -> bool:
        """Connect to hardware CAN interface
        
        Returns:
            bool: True if connection successful
        """
        if self.connected:
            return True
            
        if not CAN_AVAILABLE:
            self.logger.error("Cannot connect: python-can library not available")
            return False
            
        try:
            # If using socketcan on Linux, try to set up the interface if it's not already up
            if self.interface_type == "socketcan" and os.name == "posix":
                self._setup_socketcan_interface()
                
            # Create CAN bus instance
            self.bus = can.interface.Bus(
                channel=self.channel,
                interface=self.interface_type,
                bitrate=self.bitrate
            )
            
            self.connected = True
            self.logger.info(f"Connected to hardware CAN interface: {self.interface_type}:{self.channel}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to hardware CAN interface: {e}")
            self.bus = None
            return False
    
    def disconnect(self) -> None:
        """Disconnect from hardware CAN interface"""
        if not self.connected:
            return
            
        try:
            if self.bus:
                self.bus.shutdown()
                self.bus = None
                
            self.connected = False
            self.logger.info("Disconnected from hardware CAN interface")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from hardware CAN interface: {e}")
    
    def send(self, can_id: int, data: List[int], extended: bool = False) -> bool:
        """Send a CAN message
        
        Args:
            can_id: CAN ID
            data: Data bytes (list of integers)
            extended: Whether to use extended frame format
            
        Returns:
            bool: True if message sent successfully
        """
        if not self.connected or not self.bus:
            return False
            
        try:
            # Create CAN message
            message = can.Message(
                arbitration_id=can_id,
                data=bytes(data),
                is_extended_id=extended
            )
            
            # Send message
            self.bus.send(message)
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending CAN message: {e}")
            return False
    
    def receive(self, timeout: float = 0.0) -> Optional[Dict]:
        """Receive a CAN message
        
        Args:
            timeout: Timeout in seconds (0.0 = non-blocking)
            
        Returns:
            CAN message dictionary or None if no message available
        """
        if not self.connected or not self.bus:
            return None
            
        try:
            # Receive message from CAN bus
            msg = self.bus.recv(timeout)
            
            if not msg:
                return None
                
            # Convert to dictionary format
            message = {
                "timestamp": msg.timestamp,
                "can_id": msg.arbitration_id,
                "data": list(msg.data),
                "dlc": msg.dlc,
                "extended": msg.is_extended_id,
                "is_rx": True
            }
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error receiving CAN message: {e}")
            return None
    
    def _setup_socketcan_interface(self) -> bool:
        """Set up socketcan interface on Linux
        
        Returns:
            bool: True if setup successful or interface already up
        """
        try:
            # Check if interface is already up
            result = subprocess.run(
                ["ip", "-details", "link", "show", self.channel],
                capture_output=True,
                text=True
            )
            
            # If interface exists and is up, nothing to do
            if result.returncode == 0 and "UP" in result.stdout:
                self.logger.info(f"CAN interface {self.channel} is already up")
                return True
                
            # Try to bring up the interface
            self.logger.info(f"Setting up CAN interface {self.channel}")
            
            # Set bitrate and bring interface up
            subprocess.run(
                ["sudo", "ip", "link", "set", self.channel, "type", "can", "bitrate", str(self.bitrate)],
                check=True
            )
            
            subprocess.run(
                ["sudo", "ip", "link", "set", self.channel, "up"],
                check=True
            )
            
            self.logger.info(f"CAN interface {self.channel} set up successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error setting up CAN interface: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error setting up CAN interface: {e}")
            return False
    
    def get_interface_stats(self) -> Dict:
        """Get statistics for the CAN interface
        
        Returns:
            Dictionary with interface statistics
        """
        stats = {
            "interface": self.interface_type,
            "channel": self.channel,
            "bitrate": self.bitrate,
            "connected": self.connected
        }
        
        # Try to get additional stats for socketcan
        if self.interface_type == "socketcan" and os.name == "posix":
            try:
                result = subprocess.run(
                    ["ip", "-details", "link", "show", self.channel],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Parse statistics from command output
                    output = result.stdout
                    stats["state"] = "UP" if "UP" in output else "DOWN"
                    
                    # Try to extract error counts
                    if "RX: bytes" in output:
                        rx_line = output.split("RX: bytes")[1].split("\n")[0]
                        tx_line = output.split("TX: bytes")[1].split("\n")[0]
                        
                        stats["rx_bytes"] = rx_line.split("bytes")[1].split()[0]
                        stats["rx_packets"] = rx_line.split("packets")[1].split()[0]
                        stats["rx_errors"] = rx_line.split("errors")[1].split()[0]
                        
                        stats["tx_bytes"] = tx_line.split("bytes")[1].split()[0]
                        stats["tx_packets"] = tx_line.split("packets")[1].split()[0]
                        stats["tx_errors"] = tx_line.split("errors")[1].split()[0]
            except Exception:
                # Just ignore errors in stats collection
                pass
                
        return stats