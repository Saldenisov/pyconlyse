# iTest Task Manager - Multi-slot sequence and batch operations
"""
Task Manager for iTest PSU - enables sending coordinated tasks to multiple slots,
similar to how OWIS DS can coordinate multiple axes movements.

Features:
- Sequence execution across multiple slots
- Batch parameter changes with timing control  
- Current ramping and step sequences
- Automated testing sequences
- Safety monitoring during operations
"""

import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import threading
from contextlib import contextmanager

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from taurus import Device


class TaskType(Enum):
    """Types of tasks that can be executed"""
    SET_CURRENT = "set_current"
    RAMP_CURRENT = "ramp_current"  
    OUTPUT_CONTROL = "output_control"
    MEASURE = "measure"
    WAIT = "wait"
    SEQUENCE = "sequence"


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Individual task definition"""
    task_id: str
    task_type: TaskType
    slots: List[str]  # Slot names to apply task to
    parameters: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    error_msg: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass  
class TaskSequence:
    """Collection of tasks to execute in order"""
    sequence_id: str
    name: str
    tasks: List[Task]
    status: TaskStatus = TaskStatus.PENDING
    current_task_index: int = 0
    
    def current_task(self) -> Optional[Task]:
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None
        
    def next_task(self) -> bool:
        """Move to next task. Returns True if there are more tasks."""
        self.current_task_index += 1
        return self.current_task_index < len(self.tasks)
        
    def reset(self):
        """Reset sequence to beginning"""
        self.current_task_index = 0
        self.status = TaskStatus.PENDING
        for task in self.tasks:
            task.status = TaskStatus.PENDING
            task.start_time = None
            task.end_time = None
            task.error_msg = ""


class TaskExecutor(QThread):
    """Thread for executing tasks without blocking UI"""
    
    task_started = pyqtSignal(str)  # task_id
    task_completed = pyqtSignal(str, bool, str)  # task_id, success, message
    sequence_completed = pyqtSignal(str, bool, str)  # sequence_id, success, message
    progress_update = pyqtSignal(str, float)  # operation, percentage
    
    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self.device = device
        self.current_sequence: Optional[TaskSequence] = None
        self.should_stop = threading.Event()
        self._lock = threading.Lock()
        
    def execute_sequence(self, sequence: TaskSequence):
        """Start executing a task sequence"""
        with self._lock:
            self.current_sequence = sequence
            self.should_stop.clear()
        self.start()
        
    def stop_execution(self):
        """Stop current execution"""
        self.should_stop.set()
        
    def run(self):
        """Main execution thread"""
        if not self.current_sequence:
            return
            
        sequence = self.current_sequence
        sequence.status = TaskStatus.RUNNING
        sequence.reset()
        
        try:
            while not self.should_stop.is_set():
                task = sequence.current_task()
                if not task:
                    # No more tasks - sequence completed
                    sequence.status = TaskStatus.COMPLETED
                    self.sequence_completed.emit(sequence.sequence_id, True, "Sequence completed successfully")
                    break
                    
                # Execute current task
                success, message = self._execute_task(task)
                
                if not success:
                    task.status = TaskStatus.FAILED
                    task.error_msg = message
                    sequence.status = TaskStatus.FAILED
                    self.sequence_completed.emit(sequence.sequence_id, False, f"Task {task.task_id} failed: {message}")
                    break
                    
                task.status = TaskStatus.COMPLETED
                self.task_completed.emit(task.task_id, True, message)
                
                # Move to next task
                if not sequence.next_task():
                    # All tasks completed
                    sequence.status = TaskStatus.COMPLETED
                    self.sequence_completed.emit(sequence.sequence_id, True, "All tasks completed")
                    break
                    
        except Exception as e:
            sequence.status = TaskStatus.FAILED
            self.sequence_completed.emit(sequence.sequence_id, False, f"Execution error: {e}")
            
    def _execute_task(self, task: Task) -> tuple[bool, str]:
        """Execute a single task"""
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        self.task_started.emit(task.task_id)
        
        try:
            if task.task_type == TaskType.SET_CURRENT:
                return self._execute_set_current(task)
            elif task.task_type == TaskType.RAMP_CURRENT:
                return self._execute_ramp_current(task)
            elif task.task_type == TaskType.OUTPUT_CONTROL:
                return self._execute_output_control(task)
            elif task.task_type == TaskType.MEASURE:
                return self._execute_measure(task)
            elif task.task_type == TaskType.WAIT:
                return self._execute_wait(task)
            else:
                return False, f"Unknown task type: {task.task_type}"
                
        except Exception as e:
            return False, f"Task execution error: {e}"
        finally:
            task.end_time = time.time()
            
    def _execute_set_current(self, task: Task) -> tuple[bool, str]:
        """Set current on specified slots"""
        current = task.parameters.get("current", 0.0)
        errors = []
        
        for slot_name in task.slots:
            try:
                self.device.command_inout("SetOutputCurrent", (slot_name, float(current)))
            except Exception as e:
                errors.append(f"{slot_name}: {e}")
                
        if errors:
            return False, "; ".join(errors)
        return True, f"Set current to {current}A on {len(task.slots)} slots"
        
    def _execute_ramp_current(self, task: Task) -> tuple[bool, str]:
        """Ramp current gradually to target value"""
        start_current = task.parameters.get("start_current", 0.0)
        end_current = task.parameters.get("end_current", 0.0)
        duration = task.parameters.get("duration", 1.0)  # seconds
        steps = task.parameters.get("steps", 10)
        
        step_size = (end_current - start_current) / steps
        step_duration = duration / steps
        
        errors = []
        for i in range(steps + 1):
            if self.should_stop.is_set():
                return False, "Ramp cancelled"
                
            current = start_current + i * step_size
            
            # Set current on all slots
            for slot_name in task.slots:
                try:
                    self.device.command_inout("SetOutputCurrent", (slot_name, float(current)))
                except Exception as e:
                    errors.append(f"{slot_name}: {e}")
                    
            # Update progress
            progress = (i / steps) * 100
            self.progress_update.emit(f"Ramp {task.task_id}", progress)
            
            # Wait before next step (except for last step)
            if i < steps:
                time.sleep(step_duration)
                
        if errors:
            return False, "; ".join(errors)
        return True, f"Ramped current from {start_current}A to {end_current}A over {duration}s"
        
    def _execute_output_control(self, task: Task) -> tuple[bool, str]:
        """Enable/disable outputs on specified slots"""
        enable = task.parameters.get("enable", True)
        errors = []
        
        for slot_name in task.slots:
            try:
                if enable:
                    self.device.command_inout("OutputOn", slot_name)
                else:
                    self.device.command_inout("OutputOff", slot_name)
            except Exception as e:
                errors.append(f"{slot_name}: {e}")
                
        if errors:
            return False, "; ".join(errors)
        action = "Enabled" if enable else "Disabled"
        return True, f"{action} output on {len(task.slots)} slots"
        
    def _execute_measure(self, task: Task) -> tuple[bool, str]:
        """Take measurements from all slots"""
        try:
            raw_data = self.device.command_inout("GetAllOutputs")
            outputs_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            
            # Filter for requested slots if specified
            if task.slots:
                outputs_data = [o for o in outputs_data if o.get("name") in task.slots]
                
            # Store measurements in task parameters for later retrieval
            task.parameters["measurements"] = outputs_data
            
            return True, f"Measured {len(outputs_data)} slots"
        except Exception as e:
            return False, f"Measurement failed: {e}"
            
    def _execute_wait(self, task: Task) -> tuple[bool, str]:
        """Wait for specified duration"""
        duration = task.parameters.get("duration", 1.0)
        
        start_time = time.time()
        while (time.time() - start_time) < duration:
            if self.should_stop.is_set():
                return False, "Wait cancelled"
            time.sleep(0.1)
            
            # Update progress
            elapsed = time.time() - start_time
            progress = (elapsed / duration) * 100
            self.progress_update.emit(f"Wait {task.task_id}", progress)
            
        return True, f"Waited {duration}s"


class TaskManagerWidget(QtWidgets.QWidget):
    """GUI widget for task/sequence management"""
    
    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self.device = device
        self.executor = TaskExecutor(device)
        self.sequences: Dict[str, TaskSequence] = {}
        
        self._setup_ui()
        self._connect_signals()
        self._load_predefined_sequences()
        
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("<h3>Task Manager</h3>")
        layout.addWidget(title)
        
        # Sequence selection
        seq_layout = QtWidgets.QHBoxLayout()
        seq_layout.addWidget(QtWidgets.QLabel("Sequence:"))
        self.sequence_combo = QtWidgets.QComboBox()
        seq_layout.addWidget(self.sequence_combo)
        
        self.load_seq_btn = QtWidgets.QPushButton("Load")
        self.save_seq_btn = QtWidgets.QPushButton("Save")
        seq_layout.addWidget(self.load_seq_btn)
        seq_layout.addWidget(self.save_seq_btn)
        layout.addLayout(seq_layout)
        
        # Control buttons
        control_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start Sequence")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.pause_btn = QtWidgets.QPushButton("Pause")
        
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #F44336; color: white; }")
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # Progress display
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_label = QtWidgets.QLabel("Ready")
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)
        
        # Task list display
        self.task_table = QtWidgets.QTableWidget()
        self.task_table.setColumnCount(5)
        self.task_table.setHorizontalHeaderLabels(["Task", "Type", "Slots", "Status", "Duration"])
        layout.addWidget(self.task_table)
        
        # Log display
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
    def _connect_signals(self):
        self.start_btn.clicked.connect(self._start_sequence)
        self.stop_btn.clicked.connect(self._stop_sequence)
        self.sequence_combo.currentTextChanged.connect(self._on_sequence_changed)
        
        self.executor.task_started.connect(self._on_task_started)
        self.executor.task_completed.connect(self._on_task_completed)
        self.executor.sequence_completed.connect(self._on_sequence_completed)
        self.executor.progress_update.connect(self._on_progress_update)
        
    def _load_predefined_sequences(self):
        """Load some predefined useful sequences"""
        # Current step sequence
        step_sequence = TaskSequence(
            sequence_id="current_steps",
            name="Current Step Test",
            tasks=[
                Task("step1", TaskType.SET_CURRENT, [], {"current": 0.0}),
                Task("wait1", TaskType.WAIT, [], {"duration": 2.0}),
                Task("step2", TaskType.SET_CURRENT, [], {"current": 0.5}),
                Task("wait2", TaskType.WAIT, [], {"duration": 2.0}),
                Task("step3", TaskType.SET_CURRENT, [], {"current": 1.0}),
                Task("wait3", TaskType.WAIT, [], {"duration": 2.0}),
                Task("step4", TaskType.SET_CURRENT, [], {"current": 0.0}),
            ]
        )
        
        # Current ramp sequence
        ramp_sequence = TaskSequence(
            sequence_id="current_ramp",
            name="Current Ramp Test",
            tasks=[
                Task("ramp_up", TaskType.RAMP_CURRENT, [], {
                    "start_current": 0.0, "end_current": 2.0, "duration": 10.0, "steps": 20
                }),
                Task("hold", TaskType.WAIT, [], {"duration": 5.0}),
                Task("ramp_down", TaskType.RAMP_CURRENT, [], {
                    "start_current": 2.0, "end_current": 0.0, "duration": 10.0, "steps": 20
                }),
            ]
        )
        
        # Output cycling sequence
        cycle_sequence = TaskSequence(
            sequence_id="output_cycle",
            name="Output On/Off Cycle",
            tasks=[
                Task("all_off", TaskType.OUTPUT_CONTROL, [], {"enable": False}),
                Task("wait1", TaskType.WAIT, [], {"duration": 1.0}),
                Task("all_on", TaskType.OUTPUT_CONTROL, [], {"enable": True}),
                Task("wait2", TaskType.WAIT, [], {"duration": 3.0}),
                Task("all_off2", TaskType.OUTPUT_CONTROL, [], {"enable": False}),
            ]
        )
        
        self.sequences = {
            "current_steps": step_sequence,
            "current_ramp": ramp_sequence,
            "output_cycle": cycle_sequence,
        }
        
        # Populate combo box
        self.sequence_combo.clear()
        for seq_id, sequence in self.sequences.items():
            self.sequence_combo.addItem(sequence.name, seq_id)
            
    def _start_sequence(self):
        """Start executing the selected sequence"""
        seq_id = self.sequence_combo.currentData()
        if not seq_id or seq_id not in self.sequences:
            QtWidgets.QMessageBox.warning(self, "Task Manager", "No sequence selected")
            return
            
        # Get available slots from device
        try:
            raw_data = self.device.command_inout("GetAllOutputs")
            outputs_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            slot_names = [o.get("name", f"slot_{o.get('slot', '?')}") for o in outputs_data]
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Task Manager", f"Failed to get slot information: {e}")
            return
            
        # Apply slot names to tasks that don't have specific slots assigned
        sequence = self.sequences[seq_id]
        for task in sequence.tasks:
            if not task.slots:  # No specific slots assigned
                task.slots = slot_names
                
        self._log(f"Starting sequence: {sequence.name}")
        self._update_task_table(sequence)
        self.executor.execute_sequence(sequence)
        
    def _stop_sequence(self):
        """Stop current sequence execution"""
        self.executor.stop_execution()
        self._log("Sequence stopped by user")
        
    def _on_sequence_changed(self):
        """Handle sequence selection change"""
        seq_id = self.sequence_combo.currentData()
        if seq_id and seq_id in self.sequences:
            self._update_task_table(self.sequences[seq_id])
            
    def _update_task_table(self, sequence: TaskSequence):
        """Update the task display table"""
        self.task_table.setRowCount(len(sequence.tasks))
        
        for row, task in enumerate(sequence.tasks):
            self.task_table.setItem(row, 0, QtWidgets.QTableWidgetItem(task.task_id))
            self.task_table.setItem(row, 1, QtWidgets.QTableWidgetItem(task.task_type.value))
            self.task_table.setItem(row, 2, QtWidgets.QTableWidgetItem(", ".join(task.slots)))
            self.task_table.setItem(row, 3, QtWidgets.QTableWidgetItem(task.status.value))
            
            duration = task.duration()
            duration_str = f"{duration:.2f}s" if duration else ""
            self.task_table.setItem(row, 4, QtWidgets.QTableWidgetItem(duration_str))
            
        self.task_table.resizeColumnsToContents()
        
    def _on_task_started(self, task_id: str):
        self._log(f"Task started: {task_id}")
        self._update_current_sequence_display()
        
    def _on_task_completed(self, task_id: str, success: bool, message: str):
        status = "completed" if success else "failed"
        self._log(f"Task {status}: {task_id} - {message}")
        self._update_current_sequence_display()
        
    def _on_sequence_completed(self, sequence_id: str, success: bool, message: str):
        status = "completed" if success else "failed"
        self._log(f"Sequence {status}: {sequence_id} - {message}")
        self.progress_bar.setValue(100 if success else 0)
        self.progress_label.setText("Complete" if success else "Failed")
        self._update_current_sequence_display()
        
    def _on_progress_update(self, operation: str, percentage: float):
        self.progress_bar.setValue(int(percentage))
        self.progress_label.setText(f"{operation}: {percentage:.1f}%")
        
    def _update_current_sequence_display(self):
        """Update the task table with current status"""
        if self.executor.current_sequence:
            self._update_task_table(self.executor.current_sequence)
            
    def _log(self, message: str):
        """Add message to log display"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")


# Integration with main grid client
def integrate_task_manager(grid_client):
    """Add task manager as a tab to the main grid client"""
    if hasattr(grid_client, 'device') and grid_client.device:
        task_widget = TaskManagerWidget(grid_client.device)
        
        # Add as a new tab if the main window supports tabs
        if hasattr(grid_client, 'addDockWidget'):
            dock = QtWidgets.QDockWidget("Task Manager", grid_client)
            dock.setWidget(task_widget)
            grid_client.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        else:
            # Create a tab widget if it doesn't exist
            central_widget = grid_client.centralWidget()
            if not isinstance(central_widget, QtWidgets.QTabWidget):
                tab_widget = QtWidgets.QTabWidget()
                tab_widget.addTab(central_widget, "Grid Control")
                tab_widget.addTab(task_widget, "Task Manager")
                grid_client.setCentralWidget(tab_widget)
            else:
                central_widget.addTab(task_widget, "Task Manager")
                
        return task_widget
    return None