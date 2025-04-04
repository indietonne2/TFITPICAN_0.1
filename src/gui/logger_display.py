#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.1
# License: MIT
# Filename: logger_display.py
# Pathname: src/gui/
# Description: Log display widget for the TFITPICAN application
# -----------------------------------------------------------------------------

import os
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable, Set

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                                QTableWidgetItem, QComboBox, QPushButton, QLabel, 
                                QHeaderView, QAbstractItemView, QCheckBox, QSpinBox,
                                QMenu, QAction, QToolBar, QSplitter, QTextEdit,
                                QFileDialog, QInputDialog)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize
    from PyQt5.QtGui import QIcon, QFont, QColor, QBrush, QTextCursor
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# Custom logging handler to capture log messages
class LogHandler(logging.Handler):
    """Logging handler that sends messages to a callback function"""
    
    def __init__(self, callback: Callable[[Dict], None]):
        """Initialize the log handler
        
        Args:
            callback: Function to call with log records
        """
        super().__init__()
        self.callback = callback
        
    def emit(self, record):
        """Emit a log record
        
        Args:
            record: Log record
        """
        # Format the record
        try:
            msg = self.format(record)
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created),
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
                "raw": record
            }
            self.callback(log_entry)
        except Exception:
            self.handleError(record)

class LoggerDisplay(QWidget):
    """Log display widget for TFITPICAN"""
    
    # Signal for when a log is selected
    log_selected = pyqtSignal(dict)
    
    def __init__(self, sqlite_logger=None, translation_manager=None):
        """Initialize the logger display widget
        
        Args:
            sqlite_logger: SQLite logger instance
            translation_manager: Translation manager instance
        """
        if not GUI_AVAILABLE:
            raise ImportError("PyQt5 is required for the GUI")
            
        super().__init__()
        
        self.logger = logging.getLogger("LoggerDisplay")
        self.sqlite_logger = sqlite_logger
        self.translation_manager = translation_manager
        
        # In-memory log buffer
        self.log_buffer = []
        self.max_buffer_size = 1000
        
        # Log filters
        self.level_filter = "INFO"
        self.logger_filter = ""
        self.search_filter = ""
        self.auto_scroll = True
        self.show_timestamps = True
        
        # Register log handler
        self.log_handler = LogHandler(self._handle_log)
        self.log_handler.setLevel(logging.DEBUG)
        self.log_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(self.log_handler)
        
        # Setup UI
        self._setup_ui()
        
        # Set up update timer
        self._setup_timer()
        
        # Initial load of database logs
        self._load_database_logs()
        
        self.logger.info("Logger display initialized")
    
    def _setup_ui(self):
        """Set up the user interface"""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(16, 16))
        
        # Level filter
        level_label = QLabel("Level:")
        self.toolbar.addWidget(level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.setCurrentText(self.level_filter)
        self.level_combo.currentTextChanged.connect(self._on_filter_changed)
        self.toolbar.addWidget(self.level_combo)
        
        self.toolbar.addSeparator()
        
        # Logger filter
        logger_label = QLabel("Logger:")
        self.toolbar.addWidget(logger_label)
        
        self.logger_combo = QComboBox()
        self.logger_combo.setEditable(True)
        self.logger_combo.setMinimumWidth(150)
        self.logger_combo.currentTextChanged.connect(self._on_filter_changed)
        self.toolbar.addWidget(self.logger_combo)
        
        self.toolbar.addSeparator()
        
        # Search
        search_label = QLabel("Search:")
        self.toolbar.addWidget(search_label)
        
        self.search_combo = QComboBox()
        self.search_combo.setEditable(True)
        self.search_combo.setMinimumWidth(150)
        self.search_combo.currentTextChanged.connect(self._on_filter_changed)
        self.toolbar.addWidget(self.search_combo)
        
        self.toolbar.addSeparator()
        
        # Auto scroll checkbox
        self.auto_scroll_checkbox = QCheckBox("Auto Scroll")
        self.auto_scroll_checkbox.setChecked(self.auto_scroll)
        self.auto_scroll_checkbox.stateChanged.connect(self._on_auto_scroll_changed)
        self.toolbar.addWidget(self.auto_scroll_checkbox)
        
        # Show timestamps checkbox
        self.timestamps_checkbox = QCheckBox("Show Timestamps")
        self.timestamps_checkbox.setChecked(self.show_timestamps)
        self.timestamps_checkbox.stateChanged.connect(self._on_timestamps_changed)
        self.toolbar.addWidget(self.timestamps_checkbox)
        
        self.toolbar.addSeparator()
        
        # Clear button
        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self._on_clear)
        if os.path.exists("assets/clear.png"):
            clear_action.setIcon(QIcon("assets/clear.png"))
        self.toolbar.addAction(clear_action)
        
        # Save button
        save_action = QAction("Save", self)
        save_action.triggered.connect(self._on_save)
        if os.path.exists("assets/save.png"):
            save_action.setIcon(QIcon("assets/save.png"))
        self.toolbar.addAction(save_action)
        
        # Add toolbar to layout
        self.layout.addWidget(self.toolbar)
        
        # Create splitter for log table and details
        self.splitter = QSplitter(Qt.Vertical)
        
        # Log text view
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setFont(QFont("Monospace", 9))
        
        # Set text colors for different log levels
        self.level_colors = {
            "DEBUG": QColor(100, 100, 100),  # Gray
            "INFO": QColor(0, 0, 0),         # Black
            "WARNING": QColor(200, 150, 0),  # Orange
            "ERROR": QColor(255, 0, 0),      # Red
            "CRITICAL": QColor(150, 0, 150)  # Purple
        }
        
        self.splitter.addWidget(self.log_text)
        
        # Log details text view
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setFont(QFont("Monospace", 9))
        
        self.splitter.addWidget(self.details_text)
        
        # Set splitter proportions
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        
        # Add splitter to layout
        self.layout.addWidget(self.splitter)
        
        # Status bar
        self.status_bar = QWidget()
        self.status_layout = QHBoxLayout(self.status_bar)
        self.status_layout.setContentsMargins(5, 5, 5, 5)
        
        # Log count
        self.log_count = QLabel("0 logs")
        self.status_layout.addWidget(self.log_count)
        
        # Filtered count
        self.filtered_count = QLabel("")
        self.status_layout.addWidget(self.filtered_count, 1)
        
        # Add status bar to layout
        self.layout.addWidget(self.status_bar)
    
    def _setup_timer(self):
        """Set up timer for periodic updates"""
        from PyQt5.QtCore import QTimer
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_loggers_list)
        self.update_timer.start(5000)  # Update every 5 seconds
    
    def _handle_log(self, log_entry: Dict):
        """Handle a new log entry
        
        Args:
            log_entry: Log entry dictionary
        """
        # Add to buffer
        self.log_buffer.append(log_entry)
        
        # Trim buffer if needed
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size:]
            
        # Apply filters and update display
        if self._apply_filters(log_entry):
            self._add_log_to_display(log_entry)
            
            # Auto scroll
            if self.auto_scroll:
                scrollbar = self.log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                
        # Update status
        self._update_status()
    
    def _apply_filters(self, log_entry: Dict) -> bool:
        """Apply filters to a log entry
        
        Args:
            log_entry: Log entry dictionary
            
        Returns:
            bool: True if log entry passes filters
        """
        # Level filter
        level = log_entry["level"]
        level_idx = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].index(level)
        filter_idx = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].index(self.level_filter)
        
        if level_idx < filter_idx:
            return False
            
        # Logger filter
        if self.logger_filter and log_entry["logger"] != self.logger_filter:
            return False
            
        # Search filter
        if self.search_filter and self.search_filter.lower() not in log_entry["message"].lower():
            return False
            
        return True
    
    def _add_log_to_display(self, log_entry: Dict):
        """Add a log entry to the display
        
        Args:
            log_entry: Log entry dictionary
        """
        # Format log text
        text = ""
        
        if self.show_timestamps:
            timestamp = log_entry["timestamp"].strftime("%H:%M:%S.%f")[:-3]
            text += f"{timestamp} "
            
        level = log_entry["level"]
        logger = log_entry["logger"]
        message = log_entry["message"]
        
        text += f"[{level}] {logger}: {message}"
        
        # Set text color based on level
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        self.log_text.setTextCursor(cursor)
        
        # Set color
        color = self.level_colors.get(level, QColor(0, 0, 0))
        self.log_text.setTextColor(color)
        
        # Add text
        self.log_text.insertPlainText(text + "\n")
    
    def _update_status(self):
        """Update status information"""
        # Count logs
        total_logs = len(self.log_buffer)
        
        # Count filtered logs
        filtered_logs = sum(1 for log in self.log_buffer if self._apply_filters(log))
        
        # Update labels
        self.log_count.setText(f"{total_logs} logs")
        
        if filtered_logs < total_logs:
            self.filtered_count.setText(f"Showing {filtered_logs} logs")
        else:
            self.filtered_count.setText("")
    
    def _update_loggers_list(self):
        """Update the list of available loggers"""
        # Get unique logger names
        loggers = {log["logger"] for log in self.log_buffer}
        
        # Current text
        current_text = self.logger_combo.currentText()
        
        # Update combo box items
        self.logger_combo.clear()
        self.logger_combo.addItem("")  # Empty item for "all"
        self.logger_combo.addItems(sorted(loggers))
        
        # Restore selection
        index = self.logger_combo.findText(current_text)
        if index >= 0:
            self.logger_combo.setCurrentIndex(index)
    
    def _on_filter_changed(self):
        """Handle filter changes"""
        # Update filters
        self.level_filter = self.level_combo.currentText()
        self.logger_filter = self.logger_combo.currentText()
        self.search_filter = self.search_combo.currentText()
        
        # Reapply filters
        self._refresh_display()
    
    def _on_auto_scroll_changed(self, state):
        """Handle auto scroll setting change
        
        Args:
            state: Checkbox state
        """
        self.auto_scroll = state == Qt.Checked
    
    def _on_timestamps_changed(self, state):
        """Handle show timestamps setting change
        
        Args:
            state: Checkbox state
        """
        self.show_timestamps = state == Qt.Checked
        
        # Refresh display
        self._refresh_display()
    
    def _on_clear(self):
        """Handle clear button"""
        # Clear buffer
        self.log_buffer.clear()
        
        # Clear display
        self.log_text.clear()
        self.details_text.clear()
        
        # Update status
        self._update_status()
    
    def _on_save(self):
        """Handle save button"""
        # Show file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log",
            f"logs/tfitpican_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write logs to file
            with open(file_path, 'w') as f:
                for log in self.log_buffer:
                    timestamp = log["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    level = log["level"]
                    logger = log["logger"]
                    message = log["message"]
                    
                    f.write(f"{timestamp} [{level}] {logger}: {message}\n")
                    
            # Show confirmation in details
            self.details_text.setText(f"Log saved to {file_path}")
            
        except Exception as e:
            # Show error in details
            self.details_text.setText(f"Error saving log: {str(e)}")
    
    def _refresh_display(self):
        """Refresh the log display with current filters"""
        # Clear display
        self.log_text.clear()
        
        # Re-add filtered logs
        for log in self.log_buffer:
            if self._apply_filters(log):
                self._add_log_to_display(log)
                
        # Update status
        self._update_status()
        
        # Auto scroll
        if self.auto_scroll:
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _load_database_logs(self):
        """Load logs from database"""
        if not self.sqlite_logger:
            return
            
        try:
            # Get recent events
            events = self.sqlite_logger.get_recent_events(100)
            
            # Get recent errors
            errors = self.sqlite_logger.get_recent_errors(100)
            
            # Convert to log entries
            for event in events:
                timestamp = datetime.fromisoformat(event.get("timestamp", ""))
                event_type = event.get("event_type", "unknown")
                event_id = event.get("event_id", "")
                description = event.get("description", "")
                
                log_entry = {
                    "timestamp": timestamp,
                    "level": "INFO",
                    "logger": "SQLiteLogger",
                    "message": f"Event: {event_type} - {event_id} - {description}",
                    "raw": event
                }
                
                self.log_buffer.append(log_entry)
                
            for error in errors:
                timestamp = datetime.fromisoformat(error.get("timestamp", ""))
                source = error.get("source", "unknown")
                error_code = error.get("error_code", "")
                message = error.get("message", "")
                severity = error.get("severity", "error").upper()
                
                # Map severity to log level
                level = {
                    "INFO": "INFO",
                    "WARNING": "WARNING",
                    "ERROR": "ERROR",
                    "CRITICAL": "ERROR",
                    "EMERGENCY": "CRITICAL"
                }.get(severity, "ERROR")
                
                log_entry = {
                    "timestamp": timestamp,
                    "level": level,
                    "logger": source,
                    "message": f"{error_code}: {message}",
                    "raw": error
                }
                
                self.log_buffer.append(log_entry)
                
            # Sort by timestamp
            self.log_buffer.sort(key=lambda x: x["timestamp"])
            
            # Refresh display
            self._refresh_display()
            
        except Exception as e:
            # Log the error
            self.logger.error(f"Error loading logs from database: {e}")
    
    def add_log(self, message: str, level: str = "INFO", logger: str = "External") -> None:
        """Add a log entry programmatically
        
        Args:
            message: Log message
            level: Log level
            logger: Logger name
        """
        # Create log entry
        log_entry = {
            "timestamp": datetime.now(),
            "level": level,
            "logger": logger,
            "message": message,
            "raw": None
        }
        
        # Process the log entry
        self._handle_log(log_entry)
    
    def set_max_buffer_size(self, size: int) -> None:
        """Set the maximum buffer size
        
        Args:
            size: Maximum number of log entries to store
        """
        if size < 100:
            size = 100
            
        self.max_buffer_size = size
        
        # Trim buffer if needed
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size:]
            self._refresh_display()
    
    def get_log_count(self) -> int:
        """Get the number of logs in the buffer
        
        Returns:
            int: Number of logs
        """
        return len(self.log_buffer)
    
    def clear_logs(self) -> None:
        """Clear all logs"""
        self._on_clear()
    
    def closeEvent(self, event):
        """Handle widget close event
        
        Args:
            event: Close event
        """
        # Remove log handler
        logging.getLogger().removeHandler(self.log_handler)
        
        # Stop timer
        self.update_timer.stop()
        
        # Call parent method
        super().closeEvent(event)