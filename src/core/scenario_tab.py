        self.remove_step_button = QPushButton("Remove Step")
        self.remove_step_button.clicked.connect(self._on_remove_step)
        steps_buttons_layout.addWidget(self.remove_step_button)
        
        self.steps_layout.addLayout(steps_buttons_layout)
        
        # Add panels to splitter
        self.splitter.addWidget(self.info_panel)
        self.splitter.addWidget(self.steps_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4)
        
        # Add splitter to layout
        self.layout.addWidget(self.splitter)
        
        # Status panel
        self.status_panel = QWidget()
        self.status_layout = QHBoxLayout(self.status_panel)
        self.status_layout.setContentsMargins(5, 5, 5, 5)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_layout.addWidget(self.status_label)
        
        # Progress label
        self.progress_label = QLabel("")
        self.status_layout.addWidget(self.progress_label, 1)
        
        # Add status panel to layout
        self.layout.addWidget(self.status_panel)
        
        # Update button states
        self._update_button_states()
    
    def _setup_timer(self):
        """Set up timer for periodic updates"""
        from PyQt5.QtCore import QTimer
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(500)  # Update every 500ms
    
    def _load_scenarios(self):
        """Load available scenarios into selector"""
        if not self.scenario_loader:
            return
            
        # Clear selector
        self.scenario_selector.clear()
        
        # Add placeholder
        self.scenario_selector.addItem("Select Scenario", None)
        
        # Get available scenarios
        scenarios = self.scenario_loader.get_available_scenarios()
        
        # Add to selector
        for scenario in scenarios:
            self.scenario_selector.addItem(
                scenario.get("name", scenario.get("id", "Unknown")),
                scenario.get("id")
            )
    
    def _on_scenario_selected(self, index):
        """Handle scenario selection
        
        Args:
            index: Selected index
        """
        if index <= 0:
            # No scenario selected
            self.current_scenario = None
            self.current_scenario_path = None
            self._update_scenario_display()
            return
            
        # Get scenario ID
        scenario_id = self.scenario_selector.itemData(index)
        
        # Check for unsaved changes
        if self.scenario_modified and self.current_scenario:
            # Ask to save changes
            reply = QMessageBox.question(
                self,
                "Save Changes",
                "Save changes to the current scenario?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self._on_save()
            elif reply == QMessageBox.Cancel:
                # Revert selection
                for i in range(self.scenario_selector.count()):
                    if self.scenario_selector.itemData(i) == self.current_scenario.get("id"):
                        self.scenario_selector.setCurrentIndex(i)
                        return
                        
                # If not found, set to index 0
                self.scenario_selector.setCurrentIndex(0)
                return
        
        # Load selected scenario
        if scenario_id and self.scenario_loader:
            self.current_scenario = self.scenario_loader.load_scenario(scenario_id)
            self.scenario_modified = False
            
            # Store path if available
            if self.current_scenario:
                self.current_scenario_path = f"config/scenarios/{scenario_id}.json"
                
            self._update_scenario_display()
    
    def _update_scenario_display(self):
        """Update UI with current scenario data"""
        # Clear fields
        self.scenario_name.clear()
        self.scenario_description.clear()
        self.steps_table.setRowCount(0)
        
        if not self.current_scenario:
            return
            
        # Update fields
        self.scenario_name.setText(self.current_scenario.get("name", ""))
        self.scenario_description.setText(self.current_scenario.get("description", ""))
        
        # Load steps
        steps = self.current_scenario.get("steps", [])
        self.steps_table.setRowCount(len(steps))
        
        for i, step in enumerate(steps):
            # Step type
            step_type = step.get("type", "unknown")
            self.steps_table.setItem(i, 0, QTableWidgetItem(step_type))
            
            # Details depends on step type
            if step_type == "can_message":
                can_id = step.get("id", "")
                data = step.get("data", [])
                data_str = " ".join(f"{b:02X}" for b in data)
                details = f"ID: {can_id}, Data: {data_str}"
                self.steps_table.setItem(i, 1, QTableWidgetItem(details))
                
                # Parameters
                params = []
                if "extended" in step and step["extended"]:
                    params.append("Extended")
                params_str = ", ".join(params) if params else "Standard"
                self.steps_table.setItem(i, 2, QTableWidgetItem(params_str))
                
            elif step_type == "pause":
                duration = step.get("duration_sec", 0)
                details = f"Duration: {duration} seconds"
                self.steps_table.setItem(i, 1, QTableWidgetItem(details))
                self.steps_table.setItem(i, 2, QTableWidgetItem(""))
                
            elif step_type == "plugin_action":
                plugin = step.get("plugin", "")
                action = step.get("action", "")
                details = f"Plugin: {plugin}, Action: {action}"
                self.steps_table.setItem(i, 1, QTableWidgetItem(details))
                
                # Parameters
                params = step.get("params", {})
                params_str = ", ".join(f"{k}={v}" for k, v in params.items())
                self.steps_table.setItem(i, 2, QTableWidgetItem(params_str))
                
            elif step_type == "vehicle_control":
                control = step.get("control", "")
                value = step.get("value", "")
                details = f"Control: {control}, Value: {value}"
                self.steps_table.setItem(i, 1, QTableWidgetItem(details))
                self.steps_table.setItem(i, 2, QTableWidgetItem(""))
                
            else:
                # Unknown step type
                details = json.dumps(step)
                self.steps_table.setItem(i, 1, QTableWidgetItem(details))
                self.steps_table.setItem(i, 2, QTableWidgetItem(""))
            
            # Delay
            delay_ms = step.get("delay_ms", 0)
            delay_str = f"{delay_ms} ms" if delay_ms else ""
            self.steps_table.setItem(i, 3, QTableWidgetItem(delay_str))
            
            # Notes
            notes = step.get("notes", "")
            self.steps_table.setItem(i, 4, QTableWidgetItem(notes))
        
        # Update button states
        self._update_button_states()
    
    def _update_button_states(self):
        """Update button enabled states based on current context"""
        has_scenario = self.current_scenario is not None
        has_steps = has_scenario and len(self.current_scenario.get("steps", [])) > 0
        has_selection = self.steps_table.currentRow() >= 0
        is_running = self.scenario_manager and self.scenario_manager.get_scenario_status(self.current_scenario.get("id")) is not None
        
        # Toolbar actions
        self.save_action.setEnabled(has_scenario and self.scenario_modified)
        self.run_action.setEnabled(has_scenario and has_steps and not is_running)
        self.stop_action.setEnabled(is_running)
        
        # Step buttons
        self.add_step_button.setEnabled(has_scenario)
        self.edit_step_button.setEnabled(has_scenario and has_selection)
        self.remove_step_button.setEnabled(has_scenario and has_selection)
    
    def _update_status(self):
        """Update status information (called periodically)"""
        if not self.current_scenario or not self.scenario_manager:
            return
            
        # Get running status
        scenario_id = self.current_scenario.get("id")
        status = self.scenario_manager.get_scenario_status(scenario_id)
        
        if status:
            # Update status label
            current_state = status.get("status", "unknown")
            self.status_label.setText(f"Status: {current_state.capitalize()}")
            
            # Update progress
            current_step = status.get("current_step", 0)
            total_steps = status.get("total_steps", 0)
            
            if total_steps > 0:
                self.progress_label.setText(f"Step {current_step + 1} of {total_steps}")
            else:
                self.progress_label.setText("")
                
            # Update button states
            self._update_button_states()
        else:
            # Not running
            self.status_label.setText("Ready")
            self.progress_label.setText("")
    
    def _on_scenario_modified(self):
        """Handle scenario modification"""
        if not self.current_scenario:
            return
            
        # Update scenario data
        self.current_scenario["name"] = self.scenario_name.text()
        self.current_scenario["description"] = self.scenario_description.toPlainText()
        
        # Set modified flag
        self.scenario_modified = True
        
        # Update button states
        self._update_button_states()
    
    def _on_new(self):
        """Handle new scenario action"""
        # Check for unsaved changes
        if self.scenario_modified and self.current_scenario:
            # Ask to save changes
            reply = QMessageBox.question(
                self,
                "Save Changes",
                "Save changes to the current scenario?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self._on_save()
            elif reply == QMessageBox.Cancel:
                return
        
        # Get scenario name
        name, ok = QInputDialog.getText(
            self,
            "New Scenario",
            "Enter scenario name:"
        )
        
        if not ok or not name:
            return
            
        # Create new scenario
        if self.scenario_loader:
            scenario_id = self.scenario_loader.create_scenario(name)
            
            if scenario_id:
                # Reload scenarios
                self._load_scenarios()
                
                # Select new scenario
                for i in range(self.scenario_selector.count()):
                    if self.scenario_selector.itemData(i) == scenario_id:
                        self.scenario_selector.setCurrentIndex(i)
                        break
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to create new scenario"
                )
        else:
            # Create new scenario manually
            scenario_id = name.lower().replace(" ", "_")
            self.current_scenario = {
                "id": scenario_id,
                "name": name,
                "description": "",
                "steps": []
            }
            self.current_scenario_path = None
            self.scenario_modified = True
            
            # Update display
            self._update_scenario_display()
    
    def _on_load(self):
        """Handle load scenario action"""
        # Show file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Scenario",
            "config/scenarios",
            "Scenario Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
            
        # Check for unsaved changes
        if self.scenario_modified and self.current_scenario:
            # Ask to save changes
            reply = QMessageBox.question(
                self,
                "Save Changes",
                "Save changes to the current scenario?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self._on_save()
            elif reply == QMessageBox.Cancel:
                return
        
        try:
            # Load scenario from file
            with open(file_path, 'r') as f:
                scenario = json.load(f)
                
            # Validate basic structure
            if not isinstance(scenario, dict) or "id" not in scenario or "name" not in scenario:
                raise ValueError("Invalid scenario format")
                
            # Set as current scenario
            self.current_scenario = scenario
            self.current_scenario_path = file_path
            self.scenario_modified = False
            
            # Update display
            self._update_scenario_display()
            
            # Update selector
            for i in range(self.scenario_selector.count()):
                if self.scenario_selector.itemData(i) == scenario.get("id"):
                    self.scenario_selector.setCurrentIndex(i)
                    return
                    
            # If not found in selector, add it
            self.scenario_selector.addItem(
                scenario.get("name", scenario.get("id", "Unknown")),
                scenario.get("id")
            )
            self.scenario_selector.setCurrentIndex(self.scenario_selector.count() - 1)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load scenario: {str(e)}"
            )
    
    def _on_save(self):
        """Handle save scenario action"""
        if not self.current_scenario:
            return
            
        if self.scenario_loader:
            # Use scenario loader to save
            success = self.scenario_loader.save_scenario(self.current_scenario)
            
            if success:
                self.scenario_modified = False
                self._update_button_states()
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to save scenario"
                )
        else:
            # Save manually
            if not self.current_scenario_path:
                # Ask for file path
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save Scenario",
                    f"config/scenarios/{self.current_scenario.get('id', 'scenario')}.json",
                    "Scenario Files (*.json);;All Files (*)"
                )
                
                if not file_path:
                    return
                    
                self.current_scenario_path = file_path
            
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.current_scenario_path), exist_ok=True)
                
                # Save to file
                with open(self.current_scenario_path, 'w') as f:
                    json.dump(self.current_scenario, f, indent=2)
                    
                self.scenario_modified = False
                self._update_button_states()
                
                # Reload scenarios if saved to default location
                if self.current_scenario_path.startswith("config/scenarios/"):
                    self._load_scenarios()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to save scenario: {str(e)}"
                )
    
    def _on_run(self):
        """Handle run scenario action"""
        if not self.current_scenario or not self.scenario_manager:
            return
            
        # Save changes if modified
        if self.scenario_modified:
            if not self._on_save():
                # Failed to save
                return
                
        # Run scenario
        scenario_id = self.current_scenario.get("id")
        success = self.scenario_manager.run_scenario(scenario_id)
        
        if success:
            self.status_label.setText("Status: Running")
            self._update_button_states()
        else:
            QMessageBox.warning(
                self,
                "Error",
                "Failed to run scenario"
            )
    
    def _on_stop(self):
        """Handle stop scenario action"""
        if not self.current_scenario or not self.scenario_manager:
            return
            
        # Stop scenario
        scenario_id = self.current_scenario.get("id")
        success = self.scenario_manager.stop_scenario(scenario_id)
        
        if success:
            self.status_label.setText("Status: Stopped")
            self._update_button_states()
    
    def _on_add_step(self):
        """Handle add step action"""
        if not self.current_scenario:
            return
            
        # Show step type dialog
        step_types = ["can_message", "pause", "plugin_action", "vehicle_control"]
        step_type, ok = QInputDialog.getItem(
            self,
            "Add Step",
            "Select step type:",
            step_types,
            0,
            False
        )
        
        if not ok or not step_type:
            return
            
        # Create step based on type
        if step_type == "can_message":
            step = self._create_can_message_step()
        elif step_type == "pause":
            step = self._create_pause_step()
        elif step_type == "plugin_action":
            step = self._create_plugin_action_step()
        elif step_type == "vehicle_control":
            step = self._create_vehicle_control_step()
        else:
            step = None
            
        if step:
            # Add step to scenario
            if "steps" not in self.current_scenario:
                self.current_scenario["steps"] = []
                
            self.current_scenario["steps"].append(step)
            self.scenario_modified = True
            
            # Update display
            self._update_scenario_display()
            
            # Select the new step
            self.steps_table.selectRow(len(self.current_scenario["steps"]) - 1)
    
    def _on_edit_step(self):
        """Handle edit step action"""
        if not self.current_scenario:
            return
            
        # Get selected step
        row = self.steps_table.currentRow()
        if row < 0 or row >= len(self.current_scenario.get("steps", [])):
            return
            
        step = self.current_scenario["steps"][row]
        step_type = step.get("type", "unknown")
        
        # Edit step based on type
        if step_type == "can_message":
            new_step = self._edit_can_message_step(step)
        elif step_type == "pause":
            new_step = self._edit_pause_step(step)
        elif step_type == "plugin_action":
            new_step = self._edit_plugin_action_step(step)
        elif step_type == "vehicle_control":
            new_step = self._edit_vehicle_control_step(step)
        else:
            new_step = None
            
        if new_step:
            # Update step in scenario
            self.current_scenario["steps"][row] = new_step
            self.scenario_modified = True
            
            # Update display
            self._update_scenario_display()
            
            # Reselect the row
            self.steps_table.selectRow(row)
    
    def _on_remove_step(self):
        """Handle remove step action"""
        if not self.current_scenario:
            return
            
        # Get selected step
        row = self.steps_table.currentRow()
        if row < 0 or row >= len(self.current_scenario.get("steps", [])):
            return
            
        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Remove Step",
            "Are you sure you want to remove this step?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Remove step
        del self.current_scenario["steps"][row]
        self.scenario_modified = True
        
        # Update display
        self._update_scenario_display()
        
        # Select the next row if available
        if row < self.steps_table.rowCount():
            self.steps_table.selectRow(row)
        elif self.steps_table.rowCount() > 0:
            self.steps_table.selectRow(self.steps_table.rowCount() - 1)
    
    def _on_steps_context_menu(self, position):
        """Handle context menu on steps table
        
        Args:
            position: Menu position
        """
        if not self.current_scenario:
            return
            
        # Get selected row
        row = self.steps_table.currentRow()
        if row < 0 or row >= len(self.current_scenario.get("steps", [])):
            return
            
        # Create context menu
        context_menu = QMenu()
        
        # Add actions
        edit_action = context_menu.addAction("Edit Step")
        remove_action = context_menu.addAction("Remove Step")
        context_menu.addSeparator()
        move_up_action = context_menu.addAction("Move Up")
        move_down_action = context_menu.addAction("Move Down")
        
        # Disable move actions if at boundaries
        move_up_action.setEnabled(row > 0)
        move_down_action.setEnabled(row < len(self.current_scenario["steps"]) - 1)
        
        # Show menu and get selected action
        action = context_menu.exec_(self.steps_table.mapToGlobal(position))
        
        # Handle action
        if action == edit_action:
            self._on_edit_step()
        elif action == remove_action:
            self._on_remove_step()
        elif action == move_up_action and row > 0:
            # Swap with previous step
            self.current_scenario["steps"][row], self.current_scenario["steps"][row - 1] = \
                self.current_scenario["steps"][row - 1], self.current_scenario["steps"][row]
            self.scenario_modified = True
            self._update_scenario_display()
            self.steps_table.selectRow(row - 1)
        elif action == move_down_action and row < len(self.current_scenario["steps"]) - 1:
            # Swap with next step
            self.current_scenario["steps"][row], self.current_scenario["steps"][row + 1] = \
                self.current_scenario["steps"][row + 1], self.current_scenario["steps"][row]
            self.scenario_modified = True
            self._update_scenario_display()
            self.steps_table.selectRow(row + 1)
            
    # Step creation methods
            
    def _create_can_message_step(self):
        """Create a CAN message step
        
        Returns:
            Dict with step data or None if cancelled
        """
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("CAN Message Step")
        layout = QFormLayout(dialog)
        
        # CAN ID field
        can_id = QLineEdit()
        can_id.setPlaceholderText("e.g., 0x123 or 291")
        layout.addRow("CAN ID:", can_id)
        
        # Data field
        data = QLineEdit()
        data.setPlaceholderText("e.g., 01 02 03 FF")
        layout.addRow("Data (hex):", data)
        
        # Extended frame checkbox
        extended = QCheckBox("Extended Frame Format")
        layout.addRow("", extended)
        
        # Delay field
        delay = QSpinBox()
        delay.setRange(0, 10000)
        delay.setValue(0)
        delay.setSuffix(" ms")
        layout.addRow("Delay after sending:", delay)
        
        # Notes field
        notes = QLineEdit()
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return None
            
        # Create step
        return {
            "type": "pause",
            "duration_sec": duration.value(),
            "notes": notes.text()
        }
    
    def _edit_pause_step(self, step):
        """Edit a pause step
        
        Args:
            step: Existing step data
            
        Returns:
            Dict with updated step data or None if cancelled
        """
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Pause Step")
        layout = QFormLayout(dialog)
        
        # Duration field
        duration = QDoubleSpinBox()
        duration.setRange(0.1, 60.0)
        duration.setValue(step.get("duration_sec", 1.0))
        duration.setSuffix(" seconds")
        layout.addRow("Duration:", duration)
        
        # Notes field
        notes = QLineEdit()
        notes.setText(step.get("notes", ""))
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return None
            
        # Create updated step
        return {
            "type": "pause",
            "duration_sec": duration.value(),
            "notes": notes.text()
        }
    
    def _create_plugin_action_step(self):
        """Create a plugin action step
        
        Returns:
            Dict with step data or None if cancelled
        """
        # Get available plugins
        available_plugins = []
        if self.plugin_manager:
            available_plugins = self.plugin_manager.get_loaded_plugins()
            
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Plugin Action Step")
        layout = QFormLayout(dialog)
        
        # Plugin selector
        plugin = QComboBox()
        for plugin_name in available_plugins:
            plugin.addItem(plugin_name)
        layout.addRow("Plugin:", plugin)
        
        # Action field
        action = QLineEdit()
        layout.addRow("Action:", action)
        
        # Parameters field
        params = QTextEdit()
        params.setPlaceholderText("key1: value1\nkey2: value2")
        params.setMaximumHeight(100)
        layout.addRow("Parameters:", params)
        
        # Delay field
        delay = QSpinBox()
        delay.setRange(0, 10000)
        delay.setValue(0)
        delay.setSuffix(" ms")
        layout.addRow("Delay after action:", delay)
        
        # Notes field
        notes = QLineEdit()
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return None
            
        # Parse parameters
        try:
            params_text = params.toPlainText().strip()
            params_dict = {}
            
            if params_text:
                for line in params_text.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        params_dict[key.strip()] = value.strip()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Invalid parameter format: {str(e)}"
            )
            return None
            
        # Create step
        return {
            "type": "plugin_action",
            "plugin": plugin.currentText(),
            "action": action.text(),
            "params": params_dict,
            "delay_ms": delay.value(),
            "notes": notes.text()
        }
    
    def _edit_plugin_action_step(self, step):
        """Edit a plugin action step
        
        Args:
            step: Existing step data
            
        Returns:
            Dict with updated step data or None if cancelled
        """
        # Get available plugins
        available_plugins = []
        if self.plugin_manager:
            available_plugins = self.plugin_manager.get_loaded_plugins()
            
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Plugin Action Step")
        layout = QFormLayout(dialog)
        
        # Plugin selector
        plugin = QComboBox()
        current_plugin = step.get("plugin", "")
        
        for plugin_name in available_plugins:
            plugin.addItem(plugin_name)
            
        # Set current plugin
        index = plugin.findText(current_plugin)
        if index >= 0:
            plugin.setCurrentIndex(index)
            
        layout.addRow("Plugin:", plugin)
        
        # Action field
        action = QLineEdit()
        action.setText(step.get("action", ""))
        layout.addRow("Action:", action)
        
        # Parameters field
        params = QTextEdit()
        params_text = ""
        for key, value in step.get("params", {}).items():
            params_text += f"{key}: {value}\n"
        params.setText(params_text)
        params.setMaximumHeight(100)
        layout.addRow("Parameters:", params)
        
        # Delay field
        delay = QSpinBox()
        delay.setRange(0, 10000)
        delay.setValue(step.get("delay_ms", 0))
        delay.setSuffix(" ms")
        layout.addRow("Delay after action:", delay)
        
        # Notes field
        notes = QLineEdit()
        notes.setText(step.get("notes", ""))
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return None
            
        # Parse parameters
        try:
            params_text = params.toPlainText().strip()
            params_dict = {}
            
            if params_text:
                for line in params_text.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        params_dict[key.strip()] = value.strip()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Invalid parameter format: {str(e)}"
            )
            return None
            
        # Create updated step
        return {
            "type": "plugin_action",
            "plugin": plugin.currentText(),
            "action": action.text(),
            "params": params_dict,
            "delay_ms": delay.value(),
            "notes": notes.text()
        }
    
    def _create_vehicle_control_step(self):
        """Create a vehicle control step
        
        Returns:
            Dict with step data or None if cancelled
        """
        # Control types
        control_types = ["engine", "throttle", "brake", "gear", "headlights", 
                        "indicator_left", "indicator_right", "doors_locked"]
        
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Vehicle Control Step")
        layout = QFormLayout(dialog)
        
        # Control type selector
        control = QComboBox()
        for control_type in control_types:
            control.addItem(control_type)
        layout.addRow("Control:", control)
        
        # Value field
        value = QSpinBox()
        value.setRange(0, 100)
        value.setValue(0)
        layout.addRow("Value:", value)
        
        # Logic for updating value field based on control type
        def update_value_field():
            control_type = control.currentText()
            
            if control_type == "engine":
                # Boolean (0/1)
                value.setRange(0, 1)
                value.setPrefix("")
                value.setSuffix("")
                value.setValue(0)
            elif control_type in ["throttle", "brake"]:
                # Percentage (0-100)
                value.setRange(0, 100)
                value.setPrefix("")
                value.setSuffix("%")
                value.setValue(0)
            elif control_type == "gear":
                # Gear (0-7, 0=P, 1-6=forward, 7=R)
                value.setRange(0, 7)
                value.setPrefix("")
                value.setSuffix("")
                value.setValue(0)
            elif control_type in ["headlights", "indicator_left", "indicator_right", "doors_locked"]:
                # Toggle (0/1)
                value.setRange(0, 1)
                value.setPrefix("")
                value.setSuffix("")
                value.setValue(0)
        
        # Connect signal
        control.currentIndexChanged.connect(update_value_field)
        update_value_field()  # Initialize
        
        # Delay field
        delay = QSpinBox()
        delay.setRange(0, 10000)
        delay.setValue(0)
        delay.setSuffix(" ms")
        layout.addRow("Delay after control:", delay)
        
        # Notes field
        notes = QLineEdit()
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return None
            
        # Create step
        return {
            "type": "vehicle_control",
            "control": control.currentText(),
            "value": value.value(),
            "delay_ms": delay.value(),
            "notes": notes.text()
        }
    
    def _edit_vehicle_control_step(self, step):
        """Edit a vehicle control step
        
        Args:
            step: Existing step data
            
        Returns:
            Dict with updated step data or None if cancelled
        """
        # Control types
        control_types = ["engine", "throttle", "brake", "gear", "headlights", 
                        "indicator_left", "indicator_right", "doors_locked"]
        
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Vehicle Control Step")
        layout = QFormLayout(dialog)
        
        # Control type selector
        control = QComboBox()
        current_control = step.get("control", "")
        
        for control_type in control_types:
            control.addItem(control_type)
            
        # Set current control
        index = control.findText(current_control)
        if index >= 0:
            control.setCurrentIndex(index)
            
        layout.addRow("Control:", control)
        
        # Value field
        value = QSpinBox()
        value.setRange(0, 100)
        value.setValue(step.get("value", 0))
        layout.addRow("Value:", value)
        
        # Logic for updating value field based on control type
        def update_value_field():
            control_type = control.currentText()
            current_value = value.value()
            
            if control_type == "engine":
                # Boolean (0/1)
                value.setRange(0, 1)
                value.setPrefix("")
                value.setSuffix("")
                value.setValue(min(current_value, 1))
            elif control_type in ["throttle", "brake"]:
                # Percentage (0-100)
                value.setRange(0, 100)
                value.setPrefix("")
                value.setSuffix("%")
                value.setValue(current_value)
            elif control_type == "gear":
                # Gear (0-7, 0=P, 1-6=forward, 7=R)
                value.setRange(0, 7)
                value.setPrefix("")
                value.setSuffix("")
                value.setValue(min(current_value, 7))
            elif control_type in ["headlights", "indicator_left", "indicator_right", "doors_locked"]:
                # Toggle (0/1)
                value.setRange(0, 1)
                value.setPrefix("")
                value.setSuffix("")
                value.setValue(min(current_value, 1))
        
        # Connect signal
        control.currentIndexChanged.connect(update_value_field)
        update_value_field()  # Initialize
        
        # Delay field
        delay = QSpinBox()
        delay.setRange(0, 10000)
        delay.setValue(step.get("delay_ms", 0))
        delay.setSuffix(" ms")
        layout.addRow("Delay after control:", delay)
        
        # Notes field
        notes = QLineEdit()
        notes.setText(step.get("notes", ""))
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return None
            
        # Create updated step
        return {
            "type": "vehicle_control",
            "control": control.currentText(),
            "value": value.value(),
            "delay_ms": delay.value(),
            "notes": notes.text()
        }
    
    def save(self):
        """Save the current scenario (called externally)"""
        return self._on_save()
    
    def get_selected_scenario(self):
        """Get the currently selected scenario ID
        
        Returns:
            str: Scenario ID or None if no scenario selected
        """
        if self.current_scenario:
            return self.current_scenario.get("id")
        return None
    
    def refresh_scenarios(self):
        """Refresh the scenarios list"""
        self._load_scenarios()
        
    def trigger_run(self):
        """Trigger the scenario run (called externally)"""
        self._on_run()Accepted:
            return None
            
        # Parse CAN ID
        try:
            can_id_text = can_id.text().strip()
            if can_id_text.startswith("0x"):
                can_id_value = can_id_text  # Keep hex string format
            else:
                can_id_value = int(can_id_text)
        except ValueError:
            QMessageBox.warning(
                self,
                "Error",
                "Invalid CAN ID format"
            )
            return None
            
        # Parse data
        try:
            data_text = data.text().strip()
            data_bytes = []
            
            # Split by spaces
            for part in data_text.split():
                data_bytes.append(int(part, 16))
                
            if len(data_bytes) > 8:
                QMessageBox.warning(
                    self,
                    "Error",
                    "CAN data cannot exceed 8 bytes"
                )
                return None
        except ValueError:
            QMessageBox.warning(
                self,
                "Error",
                "Invalid data format. Use hex bytes separated by spaces (e.g., 01 A2 FF)"
            )
            return None
            
        # Create step
        return {
            "type": "can_message",
            "id": can_id_value,
            "data": data_bytes,
            "extended": extended.isChecked(),
            "delay_ms": delay.value(),
            "notes": notes.text()
        }
    
    def _edit_can_message_step(self, step):
        """Edit a CAN message step
        
        Args:
            step: Existing step data
            
        Returns:
            Dict with updated step data or None if cancelled
        """
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit CAN Message Step")
        layout = QFormLayout(dialog)
        
        # CAN ID field
        can_id = QLineEdit()
        if isinstance(step.get("id"), int):
            can_id.setText(f"0x{step['id']:X}")
        else:
            can_id.setText(str(step.get("id", "")))
        layout.addRow("CAN ID:", can_id)
        
        # Data field
        data = QLineEdit()
        data.setText(" ".join(f"{b:02X}" for b in step.get("data", [])))
        layout.addRow("Data (hex):", data)
        
        # Extended frame checkbox
        extended = QCheckBox("Extended Frame Format")
        extended.setChecked(step.get("extended", False))
        layout.addRow("", extended)
        
        # Delay field
        delay = QSpinBox()
        delay.setRange(0, 10000)
        delay.setValue(step.get("delay_ms", 0))
        delay.setSuffix(" ms")
        layout.addRow("Delay after sending:", delay)
        
        # Notes field
        notes = QLineEdit()
        notes.setText(step.get("notes", ""))
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return None
            
        # Parse CAN ID
        try:
            can_id_text = can_id.text().strip()
            if can_id_text.startswith("0x"):
                can_id_value = can_id_text  # Keep hex string format
            else:
                can_id_value = int(can_id_text)
        except ValueError:
            QMessageBox.warning(
                self,
                "Error",
                "Invalid CAN ID format"
            )
            return None
            
        # Parse data
        try:
            data_text = data.text().strip()
            data_bytes = []
            
            # Split by spaces
            for part in data_text.split():
                data_bytes.append(int(part, 16))
                
            if len(data_bytes) > 8:
                QMessageBox.warning(
                    self,
                    "Error",
                    "CAN data cannot exceed 8 bytes"
                )
                return None
        except ValueError:
            QMessageBox.warning(
                self,
                "Error",
                "Invalid data format. Use hex bytes separated by spaces (e.g., 01 A2 FF)"
            )
            return None
            
        # Create updated step
        return {
            "type": "can_message",
            "id": can_id_value,
            "data": data_bytes,
            "extended": extended.isChecked(),
            "delay_ms": delay.value(),
            "notes": notes.text()
        }
    
    def _create_pause_step(self):
        """Create a pause step
        
        Returns:
            Dict with step data or None if cancelled
        """
        # Create step dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Pause Step")
        layout = QFormLayout(dialog)
        
        # Duration field
        duration = QDoubleSpinBox()
        duration.setRange(0.1, 60.0)
        duration.setValue(1.0)
        duration.setSuffix(" seconds")
        layout.addRow("Duration:", duration)
        
        # Notes field
        notes = QLineEdit()
        layout.addRow("Notes:", notes)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # Show dialog
        if dialog.exec_() != QDialog.#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.1
# License: MIT
# Filename: scenario_tab.py
# Pathname: src/gui/
# Description: Scenario management tab for the TFITPICAN application
# -----------------------------------------------------------------------------

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union, Callable

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QToolBar, 
                                QAction, QTableWidget, QTableWidgetItem, QPushButton, 
                                QLabel, QTextEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
                                QHeaderView, QMenu, QMessageBox, QDialog, QDialogButtonBox,
                                QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
                                QListWidget, QListWidgetItem, QGroupBox, QCheckBox,
                                QFileDialog, QInputDialog)
    from PyQt5.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QIcon, QFont, QColor, QBrush
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

class ScenarioTab(QWidget):
    """Scenario management tab for TFITPICAN"""
    
    # Signal for scenario events
    scenario_signal = pyqtSignal(str, dict)  # event_type, data
    
    def __init__(self, scenario_manager=None, scenario_loader=None, car_simulator=None, 
                sqlite_logger=None, translation_manager=None, error_manager=None):
        """Initialize the scenario tab
        
        Args:
            scenario_manager: Scenario manager instance
            scenario_loader: Scenario loader instance
            car_simulator: Car simulator instance
            sqlite_logger: SQLite logger instance
            translation_manager: Translation manager instance
            error_manager: Error manager instance
        """
        if not GUI_AVAILABLE:
            raise ImportError("PyQt5 is required for the GUI")
            
        super().__init__()
        
        self.logger = logging.getLogger("ScenarioTab")
        self.scenario_manager = scenario_manager
        self.scenario_loader = scenario_loader
        self.car_simulator = car_simulator
        self.sqlite_logger = sqlite_logger
        self.translation_manager = translation_manager
        self.error_manager = error_manager
        
        # Current scenario being edited
        self.current_scenario = None
        self.current_scenario_path = None
        self.scenario_modified = False
        
        # Setup UI
        self._setup_ui()
        
        # Load available scenarios
        self._load_scenarios()
        
        # Set up update timer
        self._setup_timer()
        
        self.logger.info("Scenario tab initialized")
    
    def _setup_ui(self):
        """Set up the tab's user interface"""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(24, 24))
        
        # New scenario button
        self.new_action = QAction("New", self)
        self.new_action.triggered.connect(self._on_new)
        if os.path.exists("assets/new.png"):
            self.new_action.setIcon(QIcon("assets/new.png"))
        self.toolbar.addAction(self.new_action)
        
        # Load scenario button
        self.load_action = QAction("Load", self)
        self.load_action.triggered.connect(self._on_load)
        if os.path.exists("assets/open.png"):
            self.load_action.setIcon(QIcon("assets/open.png"))
        self.toolbar.addAction(self.load_action)
        
        # Save scenario button
        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self._on_save)
        if os.path.exists("assets/save.png"):
            self.save_action.setIcon(QIcon("assets/save.png"))
        self.toolbar.addAction(self.save_action)
        
        self.toolbar.addSeparator()
        
        # Run scenario button
        self.run_action = QAction("Run", self)
        self.run_action.triggered.connect(self._on_run)
        if os.path.exists("assets/run.png"):
            self.run_action.setIcon(QIcon("assets/run.png"))
        self.toolbar.addAction(self.run_action)
        
        # Stop scenario button
        self.stop_action = QAction("Stop", self)
        self.stop_action.triggered.connect(self._on_stop)
        if os.path.exists("assets/stop.png"):
            self.stop_action.setIcon(QIcon("assets/stop.png"))
        self.toolbar.addAction(self.stop_action)
        
        self.toolbar.addSeparator()
        
        # Scenario selector
        self.scenario_selector = QComboBox()
        self.scenario_selector.setMinimumWidth(200)
        self.scenario_selector.currentIndexChanged.connect(self._on_scenario_selected)
        self.toolbar.addWidget(self.scenario_selector)
        
        # Add toolbar to layout
        self.layout.addWidget(self.toolbar)
        
        # Create splitter for scenario information and steps
        self.splitter = QSplitter(Qt.Vertical)
        
        # Scenario info panel
        self.info_panel = QWidget()
        self.info_layout = QFormLayout(self.info_panel)
        
        # Scenario name
        self.scenario_name = QLineEdit()
        self.scenario_name.textChanged.connect(self._on_scenario_modified)
        self.info_layout.addRow("Name:", self.scenario_name)
        
        # Scenario description
        self.scenario_description = QTextEdit()
        self.scenario_description.setMaximumHeight(80)
        self.scenario_description.textChanged.connect(self._on_scenario_modified)
        self.info_layout.addRow("Description:", self.scenario_description)
        
        # Scenario steps panel
        self.steps_panel = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_panel)
        
        # Steps table
        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(5)
        self.steps_table.setHorizontalHeaderLabels(["Type", "Details", "Parameters", "Delay", "Notes"])
        self.steps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.steps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.steps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.steps_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.steps_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.steps_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.steps_table.customContextMenuRequested.connect(self._on_steps_context_menu)
        
        self.steps_layout.addWidget(self.steps_table)
        
        # Steps buttons
        steps_buttons_layout = QHBoxLayout()
        
        self.add_step_button = QPushButton("Add Step")
        self.add_step_button.clicked.connect(self._on_add_step)
        steps_buttons_layout.addWidget(self.add_step_button)
        
        self.edit_step_button = QPushButton("Edit Step")
        self.edit_step_button.clicked.connect(self._on_edit_step)
        steps_buttons_layout.addWidget(self.edit_step_button)
        
        self.remove_step_button = QPushButton("Remove Step")
        self.remove_step_button.clicked.connect(self._on_remove_step)
        steps_buttons_layout.addWidget(self.remove_step_button)
        
        self.