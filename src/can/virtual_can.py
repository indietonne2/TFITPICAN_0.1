#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: virtual_can.py
# Pathname: /path/to/tfitpican/src/can/
# Description: Virtual CAN interface implementation for TFITPICAN application
# -----------------------------------------------------------------------------

import time
import random
import logging
import threading
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from src.can.can_interface import CANInterface

class VirtualCAN(CANInterface):
    """Virtual CAN interface for simulation"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("VirtualCAN")
        
        # Message queues
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        
        # Simulation thread
        self.simulation_thread = None
        self.running = False
        
        # Traffic generator settings
        self.generate_traffic = True
        self.traffic_rate = 10.0  # messages per second
        
        # Known CAN IDs for simulation
        self.simulated_ids = [
            0x100,  # Engine RPM
            0x200,  # Vehicle Speed
            0x300,  # Coolant Temperature
            0x400,  # Throttle Position
            0x500   # Brake Pressure
        ]
    
    def connect(self) -> bool:
        """Connect to virtual CAN interface
        
        Returns:
            bool: True (always succeeds for virtual interface)
        """
        if self.connected:
            return True
            
        # Start simulation thread
        self.running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        
        self.connected = True
        self.logger.info("Connected to virtual CAN interface")
        return True
    
    def disconnect(self) -> None:
        """Disconnect from virtual CAN interface"""
        if not self.connected:
            return
            
        # Stop simulation thread
        self.running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
            
        self.connected = False
        self.logger.info("Disconnected from virtual CAN interface")
    
    def send(self, can_id: int, data: List[int], extended: bool = False) -> bool:
        """Send a CAN message
        
        Args:
            can_id: CAN ID
            data: Data bytes (list of integers)
            extended: Whether to use extended frame format
            
        Returns:
            bool: True (always succeeds for virtual interface)
        """
        if not self.connected:
            return False
            
        # Create message dictionary
        message = {
            "timestamp": datetime.now().timestamp(),
            "can_id": can_id,
            "data": data.copy(),
            "dlc": len(data),
            "extended": extended,
            "is_rx": False
        }
        
        # Add to transmit queue
        self.tx_queue.put(message)
        
        # For virtual interface, loopback message to receive queue as well
        rx_message = message.copy()
        rx_message["is_rx"] = True
        self.rx_queue.put(rx_message)
        
        return True
    
    def receive(self, timeout: float = 0.0) -> Optional[Dict]:
        """Receive a CAN message
        
        Args:
            timeout: Timeout in seconds (0.0 = non-blocking)
            
        Returns:
            CAN message dictionary or None if no message available
        """
        if not self.connected:
            return None
            
        try:
            # Get message from receive queue
            message = self.rx_queue.get(block=timeout > 0.0, timeout=timeout if timeout > 0.0 else None)
            self.rx_queue.task_done()
            return message
        except queue.Empty:
            return None
    
    def _simulation_loop(self) -> None:
        """Background thread for simulating CAN traffic"""
        self.logger.info("Virtual CAN simulation thread started")
        
        next_msg_time = time.time()
        
        while self.running:
            try:
                # Process messages from tx queue (just for monitoring)
                while not self.tx_queue.empty():
                    message = self.tx_queue.get_nowait()
                    self.logger.debug(f"TX: ID={hex(message['can_id'])} Data={[hex(b) for b in message['data']]}")
                    self.tx_queue.task_done()
                
                current_time = time.time()
                
                # Generate simulated traffic if enabled
                if self.generate_traffic and current_time >= next_msg_time:
                    self._generate_random_message()
                    
                    # Schedule next message
                    next_msg_time = current_time + (1.0 / self.traffic_rate)
                
                # Small sleep to prevent tight loop
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"Error in virtual CAN simulation: {e}")
                time.sleep(1.0)  # Delay before retry
                
        self.logger.info("Virtual CAN simulation thread stopped")
    
    def _generate_random_message(self) -> None:
        """Generate a random CAN message for simulation"""
        # Select a random CAN ID from known IDs
        can_id = random.choice(self.simulated_ids)
        
        # Generate data based on CAN ID
        if can_id == 0x100:  # Engine RPM
            # RPM range: 800-6000
            rpm = random.randint(800, 6000)
            data = [rpm & 0xFF, (rpm >> 8) & 0xFF, 0, 0, 0, 0, 0, 0]
        elif can_id == 0x200:  # Vehicle Speed
            # Speed range: 0-200 km/h
            speed = random.randint(0, 200)
            data = [speed & 0xFF, 0, 0, 0, 0, 0, 0, 0]
        elif can_id == 0x300:  # Coolant Temperature
            # Temperature range: 60-120 °C
            temp = random.randint(60, 120)
            data = [temp & 0xFF, 0, 0, 0, 0, 0, 0, 0]
        elif can_id == 0x400:  # Throttle Position
            # Throttle range: 0-100%
            throttle = random.randint(0, 100)
            data = [throttle & 0xFF, 0, 0, 0, 0, 0, 0, 0]
        elif can_id == 0x500:  # Brake Pressure
            # Brake pressure range: 0-100%
            brake = random.randint(0, 100)
            data = [brake & 0xFF, 0, 0, 0, 0, 0, 0, 0]
        else:
            # Random data for other IDs
            data = [random.randint(0, 255) for _ in range(8)]
        
        # Create message dictionary
        message = {
            "timestamp": datetime.now().timestamp(),
            "can_id": can_id,
            "data": data,
            "dlc": len(data),
            "extended": False,
            "is_rx": True
        }
        
        # Add to receive queue
        self.rx_queue.put(message)
    
    def set_traffic_rate(self, rate: float) -> None:
        """Set the rate of simulated traffic
        
        Args:
            rate: Messages per second
        """
        self.traffic_rate = max(0.1, min(100.0, rate))
        self.logger.info(f"Virtual CAN traffic rate set to {self.traffic_rate} msg/s")
    
    def enable_traffic_generation(self, enable: bool) -> None:
        """Enable or disable simulated traffic generation
        
        Args:
            enable: True to enable, False to disable
        """
        self.generate_traffic = enable
        self.logger.info(f"Virtual CAN traffic generation {'enabled' if enable else 'disabled'}")
    
    def add_simulated_id(self, can_id: int) -> None:
        """Add a CAN ID to the simulation
        
        Args:
            can_id: CAN ID to add
        """
        if can_id not in self.simulated_ids:
            self.simulated_ids.append(can_id)
            self.logger.debug(f"Added CAN ID {hex(can_id)} to simulation")