#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: car_simulator.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Car simulation component for the TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable

class CarSimulator:
    """Simulates vehicle behavior and manages CAN communication"""
    
    def __init__(self, can_manager, error_manager=None):
        self.logger = logging.getLogger("CarSimulator")
        self.can_manager = can_manager
        self.error_manager = error_manager
        
        # Simulation state
        self.running = False
        self.simulation_thread = None
        
        # Vehicle state
        self.vehicle_state = {
            "engine_running": False,
            "engine_rpm": 0,
            "vehicle_speed": 0,
            "throttle_position": 0,
            "brake_pressure": 0,
            "gear": 0,
            "steering_angle": 0,
            "coolant_temp": 80,
            "fuel_level": 100,
            "indicator_left": False,
            "indicator_right": False,
            "headlights": False,
            "doors_locked": True
        }
        
        # Callbacks for state changes
        self.state_callbacks = []
        
        # Register for CAN messages
        self.can_manager.register_callback(self._handle_can_message)
        
        self.logger.info("Car simulator initialized")
    
    def start(self) -> bool:
        """Start the car simulator
        
        Returns:
            bool: True if successful
        """
        if self.running:
            self.logger.warning("Car simulator already running")
            return True
            
        # Start the simulation thread
        self.running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        
        self.logger.info("Car simulator started")
        return True
    
    def stop(self) -> None:
        """Stop the car simulator"""
        if not self.running:
            return
            
        self.running = False
        
        # Wait for simulation thread to end
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
            
        # Reset vehicle state
        self.vehicle_state["engine_running"] = False
        self.vehicle_state["engine_rpm"] = 0
        self.vehicle_state["vehicle_speed"] = 0
        
        # Notify of state change
        self._notify_state_change("engine_running")
        
        self.logger.info("Car simulator stopped")
    
    def emergency_stop(self) -> None:
        """Emergency stop - immediately halt all operations"""
        self.logger.warning("EMERGENCY STOP triggered")
        
        # Report error
        if self.error_manager:
            self.error_manager.report_error(
                "CarSimulator", 
                "emergency_stop", 
                "Emergency stop triggered",
                severity="critical"
            )
            
        # Stop simulator
        self.stop()
    
    def _simulation_loop(self) -> None:
        """Main simulation loop"""
        self.logger.info("Simulation loop started")
        
        update_interval = 0.1  # 100ms update interval
        next_update = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Update vehicle state at regular intervals
                if current_time >= next_update:
                    self._update_vehicle_state()
                    self._send_state_messages()
                    
                    # Schedule next update
                    next_update = current_time + update_interval
                
                # Sleep to prevent tight loop
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"Error in simulation loop: {e}")
                if self.error_manager:
                    self.error_manager.report_error(
                        "CarSimulator", 
                        "simulation_error", 
                        f"Error in simulation loop: {e}",
                        severity="error"
                    )
                time.sleep(1.0)  # Delay before retry
                
        self.logger.info("Simulation loop ended")
    
    def _update_vehicle_state(self) -> None:
        """Update the vehicle state based on current conditions"""
        # Skip update if engine not running
        if not self.vehicle_state["engine_running"]:
            return
            
        # Simple vehicle physics simulation
        
        # Update RPM based on throttle
        target_rpm = 800 + (self.vehicle_state["throttle_position"] * 52)  # 800-6000 RPM range
        current_rpm = self.vehicle_state["engine_rpm"]
        
        # Gradually adjust RPM towards target
        if current_rpm < target_rpm:
            current_rpm = min(current_rpm + 200, target_rpm)
        elif current_rpm > target_rpm:
            current_rpm = max(current_rpm - 100, target_rpm)
            
        self.vehicle_state["engine_rpm"] = current_rpm
        
        # Update speed based on RPM, gear, and brake
        if self.vehicle_state["gear"] > 0:
            target_speed = (current_rpm / 100) * (self.vehicle_state["gear"] / 2)
            target_speed *= (1.0 - (self.vehicle_state["brake_pressure"] / 100))
            
            current_speed = self.vehicle_state["vehicle_speed"]
            
            # Gradually adjust speed towards target
            if current_speed < target_speed:
                current_speed = min(current_speed + 2, target_speed)
            elif current_speed > target_speed:
                current_speed = max(current_speed - 5, target_speed)
                
            self.vehicle_state["vehicle_speed"] = current_speed
        else:
            # Neutral or park
            self.vehicle_state["vehicle_speed"] = 0
            
        # Coolant temperature simulation
        coolant_temp = self.vehicle_state["coolant_temp"]
        if coolant_temp < 90:
            # Warm up
            coolant_temp += 0.1
        elif coolant_temp > 90:
            # Cool down
            coolant_temp -= 0.1
            
        self.vehicle_state["coolant_temp"] = coolant_temp
        
        # Fuel consumption
        fuel_level = self.vehicle_state["fuel_level"]
        fuel_level -= (current_rpm / 100000)  # Very slow consumption for simulation
        self.vehicle_state["fuel_level"] = max(0, fuel_level)
        
        # Notify of state changes
        self._notify_state_change("all")
    
    def _send_state_messages(self) -> None:
        """Send CAN messages for the current vehicle state"""
        if not self.can_manager:
            return
            
        # Engine RPM - ID 0x100
        rpm = int(self.vehicle_state["engine_rpm"])
        self.can_manager.send_message(0x100, [rpm & 0xFF, (rpm >> 8) & 0xFF, 0, 0, 0, 0, 0, 0])
        
        # Vehicle Speed - ID 0x200
        speed = int(self.vehicle_state["vehicle_speed"])
        self.can_manager.send_message(0x200, [speed & 0xFF, 0, 0, 0, 0, 0, 0, 0])
        
        # Coolant Temperature - ID 0x300
        temp = int(self.vehicle_state["coolant_temp"])
        self.can_manager.send_message(0x300, [temp & 0xFF, 0, 0, 0, 0, 0, 0, 0])
        
        # Throttle Position - ID 0x400
        throttle = int(self.vehicle_state["throttle_position"])
        self.can_manager.send_message(0x400, [throttle & 0xFF, 0, 0, 0, 0, 0, 0, 0])
        
        # Brake Pressure - ID 0x500
        brake = int(self.vehicle_state["brake_pressure"])
        self.can_manager.send_message(0x500, [brake & 0xFF, 0, 0, 0, 0, 0, 0, 0])
        
        # Gear and indicators - ID 0x600
        gear = self.vehicle_state["gear"] & 0x0F
        indicators = 0
        if self.vehicle_state["indicator_left"]:
            indicators |= 0x01
        if self.vehicle_state["indicator_right"]:
            indicators |= 0x02
        if self.vehicle_state["headlights"]:
            indicators |= 0x04
        if self.vehicle_state["doors_locked"]:
            indicators |= 0x08
            
        self.can_manager.send_message(0x600, [gear, indicators, 0, 0, 0, 0, 0, 0])
    
    def _handle_can_message(self, message: Dict) -> None:
        """Handle incoming CAN message
        
        Args:
            message: CAN message dictionary
        """
        can_id = message["can_id"]
        data = message["data"]
        
        # Process based on CAN ID
        if can_id == 0x101:  # Engine control
            if len(data) >= 1:
                command = data[0]
                if command == 0x01:  # Start engine
                    self.start_engine()
                elif command == 0x02:  # Stop engine
                    self.stop_engine()
                    
        elif can_id == 0x102:  # Throttle control
            if len(data) >= 1:
                throttle = data[0]
                self.set_throttle(throttle)
                
        elif can_id == 0x103:  # Brake control
            if len(data) >= 1:
                brake = data[0]
                self.set_brake(brake)
                
        elif can_id == 0x104:  # Gear control
            if len(data) >= 1:
                gear = data[0] & 0x0F
                self.set_gear(gear)
    
    def register_state_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback for state changes
        
        Args:
            callback: Function that takes state key and new value
        """
        if callback not in self.state_callbacks:
            self.state_callbacks.append(callback)
    
    def unregister_state_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Unregister a state change callback
        
        Args:
            callback: Previously registered callback function
        """
        if callback in self.state_callbacks:
            self.state_callbacks.remove(callback)
    
    def _notify_state_change(self, key: str) -> None:
        """Notify callbacks of state change
        
        Args:
            key: State key that changed, or "all" for all keys
        """
        if key == "all":
            # Notify for all keys
            for k, v in self.vehicle_state.items():
                for callback in self.state_callbacks:
                    try:
                        callback(k, v)
                    except Exception as e:
                        self.logger.error(f"Error in state callback: {e}")
        else:
            # Notify for specific key
            value = self.vehicle_state.get(key)
            for callback in self.state_callbacks:
                try:
                    callback(key, value)
                except Exception as e:
                    self.logger.error(f"Error in state callback: {e}")
    
    # Public API for controlling the vehicle
    
    def start_engine(self) -> bool:
        """Start the engine
        
        Returns:
            bool: True if successful
        """
        if self.vehicle_state["engine_running"]:
            return True
            
        self.vehicle_state["engine_running"] = True
        self.vehicle_state["engine_rpm"] = 800  # Idle RPM
        
        self._notify_state_change("engine_running")
        self._notify_state_change("engine_rpm")
        
        self.logger.info("Engine started")
        return True
    
    def stop_engine(self) -> bool:
        """Stop the engine
        
        Returns:
            bool: True if successful
        """
        if not self.vehicle_state["engine_running"]:
            return True
            
        self.vehicle_state["engine_running"] = False
        self.vehicle_state["engine_rpm"] = 0
        self.vehicle_state["throttle_position"] = 0
        
        self._notify_state_change("engine_running")
        self._notify_state_change("engine_rpm")
        self._notify_state_change("throttle_position")
        
        self.logger.info("Engine stopped")
        return True
    
    def set_throttle(self, position: int) -> None:
        """Set throttle position
        
        Args:
            position: Throttle position (0-100)
        """
        position = max(0, min(100, position))
        self.vehicle_state["throttle_position"] = position
        self._notify_state_change("throttle_position")
    
    def set_brake(self, pressure: int) -> None:
        """Set brake pressure
        
        Args:
            pressure: Brake pressure (0-100)
        """
        pressure = max(0, min(100, pressure))
        self.vehicle_state["brake_pressure"] = pressure
        self._notify_state_change("brake_pressure")
    
    def set_gear(self, gear: int) -> None:
        """Set transmission gear
        
        Args:
            gear: Gear position (0=P, 1-6=Forward gears, 7=R)
        """
        gear = max(0, min(7, gear))
        self.vehicle_state["gear"] = gear
        self._notify_state_change("gear")
    
    def toggle_headlights(self) -> None:
        """Toggle headlights on/off"""
        self.vehicle_state["headlights"] = not self.vehicle_state["headlights"]
        self._notify_state_change("headlights")
    
    def toggle_left_indicator(self) -> None:
        """Toggle left indicator on/off"""
        self.vehicle_state["indicator_left"] = not self.vehicle_state["indicator_left"]
        self._notify_state_change("indicator_left")
    
    def toggle_right_indicator(self) -> None:
        """Toggle right indicator on/off"""
        self.vehicle_state["indicator_right"] = not self.vehicle_state["indicator_right"]
        self._notify_state_change("indicator_right")
    
    def toggle_door_locks(self) -> None:
        """Toggle door locks on/off"""
        self.vehicle_state["doors_locked"] = not self.vehicle_state["doors_locked"]
        self._notify_state_change("doors_locked")
        
    def get_vehicle_state(self) -> Dict:
        """Get the current vehicle state
        
        Returns:
            Dictionary with vehicle state
        """
        return self.vehicle_state.copy()