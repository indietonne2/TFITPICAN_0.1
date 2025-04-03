#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: can_interface.py
# Pathname: /path/to/tfitpican/src/can/
# Description: Abstract CAN interface class for TFITPICAN application
# -----------------------------------------------------------------------------

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union

class CANInterface(ABC):
    """Abstract base class for CAN interfaces"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to CAN interface
        
        Returns:
            bool: True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from CAN interface"""
        pass
    
    @abstractmethod
    def send(self, can_id: int, data: List[int], extended: bool = False) -> bool:
        """Send a CAN message
        
        Args:
            can_id: CAN ID
            data: Data bytes (list of integers)
            extended: Whether to use extended frame format
            
        Returns:
            bool: True if message sent successfully
        """
        pass
    
    @abstractmethod
    def receive(self, timeout: float = 0.0) -> Optional[Dict]:
        """Receive a CAN message
        
        Args:
            timeout: Timeout in seconds (0.0 = non-blocking)
            
        Returns:
            CAN message dictionary or None if no message available
        """
        pass
    
    def is_connected(self) -> bool:
        """Check if interface is connected
        
        Returns:
            bool: True if connected
        """
        return self.connected
