#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: bluetooth_comm.py
# Pathname: /path/to/tfitpican/src/comm/
# Description: Bluetooth communication module for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import sys
import json
import time
import logging
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union, Tuple

# Try importing Bluetooth libraries with fallbacks
try:
    import bluetooth
    BLUETOOTH_AVAILABLE = True
except ImportError:
    try:
        # Try alternative library (Bleak for cross-platform BLE)
        import bleak
        BLUETOOTH_AVAILABLE = True
        USE_BLEAK = True
    except ImportError:
        BLUETOOTH_AVAILABLE = False
        USE_BLEAK = False

class BluetoothComm:
    """Manages Bluetooth communication between devices running TFITPICAN"""
    
    def __init__(self, config_path: str = "config/config.json", error_manager=None):
        self.logger = logging.getLogger("BluetoothComm")
        self.config = self._load_config(config_path)
        self.error_manager = error_manager
        
        # Bluetooth device state
        self.device_name = self.config.get("bluetooth", {}).get("device_name", "TFITPICAN")
        self.device_uuid = str(uuid.uuid4())
        self.is_primary = False
        self.connected_devices = {}  # Map of device_id -> device_info
        self.paired_roles = {}       # Map of device_id -> assigned role
        
        # Connection state
        self.server_socket = None
        self.is_connected = False
        self.discovery_thread = None
        self.server_thread = None
        self.running = False
        
        # Communication callbacks
        self.message_callbacks = {}  # Map of message_type -> list of callbacks
        
        # Check if Bluetooth is available
        if not BLUETOOTH_AVAILABLE:
            self.logger.warning("Bluetooth libraries not available, functionality limited")
            if self.error_manager:
                self.error_manager.report_error(
                    "BluetoothComm", 
                    "bluetooth_unavailable", 
                    "Bluetooth libraries not available, functionality limited",
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
            
    def start_pairing(self) -> bool:
        """Start the Bluetooth pairing process
        
        Returns:
            bool: True if pairing started successfully, False otherwise
        """
        if not BLUETOOTH_AVAILABLE:
            self.logger.error("Bluetooth unavailable, cannot start pairing")
            return False
            
        if self.running:
            self.logger.warning("Bluetooth service already running")
            return True
            
        self.running = True
        
        # Start discovery thread
        self.discovery_thread = threading.Thread(target=self._discovery_loop)
        self.discovery_thread.daemon = True
        self.discovery_thread.start()
        
        # Start server thread to accept connections
        self.server_thread = threading.Thread(target=self._server_loop)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.logger.info("Bluetooth pairing started")
        return True
        
    def stop(self) -> None:
        """Stop all Bluetooth communication"""
        if not self.running:
            return
            
        self.running = False
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        # Wait for threads to terminate
        if self.discovery_thread:
            self.discovery_thread.join(timeout=2.0)
        if self.server_thread:
            self.server_thread.join(timeout=2.0)
            
        # Disconnect from all devices
        for device_id in list(self.connected_devices.keys()):
            self._disconnect_device(device_id)
            
        self.logger.info("Bluetooth service stopped")
            
    def _discovery_loop(self) -> None:
        """Thread for discovering other TFITPICAN devices"""
        self.logger.info("Bluetooth discovery started")
        
        scan_interval = self.config.get("bluetooth", {}).get("scan_interval_sec", 30)
        
        while self.running:
            try:
                if USE_BLEAK:
                    self._discover_devices_bleak()
                else:
                    self._discover_devices_pybluez()
                    
                # Sleep until next scan
                time.sleep(scan_interval)
                
            except Exception as e:
                self.logger.error(f"Error in Bluetooth discovery: {e}")
                if self.error_manager:
                    self.error_manager.report_error(
                        "BluetoothComm", 
                        "discovery_error", 
                        f"Error in Bluetooth discovery: {e}",
                        severity="error"
                    )
                time.sleep(5)  # Short delay before retry
                
        self.logger.info("Bluetooth discovery stopped")
                
    def _discover_devices_pybluez(self) -> None:
        """Discover nearby devices using PyBluez"""
        self.logger.info("Scanning for nearby devices...")
        
        try:
            nearby_devices = bluetooth.discover_devices(
                duration=8, 
                lookup_names=True,
                flush_cache=True,
                lookup_class=False
            )
            
            for addr, name in nearby_devices:
                self.logger.info(f"Found device: {name} ({addr})")
                
                # Check if this is a TFITPICAN device
                if "TFITPICAN" in name:
                    # Try to connect
                    self._connect_to_device(addr, name)
                    
        except Exception as e:
            self.logger.error(f"Error scanning for devices: {e}")
            
    def _discover_devices_bleak(self) -> None:
        """Discover nearby devices using Bleak (BLE)"""
        import asyncio
        from bleak import BleakScanner
        
        self.logger.info("Scanning for nearby BLE devices...")
        
        async def scan():
            devices = await BleakScanner.discover()
            for device in devices:
                self.logger.info(f"Found device: {device.name} ({device.address})")
                
                # Check if this is a TFITPICAN device
                if device.name and "TFITPICAN" in device.name:
                    # Try to connect
                    self._connect_to_device_ble(device.address, device.name)
                    
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(scan())
        
    def _server_loop(self) -> None:
        """Thread for accepting incoming connections"""
        if not BLUETOOTH_AVAILABLE:
            return
            
        self.logger.info("Starting Bluetooth server...")
        
        try:
            if not USE_BLEAK:
                # Using PyBluez
                self.server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
                self.server_socket.bind(("", bluetooth.PORT_ANY))
                self.server_socket.listen(1)
                
                port = self.server_socket.getsockname()[1]
                
                # Advertise service
                service_uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"
                bluetooth.advertise_service(
                    self.server_socket, 
                    "TFITPICAN",
                    service_id=service_uuid,
                    service_classes=[service_uuid, bluetooth.SERIAL_PORT_CLASS],
                    profiles=[bluetooth.SERIAL_PORT_PROFILE]
                )
                
                self.logger.info(f"Bluetooth server started on RFCOMM channel {port}")
                
                # Accept connections
                while self.running:
                    try:
                        client_sock, client_info = self.server_socket.accept()
                        self.logger.info(f"Accepted connection from {client_info}")
                        
                        # Handle connection in a new thread
                        client_thread = threading.Thread(
                            target=self._handle_client,
                            args=(client_sock, client_info)
                        )
                        client_thread.daemon = True
                        client_thread.start()
                        
                    except bluetooth.btcommon.BluetoothError as e:
                        if not self.running:
                            break  # Normal shutdown
                        self.logger.error(f"Bluetooth server error: {e}")
                        time.sleep(1)
            else:
                # Using Bleak (BLE)
                self.logger.info("BLE server functionality not fully implemented")
                # BLE server implementation would go here
                # This is more complex with Bleak and requires platform-specific code
                pass
                
        except Exception as e:
            self.logger.error(f"Error in Bluetooth server: {e}")
            if self.error_manager:
                self.error_manager.report_error(
                    "BluetoothComm", 
                    "server_error", 
                    f"Error in Bluetooth server: {e}",
                    severity="error"
                )
        finally:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
                
        self.logger.info("Bluetooth server stopped")
    
    def _handle_client(self, client_sock, client_info) -> None:
        """Handle a connected client"""
        device_id = str(client_info)
        
        try:
            # Register device
            self.connected_devices[device_id] = {
                "address": client_info,
                "name": "Unknown",
                "socket": client_sock,
                "connected_time": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat()
            }
            
            # Handshake to exchange device info
            self._send_handshake(client_sock)
            
            # Main communication loop
            buffer = ""
            while self.running:
                try:
                    data = client_sock.recv(1024)
                    if not data:
                        break  # Disconnected
                        
                    # Process received data
                    buffer += data.decode('utf-8')
                    
                    # Process complete messages
                    while '\n' in buffer:
                        message, buffer = buffer.split('\n', 1)
                        self._process_message(device_id, message)
                        
                    # Update last seen
                    self.connected_devices[device_id]["last_seen"] = datetime.now().isoformat()
                    
                except Exception as e:
                    self.logger.error(f"Error receiving data from {device_id}: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"Error handling client {device_id}: {e}")
        finally:
            # Clean up connection
            self._disconnect_device(device_id)
            
    def _connect_to_device(self, address, name) -> bool:
        """Connect to a device using PyBluez"""
        device_id = str(address)
        
        # Check if already connected
        if device_id in self.connected_devices:
            return True
            
        try:
            # Connect to the RFCOMM service
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            
            # Find the TFITPICAN service
            services = bluetooth.find_service(
                uuid="94f39d29-7d6d-437d-973b-fba39e49d4ee",
                address=address
            )
            
            if not services:
                self.logger.warning(f"No TFITPICAN service found on device {name}")
                return False
                
            first_match = services[0]
            port = first_match["port"]
            host = first_match["host"]
            
            # Connect to service
            sock.connect((host, port))
            
            # Register device
            self.connected_devices[device_id] = {
                "address": address,
                "name": name,
                "socket": sock,
                "connected_time": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat()
            }
            
            # Start handler thread
            handler_thread = threading.Thread(
                target=self._handle_client,
                args=(sock, address)
            )
            handler_thread.daemon = True
            handler_thread.start()
            
            self.logger.info(f"Connected to device {name} ({address})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to device {name} ({address}): {e}")
            return False
            
    def _connect_to_device_ble(self, address, name) -> bool:
        """Connect to a device using Bleak (BLE)"""
        # BLE connection implementation would go here
        # This is more complex with Bleak and requires async code
        
        # Placeholder for demonstration
        self.logger.info(f"BLE connection to {name} would be handled here")
        return False
            
    def _disconnect_device(self, device_id) -> None:
        """Disconnect and cleanup a device connection"""
        if device_id not in self.connected_devices:
            return
            
        device = self.connected_devices[device_id]
        
        try:
            # Close socket
            if "socket" in device:
                device["socket"].close()
                
            # Remove from connected devices
            del self.connected_devices[device_id]
            
            # Remove from paired roles if present
            if device_id in self.paired_roles:
                del self.paired_roles[device_id]
                
            self.logger.info(f"Disconnected device {device.get('name', device_id)}")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting device {device_id}: {e}")
            
    def _send_handshake(self, sock) -> None:
        """Send initial handshake message to establish connection"""
        handshake = {
            "type": "handshake",
            "device_name": self.device_name,
            "device_uuid": self.device_uuid,
            "is_primary": self.is_primary,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            message = json.dumps(handshake) + "\n"
            sock.send(message.encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Error sending handshake: {e}")
            
    def _process_message(self, device_id, message) -> None:
        """Process a received message"""
        try:
            data = json.loads(message)
            message_type = data.get("type", "unknown")
            
            self.logger.debug(f"Received {message_type} message from {device_id}")
            
            # Handle specific message types
            if message_type == "handshake":
                self._handle_handshake(device_id, data)
            elif message_type == "role_info":
                self._handle_role_info(device_id, data)
            elif message_type == "status":
                self._handle_status(device_id, data)
                
            # Call registered callbacks
            if message_type in self.message_callbacks:
                for callback in self.message_callbacks[message_type]:
                    try:
                        callback(device_id, data)
                    except Exception as e:
                        self.logger.error(f"Error in message callback: {e}")
                        
        except json.JSONDecodeError:
            self.logger.error(f"Received invalid JSON from {device_id}: {message}")
        except Exception as e:
            self.logger.error(f"Error processing message from {device_id}: {e}")
            
    def _handle_handshake(self, device_id, data) -> None:
        """Handle a handshake message"""
        if device_id in self.connected_devices:
            # Update device info
            self.connected_devices[device_id].update({
                "name": data.get("device_name", "Unknown"),
                "uuid": data.get("device_uuid", ""),
                "is_primary": data.get("is_primary", False)
            })
            
            self.logger.info(f"Handshake completed with {data.get('device_name', device_id)}")
            
    def _handle_role_info(self, device_id, data) -> None:
        """Handle a role info message"""
        role = data.get("role")
        if role and device_id in self.connected_devices:
            self.paired_roles[device_id] = role
            self.logger.info(f"Device {self.connected_devices[device_id].get('name', device_id)} assigned role: {role}")
            
    def _handle_status(self, device_id, data) -> None:
        """Handle a status update message"""
        if device_id in self.connected_devices:
            # Update device status
            if "status" in data:
                self.connected_devices[device_id]["status"] = data["status"]
                
            # Log status change if significant
            if "state_change" in data:
                self.logger.info(f"Device {self.connected_devices[device_id].get('name', device_id)} state changed to: {data['state_change']}")
    
    def register_callback(self, message_type: str, callback: Callable[[str, Dict], None]) -> None:
        """Register a callback for a specific message type
        
        Args:
            message_type: Type of message to listen for
            callback: Function taking device_id and message data arguments
        """
        if message_type not in self.message_callbacks:
            self.message_callbacks[message_type] = []
            
        if callback not in self.message_callbacks[message_type]:
            self.message_callbacks[message_type].append(callback)
            
    def unregister_callback(self, message_type: str, callback: Callable[[str, Dict], None]) -> None:
        """Unregister a callback"""
        if message_type in self.message_callbacks and callback in self.message_callbacks[message_type]:
            self.message_callbacks[message_type].remove(callback)
            
    def send_role_info(self, role_data: Dict) -> bool:
        """Send role information to all connected devices
        
        Args:
            role_data: Role information to send
            
        Returns:
            bool: True if message was sent to at least one device
        """
        message = {
            "type": "role_info",
            "role": role_data,
            "timestamp": datetime.now().isoformat()
        }
        
        return self._broadcast_message(message)
        
    def send_status_update(self, status: Dict) -> bool:
        """Send status update to all connected devices
        
        Args:
            status: Status information to send
            
        Returns:
            bool: True if message was sent to at least one device
        """
        message = {
            "type": "status",
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        return self._broadcast_message(message)
        
    def _broadcast_message(self, message: Dict) -> bool:
        """Send a message to all connected devices
        
        Args:
            message: Message dictionary to send
            
        Returns:
            bool: True if message was sent to at least one device
        """
        if not self.connected_devices:
            return False
            
        sent_count = 0
        message_str = json.dumps(message) + "\n"
        message_bytes = message_str.encode('utf-8')
        
        for device_id, device in list(self.connected_devices.items()):
            try:
                if "socket" in device:
                    device["socket"].send(message_bytes)
                    sent_count += 1
            except Exception as e:
                self.logger.error(f"Error sending message to {device.get('name', device_id)}: {e}")
                # Disconnect problematic device
                self._disconnect_device(device_id)
                
        return sent_count > 0
        
    def set_primary(self, is_primary: bool) -> None:
        """Set whether this device is the primary controller
        
        Args:
            is_primary: True if this device is primary controller
        """
        if self.is_primary != is_primary:
            self.is_primary = is_primary
            self.logger.info(f"Device role set to {'PRIMARY' if is_primary else 'SECONDARY'}")
            
            # Notify connected devices of role change
            status = {
                "is_primary": is_primary,
                "state_change": "primary_role_change"
            }
            self.send_status_update(status)
            
    def get_connected_devices(self) -> List[Dict]:
        """Get list of connected devices
        
        Returns:
            List of device information dictionaries
        """
        return [
            {
                "id": device_id,
                "name": info.get("name", "Unknown"),
                "address": info.get("address", ""),
                "is_primary": info.get("is_primary", False),
                "connected_time": info.get("connected_time", ""),
                "last_seen": info.get("last_seen", ""),
                "role": self.paired_roles.get(device_id, "unknown"),
                "status": info.get("status", {})
            }
            for device_id, info in self.connected_devices.items()
        ]
        
    def get_device_role(self, device_id: str) -> Optional[str]:
        """Get the role assigned to a specific device
        
        Args:
            device_id: Device identifier
            
        Returns:
            String role name or None if device not found/no role assigned
        """
        return self.paired_roles.get(device_id)
        
    def assign_device_role(self, device_id: str, role: str) -> bool:
        """Assign a role to a connected device
        
        Args:
            device_id: Device identifier
            role: Role to assign
            
        Returns:
            bool: True if role was assigned, False if device not found
        """
        if device_id not in self.connected_devices:
            return False
            
        # Assign role locally
        self.paired_roles[device_id] = role
        
        # Send role information to the device
        device = self.connected_devices[device_id]
        message = {
            "type": "role_info",
            "role": role,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            message_str = json.dumps(message) + "\n"
            device["socket"].send(message_str.encode('utf-8'))
            self.logger.info(f"Assigned role '{role}' to device {device.get('name', device_id)}")
            return True
        except Exception as e:
            self.logger.error(f"Error sending role to {device.get('name', device_id)}: {e}")
            return False