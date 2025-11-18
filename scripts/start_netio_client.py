#!/usr/bin/env python3
"""NETIO Client with Device Selection

This script creates a NETIO client similar to the legacy version,
with options to select which NETIO device servers to control.

Usage:
  python start_netio_client.py [instance] [vis_type]

Where:
  instance: V0, VD2, all (default: shows selection dialog)
  vis_type: FULL, MIN (default: FULL)
"""

import sys
from pathlib import Path
from typing import List, Optional

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# NETIO Device Layouts (similar to legacy)
NETIO_LAYOUTS = {
    "V0": {
        "selection": ["manip/V0/PDU_VO", "manip/SD1/PDU_SD1", "manip/SD2/PDU_SD2"],
        "width": 1,
        "description": "V0 Setup - Main chamber PDUs",
    },
    "VD2": {
        "selection": ["manip/VD2/PDU_VD2", "manip/SD2/PDU_SD2"],
        "width": 1,
        "description": "VD2 Setup - Secondary chamber PDUs",
    },
    "all": {
        "selection": [
            "manip/V0/PDU_VO",
            "manip/VD2/PDU_VD2",
            "manip/SD1/PDU_SD1",
            "manip/SD2/PDU_SD2",
            "manip/ELYSE/PDU_ELYSE",
        ],
        "width": 1,
        "description": "All NETIO PDUs in the system",
    },
    "single": {
        "selection": [],  # Will be populated dynamically
        "width": 1,
        "description": "Single device (specified via command line)",
    },
}


def discover_netio_devices():
    """Discover available NETIO devices from Tango database."""
    devices = []
    try:
        from main_app.core.config import OFFLINE_MODE

        if OFFLINE_MODE:
            print("Offline mode - using predefined device list")
            # Return all known devices from layouts
            for layout_name, layout_info in NETIO_LAYOUTS.items():
                if layout_name != "single":
                    devices.extend(layout_info["selection"])
            return sorted(set(devices))

        from tango import Database

        print("Discovering NETIO devices from Tango database...")

        db = Database()
        all_devices = []

        # Search for devices with NETIO-related patterns
        for prefix in ["ELYSE", "manip"]:
            try:
                exported = list(db.get_device_exported(f"{prefix}*"))
                all_devices.extend(exported)
            except Exception as e:
                print(f"Could not query {prefix}* devices: {e}")

        # Filter for NETIO/PDU devices
        netio_keywords = ["pdu", "netio", "PDU", "NETIO"]
        for device in all_devices:
            device_lower = device.lower()
            if any(keyword.lower() in device_lower for keyword in netio_keywords):
                devices.append(device)

        print(f"Found {len(devices)} NETIO devices: {devices}")
        return sorted(devices)

    except Exception as e:
        print(f"Device discovery failed: {e}")
        # Fallback to predefined list
        fallback_devices = [
            "manip/V0/PDU_VO",
            "manip/VD2/PDU_VD2",
            "manip/SD1/PDU_SD1",
            "manip/SD2/PDU_SD2",
            "manip/ELYSE/PDU_ELYSE",
        ]
        print(f"Using fallback device list: {fallback_devices}")
        return fallback_devices


def create_device_selection_dialog(available_devices: List[str]):
    """Create a dialog to select NETIO devices and configuration."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QButtonGroup,
        QDialog,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QRadioButton,
        QTextEdit,
        QVBoxLayout,
    )

    class NetioSelectionDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("NETIO Client - Device Selection")
            self.setMinimumSize(500, 600)

            self.selected_devices = []
            self.vis_type = "FULL"

            layout = QVBoxLayout()

            # Title
            title = QLabel("NETIO Power Distribution Unit Client")
            title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)

            # Preset configurations
            preset_group = QGroupBox("Preset Configurations")
            preset_layout = QVBoxLayout()

            self.preset_group = QButtonGroup()
            for layout_name, layout_info in NETIO_LAYOUTS.items():
                if layout_name == "single":
                    continue

                rb = QRadioButton(
                    f"{layout_name.upper()} - {layout_info['description']}"
                )
                rb.setProperty("layout_name", layout_name)
                rb.toggled.connect(self.on_preset_selected)
                self.preset_group.addButton(rb)
                preset_layout.addWidget(rb)

                # Show devices in this preset
                devices_text = QLabel(
                    f"  Devices: {', '.join(layout_info['selection'])}"
                )
                devices_text.setStyleSheet(
                    "font-size: 10px; color: gray; margin-left: 20px;"
                )
                devices_text.setWordWrap(True)
                preset_layout.addWidget(devices_text)

            # Custom selection option
            self.custom_rb = QRadioButton("Custom Selection")
            self.custom_rb.setProperty("layout_name", "custom")
            self.custom_rb.toggled.connect(self.on_preset_selected)
            self.preset_group.addButton(self.custom_rb)
            preset_layout.addWidget(self.custom_rb)

            preset_group.setLayout(preset_layout)
            layout.addWidget(preset_group)

            # Available devices (for custom selection)
            self.devices_group = QGroupBox("Available NETIO Devices")
            devices_layout = QVBoxLayout()

            self.device_list = QListWidget()
            self.device_list.setSelectionMode(QListWidget.MultiSelection)

            for device in available_devices:
                item = QListWidgetItem(device)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.device_list.addItem(item)

            devices_layout.addWidget(self.device_list)
            self.devices_group.setLayout(devices_layout)
            self.devices_group.setEnabled(False)  # Disabled initially
            layout.addWidget(self.devices_group)

            # Visualization type
            vis_group = QGroupBox("Visualization Type")
            vis_layout = QHBoxLayout()

            self.vis_group = QButtonGroup()
            for vis_type in ["FULL", "MIN"]:
                rb = QRadioButton(vis_type)
                rb.setProperty("vis_type", vis_type)
                rb.toggled.connect(self.on_vis_type_selected)
                if vis_type == "FULL":
                    rb.setChecked(True)
                self.vis_group.addButton(rb)
                vis_layout.addWidget(rb)

            vis_layout.addStretch()
            vis_group.setLayout(vis_layout)
            layout.addWidget(vis_group)

            # Info text
            info_text = QTextEdit()
            info_text.setMaximumHeight(80)
            info_text.setReadOnly(True)
            info_text.setText(
                "FULL: Complete interface with all controls and status\n"
                "MIN: Minimal interface with essential controls only"
            )
            layout.addWidget(info_text)

            # Buttons
            button_layout = QHBoxLayout()

            self.launch_btn = QPushButton("Launch NETIO Client")
            self.launch_btn.clicked.connect(self.accept)
            self.launch_btn.setStyleSheet(
                "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }"
            )

            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)

            button_layout.addStretch()
            button_layout.addWidget(cancel_btn)
            button_layout.addWidget(self.launch_btn)

            layout.addLayout(button_layout)

            self.setLayout(layout)

            # Set default selection
            if self.preset_group.buttons():
                self.preset_group.buttons()[0].setChecked(True)  # Select first preset

        def on_preset_selected(self):
            sender = self.sender()
            if sender.isChecked():
                layout_name = sender.property("layout_name")

                if layout_name == "custom":
                    self.devices_group.setEnabled(True)
                    self.selected_devices = self.get_custom_selected_devices()
                else:
                    self.devices_group.setEnabled(False)
                    self.selected_devices = NETIO_LAYOUTS[layout_name]["selection"]

        def on_vis_type_selected(self):
            sender = self.sender()
            if sender.isChecked():
                self.vis_type = sender.property("vis_type")

        def get_custom_selected_devices(self):
            devices = []
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item.checkState() == Qt.Checked:
                    devices.append(item.text())
            return devices

        def accept(self):
            # Update selected devices if custom is selected
            if self.custom_rb.isChecked():
                self.selected_devices = self.get_custom_selected_devices()

            if not self.selected_devices:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self, "No Selection", "Please select at least one device."
                )
                return

            super().accept()

    dialog = NetioSelectionDialog()
    if dialog.exec_() == QDialog.Accepted:
        return dialog.selected_devices, dialog.vis_type
    else:
        return None, None


def create_netio_panel(devices: List[str], vis_type: str = "FULL"):
    """Create NETIO panel with multiple devices (similar to legacy GeneralPanel)."""
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import (
        QFrame,
        QLabel,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    try:
        from main_app.core.config import OFFLINE_MODE

        # Main panel widget
        panel = QWidget()
        panel.setWindowTitle(f"NETIO Client - {len(devices)} device(s) - {vis_type}")

        # Set icon if available
        try:
            panel.setWindowIcon(QIcon("icons/NETIO.ico"))
        except:
            pass

        # Main layout
        main_layout = QVBoxLayout()

        # Scroll area for devices (in case there are many)
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        # Create widgets for each device
        widgets = {}

        print(f"Creating NETIO widgets for {len(devices)} devices...")

        for i, device_name in enumerate(devices):
            print(f"Creating widget {i+1}/{len(devices)}: {device_name}")

            try:
                if OFFLINE_MODE:
                    # Create offline placeholder
                    from PyQt5.QtWidgets import QGroupBox

                    group = QGroupBox(f"NETIO Device (Offline): {device_name}")
                    group_layout = QVBoxLayout()

                    offline_label = QLabel(
                        f"Offline mode enabled.\nWould connect to: {device_name}"
                    )
                    offline_label.setWordWrap(True)
                    offline_label.setStyleSheet(
                        "color: orange; font-style: italic; padding: 10px;"
                    )

                    group_layout.addWidget(offline_label)
                    group.setLayout(group_layout)

                    scroll_layout.addWidget(group)
                    widgets[device_name] = group

                else:
                    # Create actual NETIO widget
                    from DeviceServers.power.netio.DS_NETIO_Widget import Netio_pdu
                    from DeviceServers.shared.DS_Widget import VisType

                    vis_enum = VisType.FULL if vis_type == "FULL" else VisType.MIN

                    netio_widget = Netio_pdu(
                        device_name, parent=panel, vis_type=vis_enum
                    )
                    scroll_layout.addWidget(netio_widget)
                    widgets[device_name] = netio_widget

                # Add separator between devices (except for last one)
                if i < len(devices) - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.HLine)
                    separator.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
                    separator.setLineWidth(2)
                    scroll_layout.addWidget(separator)

            except Exception as e:
                print(f"Error creating widget for {device_name}: {e}")

                # Create error placeholder
                from PyQt5.QtWidgets import QGroupBox

                group = QGroupBox(f"NETIO Device (Error): {device_name}")
                group_layout = QVBoxLayout()

                error_label = QLabel(
                    f"Error loading device:\n{device_name}\n\n{str(e)}"
                )
                error_label.setWordWrap(True)
                error_label.setStyleSheet("color: red; padding: 10px;")

                group_layout.addWidget(error_label)
                group.setLayout(group_layout)

                scroll_layout.addWidget(group)
                widgets[device_name] = group

        # Finish scroll layout
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        # Add to main layout
        main_layout.addWidget(scroll_area)

        # Status bar
        status_label = QLabel(
            f"NETIO Client - {len(devices)} device(s) loaded - {vis_type} mode"
        )
        status_label.setStyleSheet(
            "background-color: #f0f0f0; padding: 5px; border-top: 1px solid #ccc;"
        )
        main_layout.addWidget(status_label)

        panel.setLayout(main_layout)

        # Store widgets reference
        panel.netio_widgets = widgets

        # Set reasonable size
        panel.resize(1000, 600)

        return panel

    except Exception as e:
        print(f"Error creating NETIO panel: {e}")
        import traceback

        traceback.print_exc()
        return None


def start_netio_client(instance: Optional[str] = None, vis_type: Optional[str] = None):
    """Start NETIO client with device selection capabilities."""

    try:
        print("=== NETIO Client Launcher ===")
        print("Initializing PyQt5...")

        from PyQt5.QtWidgets import QApplication

        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            app.setApplicationName("NETIO Client")

        print("PyQt5 initialized successfully")

        # Check arguments
        if instance is None and len(sys.argv) >= 2:
            instance = sys.argv[1]
        if vis_type is None and len(sys.argv) >= 3:
            vis_type = sys.argv[2]

        # Set defaults
        if vis_type is None:
            vis_type = "FULL"

        print(f"Instance: {instance}, Vis Type: {vis_type}")

        # Determine devices to use
        if instance and instance in NETIO_LAYOUTS:
            # Use predefined layout
            devices = NETIO_LAYOUTS[instance]["selection"]
            print(f"Using predefined layout '{instance}': {devices}")
        elif instance and instance not in ["V0", "VD2", "all"]:
            # Single device specified
            devices = [instance]
            print(f"Using single device: {instance}")
        else:
            # Show selection dialog
            print("Discovering available devices...")
            available_devices = discover_netio_devices()

            if not available_devices:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    None, "No Devices", "No NETIO devices found or available."
                )
                return 1

            print("Showing device selection dialog...")
            devices, vis_type = create_device_selection_dialog(available_devices)

            if not devices:
                print("No devices selected or dialog cancelled")
                return 0

        print(f"Creating NETIO panel for devices: {devices}")

        # Create and show panel
        panel = create_netio_panel(devices, vis_type)
        if panel is None:
            print("Failed to create NETIO panel")
            return 1

        panel.show()
        print("NETIO client started successfully")

        # Run event loop
        return app.exec_()

    except Exception as e:
        print(f"Error starting NETIO client: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    print("=== NETIO Client with Device Selection ===")
    print("Available instances: V0, VD2, all, or custom device name")
    print("Available vis_types: FULL, MIN")
    print()

    exit_code = start_netio_client()
    sys.exit(exit_code)
