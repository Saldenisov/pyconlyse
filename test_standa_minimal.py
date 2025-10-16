#!/usr/bin/env python3
"""Test script for minimal Standa widget"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from DeviceServers.motion.standa.DS_STANDA_LaserPointing_Widget import Standa_LaserPointing

def test_standa_widget():
    """Test the minimal Standa widget"""
    app = QApplication(sys.argv)
    
    # Test device - use one that should exist
    device_name = "elyse/motorized_devices/de1"
    
    # Create main window
    main_window = QWidget()
    main_window.setWindowTitle(f"Test Standa Widget: {device_name}")
    main_window.resize(300, 200)
    
    layout = QVBoxLayout()
    main_window.setLayout(layout)
    
    try:
        # Create widget
        widget = Standa_LaserPointing(device_name)
        layout.addWidget(widget)
        
        print(f"Successfully created widget for {device_name}")
        
    except Exception as e:
        print(f"Error creating widget: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    main_window.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(test_standa_widget())