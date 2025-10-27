"""
DAQmx ZMQ Widget for displaying PSP variables in real-time
"""
import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QWidget, QGridLayout, QPushButton, QTabWidget
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType
from taurus import Device


class DAQmxZMQ_Widget(DS_General_Widget):
    """Widget for displaying DAQmx ZMQ data from LabVIEW PSP"""
    
    def __init__(self, dev_name: str, panel=None, vis: VisType = VisType.FULL):
        # Data storage - initialize before super()
        self.channel_labels = {}
        self.channel_values = {}
        self.update_timer = None
        
        # Category tabs
        self.category_grids = {}
        self.category_tabs = {}
        self.category_row_counters = {}
        
        super().__init__(dev_name, panel, vis)
    
    def register_full_layouts(self):
        """Required by DS_General_Widget"""
        super().register_full_layouts()
        # Add status display if in FULL mode
        self.set_state_status()
        # Add custom layouts to the parent's main layout
        lo_group_1 = getattr(self, f"lo_group_{1}")
        layout_main = getattr(self, f"layout_main_{self.dev_name}")
        lo_group_1.addLayout(layout_main)
        self._build_custom_ui()
        # Start update timer after UI is built
        self.start_updates()
    
    def register_min_layouts(self):
        """Required by DS_General_Widget"""
        super().register_min_layouts()
        # Add status display if in MIN mode
        self.set_state_status()
        # Add custom layouts to the parent's main layout
        lo_group_1 = getattr(self, f"lo_group_{1}")
        layout_main = getattr(self, f"layout_main_{self.dev_name}")
        lo_group_1.addLayout(layout_main)
        self._build_custom_ui()
        # Start update timer after UI is built
        self.start_updates()
    
    def set_the_control_value(self, value):
        """Required by DS_General_Widget"""
        pass
    
    def _build_custom_ui(self):
        """Build custom UI components"""
        # Get the main layout from parent
        layout_main = getattr(self, f"layout_main_{self.dev_name}")
        
        # Header with device info
        header_group = QGroupBox("DAQmx ZMQ Reader")
        header_layout = QVBoxLayout()
        
        self.device_label = QLabel(f"Device: {self.dev_name}")
        self.device_label.setFont(QFont("Arial", 10, QFont.Bold))
        header_layout.addWidget(self.device_label)
        
        # Status info
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Connecting...")
        self.messages_label = QLabel("Messages: 0")
        self.samples_label = QLabel("Samples: 0")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.messages_label)
        status_layout.addWidget(self.samples_label)
        status_layout.addStretch()
        header_layout.addLayout(status_layout)
        
        header_group.setLayout(header_layout)
        layout_main.addWidget(header_group)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh Data")
        self.btn_refresh.clicked.connect(self.force_update)
        self.btn_clear = QPushButton("Clear Display")
        self.btn_clear.clicked.connect(self.clear_display)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        layout_main.addLayout(btn_layout)
        
        # Tabbed interface for categorized channels
        self.tabs = QTabWidget()
        
        # Define categories based on channel path patterns
        categories = [
            ("Vacuum", "vacuum"),
            ("Sync", "sync"),
            ("Magnets", "magnets"),
            ("Modulator", "modulator"),
            ("HF", "HF"),
            ("HT", "HT"),
            ("Cooling", "cooling"),
            ("Preamplifier", "preamplifier"),
            ("All", None),  # None means show everything
        ]
        
        # Create tab for each category
        for tab_name, filter_key in categories:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_content = QWidget()
            grid = QGridLayout(scroll_content)
            grid.setColumnStretch(1, 1)
            
            # Header for grid
            header_name = QLabel("Channel")
            header_name.setFont(QFont("Arial", 9, QFont.Bold))
            header_value = QLabel("Value")
            header_value.setFont(QFont("Arial", 9, QFont.Bold))
            grid.addWidget(header_name, 0, 0)
            grid.addWidget(header_value, 0, 1)
            
            scroll.setWidget(scroll_content)
            self.tabs.addTab(scroll, tab_name)
            
            # Store grid and filter for later use
            self.category_grids[tab_name] = grid
            self.category_tabs[tab_name] = filter_key
            self.category_row_counters[tab_name] = 1  # Start after header
        
        layout_main.addWidget(self.tabs)
    
    def start_updates(self):
        """Start periodic updates"""
        if self.update_timer is None:
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self.update_data)
            self.update_timer.start(1000)  # Update every 1 second
    
    def stop_updates(self):
        """Stop periodic updates"""
        if self.update_timer:
            self.update_timer.stop()
    
    def update_data(self):
        """Update displayed data from device"""
        try:
            # Use the device from parent class
            device = self.ds
            
            # Update status
            try:
                state = str(device.state)
                zmq_status = device.zmq_status
                messages = device.messages_received
                samples = device.sample_count
                
                self.status_label.setText(f"Status: {state} | {zmq_status}")
                self.messages_label.setText(f"Messages: {messages}")
                self.samples_label.setText(f"Samples: {samples}")
            except Exception as e:
                self.status_label.setText(f"Status: Error reading status - {e}")
                print(f"Error reading status: {e}")
            
            # Get channel data
            try:
                import json
                latest_json = device.latest_values_json
                latest = json.loads(latest_json)
                data = latest.get('data', {})
                
                print(f"Retrieved {len(data)} channels")
                
                # Update channel displays
                if data:
                    self._update_channels(data)
                else:
                    print("No data available yet")
                
            except Exception as e:
                print(f"Error reading channel data: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            error_msg = f"Status: Connection Error - {e}"
            self.status_label.setText(error_msg)
            print(error_msg)
    
    def _update_channels(self, data: dict):
        """Update or create channel displays in appropriate tabs"""
        # Get sorted channel names for consistent display
        sorted_channels = sorted(data.keys())
        
        for channel in sorted_channels:
            value = data[channel]
            
            # Determine which categories this channel belongs to
            matching_categories = []
            for cat_name, filter_key in self.category_tabs.items():
                if filter_key is None:  # "All" category
                    matching_categories.append(cat_name)
                elif filter_key in channel:
                    matching_categories.append(cat_name)
            
            # Create or update labels in each matching category
            for cat_name in matching_categories:
                grid = self.category_grids[cat_name]
                label_key = f"{cat_name}::{channel}"
                
                # Create new labels if channel doesn't exist in this category
                if label_key not in self.channel_labels:
                    name_label = QLabel(channel)
                    name_label.setFont(QFont("Courier", 8))
                    value_label = QLabel()
                    value_label.setFont(QFont("Courier", 8, QFont.Bold))
                    
                    row = self.category_row_counters[cat_name]
                    grid.addWidget(name_label, row, 0)
                    grid.addWidget(value_label, row, 1)
                    
                    self.channel_labels[label_key] = name_label
                    self.channel_values[label_key] = value_label
                    self.category_row_counters[cat_name] += 1
                
                # Update value
                value_label = self.channel_values[label_key]
                if isinstance(value, float):
                    value_label.setText(f"{value:.6g}")
                else:
                    value_label.setText(str(value))
    
    def force_update(self):
        """Force an immediate update"""
        self.update_data()
    
    def clear_display(self):
        """Clear all channel displays"""
        # Remove all channel widgets
        for channel in list(self.channel_labels.keys()):
            self.channel_labels[channel].deleteLater()
            self.channel_values[channel].deleteLater()
        
        self.channel_labels.clear()
        self.channel_values.clear()
    
    def closeEvent(self, event):
        """Handle widget close"""
        self.stop_updates()
        super().closeEvent(event)
