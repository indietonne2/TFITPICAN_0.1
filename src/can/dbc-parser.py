#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: dbc_parser.py
# Pathname: src/can/
# Description: DBC file parser for decoding and encoding CAN messages
# -----------------------------------------------------------------------------

import os
import re
import logging
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable

# Try importing cantools, fall back to custom implementation if not available
try:
    import cantools
    CANTOOLS_AVAILABLE = True
except ImportError:
    CANTOOLS_AVAILABLE = False

class DBCParser:
    """Parser for DBC files to decode and encode CAN messages"""
    
    def __init__(self, error_manager=None):
        self.logger = logging.getLogger("DBCParser")
        self.error_manager = error_manager
        
        # Loaded DBC databases
        self.dbc_databases = {}
        
        # Signal callback for decoded signals
        self.signal_callbacks = []
        
        # Check if cantools is available
        if not CANTOOLS_AVAILABLE:
            self.logger.warning("cantools library not available, using limited custom implementation")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "DBCParser", 
                    "cantools_unavailable", 
                    "cantools library not available, using limited custom implementation",
                    severity="warning"
                )
                
        self.logger.info("DBC Parser initialized")
    
    def load_dbc_file(self, file_path: str, db_name: Optional[str] = None) -> bool:
        """Load a DBC file
        
        Args:
            file_path: Path to DBC file
            db_name: Optional name for the database
            
        Returns:
            bool: True if file was loaded successfully
        """
        if not os.path.exists(file_path):
            self.logger.error(f"DBC file not found: {file_path}")
            return False
            
        # Use filename as db_name if not provided
        if db_name is None:
            db_name = os.path.splitext(os.path.basename(file_path))[0]
            
        try:
            if CANTOOLS_AVAILABLE:
                # Use cantools to load the DBC file
                db = cantools.database.load_file(file_path)
                self.dbc_databases[db_name] = db
                
                # Log information about loaded database
                message_count = len(db.messages)
                self.logger.info(f"Loaded DBC file {file_path} with {message_count} messages as '{db_name}'")
                
                return True
            else:
                # Use custom implementation
                db = self._load_dbc_custom(file_path)
                if db:
                    self.dbc_databases[db_name] = db
                    
                    # Log information about loaded database
                    message_count = len(db.get("messages", {}))
                    self.logger.info(f"Loaded DBC file {file_path} with {message_count} messages as '{db_name}'")
                    
                    return True
                else:
                    self.logger.error(f"Failed to parse DBC file: {file_path}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error loading DBC file {file_path}: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "DBCParser", 
                    "dbc_load_error", 
                    f"Error loading DBC file {file_path}: {e}",
                    severity="error"
                )
                
            return False
    
    def _load_dbc_custom(self, file_path: str) -> Dict:
        """Custom implementation for loading DBC files when cantools is not available
        
        Args:
            file_path: Path to DBC file
            
        Returns:
            Dict with parsed DBC information
        """
        try:
            # Initialize database structure
            db = {
                "messages": {},
                "signals": {},
                "value_tables": {}
            }
            
            # Read file contents
            with open(file_path, 'r', errors='replace') as f:
                content = f.read()
                
            # Parse messages
            message_pattern = r'BO_ (\d+) (\w+): (\d+) (\w+)'
            for match in re.finditer(message_pattern, content):
                can_id, name, dlc, sender = match.groups()
                
                db["messages"][int(can_id)] = {
                    "name": name,
                    "id": int(can_id),
                    "dlc": int(dlc),
                    "sender": sender,
                    "signals": {}
                }
                
            # Parse signals
            signal_pattern = r'SG_ (\w+) : (\d+)\|(\d+)@(\d+)([+-]) \(([^,]+),([^)]+)\) \[([^|]+)\|([^]]+)\] "(.*?)" (.*)'
            current_message_id = None
            
            for line in content.split('\n'):
                # Check for message definition
                msg_match = re.match(r'BO_ (\d+)', line)
                if msg_match:
                    current_message_id = int(msg_match.group(1))
                    
                # Check for signal definition
                sig_match = re.match(signal_pattern, line)
                if sig_match and current_message_id is not None:
                    (name, start_bit, length, byte_order, sign,
                     factor, offset, minimum, maximum, unit, receivers) = sig_match.groups()
                    
                    # Create signal definition
                    signal = {
                        "name": name,
                        "start_bit": int(start_bit),
                        "length": int(length),
                        "byte_order": "little_endian" if byte_order == "1" else "big_endian",
                        "is_signed": sign == "-",
                        "factor": float(factor),
                        "offset": float(offset),
                        "minimum": float(minimum) if minimum else None,
                        "maximum": float(maximum) if maximum else None,
                        "unit": unit,
                        "receivers": receivers.split()
                    }
                    
                    # Add to message
                    if current_message_id in db["messages"]:
                        db["messages"][current_message_id]["signals"][name] = signal
                    
            # Parse value tables (simple implementation)
            val_table_pattern = r'VAL_ (\d+) (\w+) (.*);'
            for match in re.finditer(val_table_pattern, content):
                msg_id, signal_name, values = match.groups()
                
                # Parse value mappings
                value_map = {}
                for val_match in re.finditer(r'(\d+) "([^"]+)"', values):
                    val, desc = val_match.groups()
                    value_map[int(val)] = desc
                    
                # Store in database
                key = f"{msg_id}_{signal_name}"
                db["value_tables"][key] = value_map
                
            return db
            
        except Exception as e:
            self.logger.error(f"Error in custom DBC parser: {e}")
            return None
    
    def unload_dbc(self, db_name: str) -> bool:
        """Unload a DBC database
        
        Args:
            db_name: Name of the database to unload
            
        Returns:
            bool: True if database was unloaded
        """
        if db_name in self.dbc_databases:
            del self.dbc_databases[db_name]
            self.logger.info(f"Unloaded DBC database: {db_name}")
            return True
        else:
            self.logger.warning(f"DBC database not found: {db_name}")
            return False
    
    def decode_message(self, can_id: Union[int, str], data: Union[List[int], bytes, str], 
                      db_name: Optional[str] = None) -> Optional[Dict]:
        """Decode a CAN message
        
        Args:
            can_id: CAN message ID
            data: Message data (bytes, list of integers, or hex string)
            db_name: Optional database name (uses first available if None)
            
        Returns:
            Dict with decoded signals or None if decoding failed
        """
        # Ensure can_id is an integer
        if isinstance(can_id, str):
            try:
                can_id = int(can_id, 16) if can_id.startswith("0x") else int(can_id)
            except ValueError:
                self.logger.error(f"Invalid CAN ID format: {can_id}")
                return None
                
        # Convert data to bytes
        if isinstance(data, str):
            # Remove spaces and convert hex string to bytes
            data = bytes.fromhex(data.replace(" ", ""))
        elif isinstance(data, list):
            # Convert list of integers to bytes
            data = bytes(data)
            
        # Select database
        if db_name is not None:
            if db_name not in self.dbc_databases:
                self.logger.error(f"DBC database not found: {db_name}")
                return None
                
            databases = [self.dbc_databases[db_name]]
        else:
            # Try all databases
            databases = list(self.dbc_databases.values())
            
        if not databases:
            self.logger.warning("No DBC databases loaded")
            return None
            
        # Try to decode with each database
        for db in databases:
            try:
                if CANTOOLS_AVAILABLE:
                    # Use cantools for decoding
                    try:
                        message = db.get_message_by_frame_id(can_id)
                        decoded = message.decode(data)
                        
                        # Notify callbacks
                        self._notify_signals(can_id, decoded)
                        
                        return decoded
                    except (KeyError, cantools.database.errors.DecodeError):
                        # Message not found in this database or decode error
                        continue
                else:
                    # Use custom decoding
                    decoded = self._decode_message_custom(db, can_id, data)
                    if decoded:
                        # Notify callbacks
                        self._notify_signals(can_id, decoded)
                        
                        return decoded
            except Exception as e:
                self.logger.error(f"Error decoding message: {e}")
                
        # No successful decoding
        return None
    
    def _decode_message_custom(self, db: Dict, can_id: int, data: bytes) -> Optional[Dict]:
        """Custom implementation for decoding CAN messages
        
        Args:
            db: DBC database dictionary
            can_id: CAN message ID
            data: Message data as bytes
            
        Returns:
            Dict with decoded signals or None if decoding failed
        """
        if can_id not in db.get("messages", {}):
            return None
            
        message = db["messages"][can_id]
        signals = message.get("signals", {})
        result = {}
        
        for signal_name, signal in signals.items():
            try:
                # Extract bits from data
                start_bit = signal["start_bit"]
                length = signal["length"]
                byte_order = signal["byte_order"]
                is_signed = signal["is_signed"]
                factor = signal["factor"]
                offset = signal["offset"]
                
                # Extract raw value
                raw_value = self._extract_bits(data, start_bit, length, byte_order)
                
                # Convert to actual value
                if is_signed:
                    # Handle sign bit
                    sign_bit = 1 << (length - 1)
                    if raw_value & sign_bit:
                        raw_value = raw_value - (1 << length)
                        
                # Apply factor and offset
                value = (raw_value * factor) + offset
                
                # Store in result
                result[signal_name] = value
                
            except Exception as e:
                self.logger.error(f"Error decoding signal {signal_name}: {e}")
                
        return result
    
    def _extract_bits(self, data: bytes, start_bit: int, length: int, 
                     byte_order: str) -> int:
        """Extract bits from byte array
        
        Args:
            data: Bytes to extract from
            start_bit: Starting bit position
            length: Number of bits to extract
            byte_order: Byte order ('little_endian' or 'big_endian')
            
        Returns:
            int: Extracted value
        """
        # Convert bytes to integer
        data_int = int.from_bytes(data, byteorder='little')
        
        if byte_order == "little_endian":
            # Extract bits
            mask = (1 << length) - 1
            return (data_int >> start_bit) & mask
        else:
            # Big endian extraction (Motorola format)
            # This is a simplified implementation and may not work for all DBC files
            byte_index = start_bit // 8
            bit_index = start_bit % 8
            
            # Adjust for big endian
            adjusted_bit = (7 - bit_index) + (byte_index * 8)
            
            # Extract bits
            mask = (1 << length) - 1
            return (data_int >> adjusted_bit) & mask
    
    def encode_message(self, can_id: Union[int, str], signals: Dict, 
                      db_name: Optional[str] = None) -> Optional[bytes]:
        """Encode signals into a CAN message
        
        Args:
            can_id: CAN message ID
            signals: Dictionary of signal name to value
            db_name: Optional database name (uses first available if None)
            
        Returns:
            bytes: Encoded message data or None if encoding failed
        """
        # Ensure can_id is an integer
        if isinstance(can_id, str):
            try:
                can_id = int(can_id, 16) if can_id.startswith("0x") else int(can_id)
            except ValueError:
                self.logger.error(f"Invalid CAN ID format: {can_id}")
                return None
                
        # Select database
        if db_name is not None:
            if db_name not in self.dbc_databases:
                self.logger.error(f"DBC database not found: {db_name}")
                return None
                
            databases = [self.dbc_databases[db_name]]
        else:
            # Try all databases
            databases = list(self.dbc_databases.values())
            
        if not databases:
            self.logger.warning("No DBC databases loaded")
            return None
            
        # Try to encode with each database
        for db in databases:
            try:
                if CANTOOLS_AVAILABLE:
                    # Use cantools for encoding
                    try:
                        message = db.get_message_by_frame_id(can_id)
                        encoded = message.encode(signals)
                        return encoded
                    except (KeyError, cantools.database.errors.EncodeError):
                        # Message not found in this database or encode error
                        continue
                else:
                    # Custom encoding not implemented
                    self.logger.warning("Custom encoding not implemented, install cantools")
                    return None
            except Exception as e:
                self.logger.error(f"Error encoding message: {e}")
                
        # No successful encoding
        return None
    
    def get_message_info(self, can_id: Union[int, str], 
                        db_name: Optional[str] = None) -> Optional[Dict]:
        """Get information about a CAN message
        
        Args:
            can_id: CAN message ID
            db_name: Optional database name (uses first available if None)
            
        Returns:
            Dict with message information or None if not found
        """
        # Ensure can_id is an integer
        if isinstance(can_id, str):
            try:
                can_id = int(can_id, 16) if can_id.startswith("0x") else int(can_id)
            except ValueError:
                self.logger.error(f"Invalid CAN ID format: {can_id}")
                return None
                
        # Select database
        if db_name is not None:
            if db_name not in self.dbc_databases:
                self.logger.error(f"DBC database not found: {db_name}")
                return None
                
            databases = [(db_name, self.dbc_databases[db_name])]
        else:
            # Try all databases
            databases = list(self.dbc_databases.items())
            
        if not databases:
            self.logger.warning("No DBC databases loaded")
            return None
            
        # Try to find message in each database
        for db_name, db in databases:
            try:
                if CANTOOLS_AVAILABLE:
                    # Use cantools
                    try:
                        message = db.get_message_by_frame_id(can_id)
                        
                        # Convert to dictionary
                        info = {
                            "name": message.name,
                            "id": message.frame_id,
                            "dlc": message.length,
                            "comment": message.comment,
                            "signals": [],
                            "database": db_name
                        }
                        
                        # Add signals
                        for signal in message.signals:
                            signal_info = {
                                "name": signal.name,
                                "start_bit": signal.start,
                                "length": signal.length,
                                "byte_order": "little_endian" if signal.byte_order == "little_endian" else "big_endian",
                                "is_signed": signal.is_signed,
                                "factor": signal.scale,
                                "offset": signal.offset,
                                "minimum": signal.minimum,
                                "maximum": signal.maximum,
                                "unit": signal.unit,
                                "comment": signal.comment
                            }
                            
                            # Add value table if available
                            if signal.choices:
                                signal_info["values"] = signal.choices
                                
                            info["signals"].append(signal_info)
                            
                        return info
                    except KeyError:
                        # Message not found in this database
                        continue
                else:
                    # Use custom implementation
                    if can_id in db.get("messages", {}):
                        message = db["messages"][can_id]
                        
                        # Convert to common format
                        info = {
                            "name": message.get("name", f"UNK_{can_id:X}"),
                            "id": can_id,
                            "dlc": message.get("dlc", 8),
                            "comment": "",
                            "signals": [],
                            "database": db_name
                        }
                        
                        # Add signals
                        for signal_name, signal in message.get("signals", {}).items():
                            signal_info = {
                                "name": signal_name,
                                "start_bit": signal.get("start_bit", 0),
                                "length": signal.get("length", 8),
                                "byte_order": signal.get("byte_order", "little_endian"),
                                "is_signed": signal.get("is_signed", False),
                                "factor": signal.get("factor", 1.0),
                                "offset": signal.get("offset", 0.0),
                                "minimum": signal.get("minimum"),
                                "maximum": signal.get("maximum"),
                                "unit": signal.get("unit", ""),
                                "comment": ""
                            }
                            
                            # Add value table if available
                            key = f"{can_id}_{signal_name}"
                            if key in db.get("value_tables", {}):
                                signal_info["values"] = db["value_tables"][key]
                                
                            info["signals"].append(signal_info)
                            
                        return info
            except Exception as e:
                self.logger.error(f"Error getting message info: {e}")
                
        # Message not found in any database
        return None
    
    def get_all_messages(self, db_name: Optional[str] = None) -> List[Dict]:
        """Get information about all messages
        
        Args:
            db_name: Optional database name (uses all if None)
            
        Returns:
            List of message information dictionaries
        """
        result = []
        
        # Select database(s)
        if db_name is not None:
            if db_name not in self.dbc_databases:
                self.logger.error(f"DBC database not found: {db_name}")
                return []
                
            databases = [(db_name, self.dbc_databases[db_name])]
        else:
            # Use all databases
            databases = list(self.dbc_databases.items())
            
        if not databases:
            self.logger.warning("No DBC databases loaded")
            return []
            
        # Get messages from each database
        for db_name, db in databases:
            try:
                if CANTOOLS_AVAILABLE:
                    # Use cantools
                    for message in db.messages:
                        # Basic message info
                        msg_info = {
                            "name": message.name,
                            "id": message.frame_id,
                            "dlc": message.length,
                            "comment": message.comment,
                            "signal_count": len(message.signals),
                            "database": db_name
                        }
                        
                        result.append(msg_info)
                else:
                    # Use custom implementation
                    for can_id, message in db.get("messages", {}).items():
                        # Basic message info
                        msg_info = {
                            "name": message.get("name", f"UNK_{can_id:X}"),
                            "id": can_id,
                            "dlc": message.get("dlc", 8),
                            "comment": "",
                            "signal_count": len(message.get("signals", {})),
                            "database": db_name
                        }
                        
                        result.append(msg_info)
            except Exception as e:
                self.logger.error(f"Error getting messages from {db_name}: {e}")
                
        return result
    
    def register_signal_callback(self, callback: Callable[[int, Dict], None]) -> None:
        """Register a callback for decoded signals
        
        Args:
            callback: Function that takes CAN ID and signals dictionary
        """
        if callback not in self.signal_callbacks:
            self.signal_callbacks.append(callback)
    
    def unregister_signal_callback(self, callback: Callable[[int, Dict], None]) -> None:
        """Unregister a signal callback
        
        Args:
            callback: Previously registered callback function
        """
        if callback in self.signal_callbacks:
            self.signal_callbacks.remove(callback)
    
    def _notify_signals(self, can_id: int, signals: Dict) -> None:
        """Notify callbacks of decoded signals
        
        Args:
            can_id: CAN message ID
            signals: Dictionary of decoded signals
        """
        for callback in self.signal_callbacks:
            try:
                callback(can_id, signals)
            except Exception as e:
                self.logger.error(f"Error in signal callback: {e}")
                
    def get_loaded_databases(self) -> List[str]:
        """Get names of loaded DBC databases
        
        Returns:
            List of database names
        """
        return list(self.dbc_databases.keys())
    
    def create_simple_dbc(self, messages: List[Dict], output_path: str) -> bool:
        """Create a simple DBC file from message definitions
        
        Args:
            messages: List of message dictionaries
            output_path: Path to save the DBC file
            
        Returns:
            bool: True if file was created successfully
        """
        if not CANTOOLS_AVAILABLE:
            self.logger.error("cantools required for DBC file creation")
            return False
            
        try:
            # Create a new database
            db = cantools.database.Database()
            
            # Add each message
            for msg_def in messages:
                msg_id = msg_def.get("id")
                msg_name = msg_def.get("name", f"MSG_{msg_id:X}")
                msg_length = msg_def.get("dlc", 8)
                msg_comment = msg_def.get("comment", "")
                
                # Create message
                message = cantools.database.can.Message(
                    frame_id=msg_id,
                    name=msg_name,
                    length=msg_length,
                    comment=msg_comment
                )
                
                # Add signals
                for sig_def in msg_def.get("signals", []):
                    sig_name = sig_def.get("name")
                    start_bit = sig_def.get("start_bit", 0)
                    sig_length = sig_def.get("length", 8)
                    byte_order = sig_def.get("byte_order", "little_endian")
                    is_signed = sig_def.get("is_signed", False)
                    factor = sig_def.get("factor", 1.0)
                    offset = sig_def.get("offset", 0.0)
                    minimum = sig_def.get("minimum")
                    maximum = sig_def.get("maximum")
                    unit = sig_def.get("unit", "")
                    comment = sig_def.get("comment", "")
                    
                    # Create signal
                    signal = cantools.database.can.Signal(
                        name=sig_name,
                        start=start_bit,
                        length=sig_length,
                        byte_order=byte_order,
                        is_signed=is_signed,
                        scale=factor,
                        offset=offset,
                        minimum=minimum,
                        maximum=maximum,
                        unit=unit,
                        comment=comment
                    )
                    
                    # Add value definitions if available
                    if "values" in sig_def:
                        signal.choices = sig_def["values"]
                        
                    # Add signal to message
                    message.signals.append(signal)
                    
                # Add message to database
                db.messages.append(message)
                
            # Save database to file
            with open(output_path, 'w') as f:
                f.write(db.as_dbc_string())
                
            self.logger.info(f"Created DBC file with {len(messages)} messages: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating DBC file: {e}")
            
            if self.error_manager:
                self.error_manager.report_error(
                    "DBCParser", 
                    "dbc_creation_error", 
                    f"Error creating DBC file: {e}",
                    severity="error"
                )
                
            return False