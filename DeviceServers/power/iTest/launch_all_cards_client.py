#!/usr/bin/env python3
"""
Multi-card client launcher for iTest PSU.

This script launches a client that shows all discovered cards in a tabbed interface.
"""

import sys
import json
from pathlib import Path

# Ensure repo root on path
app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget
from taurus.qt.qtgui.application import TaurusApplication
from DeviceServers.power.iTest.DS_iTest_PSU_Widget import Itest_PSU


class MultiCardClient(QWidget):
    """Multi-card tabbed interface for iTest PSU cards."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iTest PSU - All Cards")
        
        # Load discovered devices
        discovered_file = Path(__file__).parent / "discovered_devices.json"
        if not discovered_file.exists():
            raise FileNotFoundError(
                f"No discovered devices file found at {discovered_file}. "
                "Run discover_and_register_cards.py first."
            )
        
        with open(discovered_file) as f:
            discovery_data = json.load(f)
        
        devices = discovery_data.get("tango_devices", [])
        cards = discovery_data.get("cards", [])
        
        if not devices:
            raise ValueError("No devices found in discovery data")
        
        # Create tabbed interface
        self.tab_widget = QTabWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)
        
        # Create a tab for each card
        for i, (device_name, card_info) in enumerate(zip(devices, cards)):
            try:
                slot = card_info.get("slot", i+1)
                model = card_info.get("model", "Unknown")
                
                # Create widget for this card
                widget = Itest_PSU(device_name, parent=self)
                
                # Tab title shows slot and model
                tab_title = f"Slot {slot} ({model})"
                self.tab_widget.addTab(widget, tab_title)
                
                print(f"Added tab: {tab_title} -> {device_name}")
                
            except Exception as e:
                print(f"Error creating tab for {device_name}: {e}")
                continue
        
        # Set a reasonable window size
        self.resize(1200, 800)


def main():
    app = TaurusApplication(sys.argv, cmd_line_parser=None)
    
    try:
        client = MultiCardClient()
        client.show()
        return app.exec_()
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())