#!/usr/bin/env python3
"""
iTest PSU Client Launcher for PyConlyse Integration

This script provides the enhanced grid-based client interface for iTest Power Supply Units
that integrates with the PyConlyse main application.

Usage (called from PyConlyse main app):
    python DS_iTest_PSU_client.py ITestPSU/test [VIS_TYPE]

Usage (standalone):
    python DS_iTest_PSU_client.py test/itest/psu01 --standalone

Features:
- Enhanced grid-based client (no tabs, grid layout for all slots)
- One Device Server controls multiple slots (like OWIS pattern)
- Task manager integration for sequences and automation
- Flexible slot count (works with 8 slots, 16 slots, or any number)
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

# Add current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent.parent.parent))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
    from PyQt5 import QtGui
    
    # Import our enhanced grid client
    from DS_iTest_GridClient import ITestGridClient
    from ITestTaskManager import integrate_task_manager
    
    # Import PyConlyse DS widget framework for fallback compatibility
    try:
        from DeviceServers.shared.DS_Widget import VisType
    except ImportError:
        # Define fallback if not available
        from enum import Enum
        class VisType(Enum):
            FULL = "FULL"
            MIN = "MIN"
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure PyQt5, taurus, and required dependencies are installed")
    sys.exit(1)


def resolve_device_name(config_name: str) -> str:
    """
    Resolve configuration name to actual device name.
    
    This maps the configuration names used in PyConlyse to actual Tango device names.
    """
    # Configuration mappings for iTest devices
    config_mappings = {
        # Presets
        "ELYSE": "ELYSE/pdu/iTest",
        "ITestPSU/ELYSE": "ELYSE/pdu/iTest",
        # Common configs
        "ITestPSU/test": "test/itest/psu01",
        "ITestPSU/main": "manip/power/itest_psu01", 
        "ITestPSU/lab": "lab/itest/psu01",
        "ITestPSU/bilt": "bilt/power/itest_main",
        # Short aliases
        "test": "test/itest/psu01",
        "main": "manip/power/itest_psu01",
        "lab": "lab/itest/psu01",
        "bilt": "bilt/power/itest_main",
    }
    
    # If it's already a device name format (contains slashes), use as-is
    if "/" in config_name and config_name not in config_mappings:
        return config_name
        
    # Otherwise map from config name
    return config_mappings.get(config_name, config_name)


def apply_theme(app: QApplication, theme: str = "dark"):
    """Apply visual theme to the application"""
    if theme == "dark":
        app.setStyle('Fusion')
        
        palette = QtGui.QPalette()
        
        # Dark theme colors
        window_color = QtGui.QColor(53, 53, 53)
        windowText_color = QtGui.QColor(255, 255, 255)
        base_color = QtGui.QColor(25, 25, 25)
        alternateBase_color = QtGui.QColor(53, 53, 53)
        toolTipBase_color = QtGui.QColor(0, 0, 0)
        toolTipText_color = QtGui.QColor(255, 255, 255)
        text_color = QtGui.QColor(255, 255, 255)
        button_color = QtGui.QColor(53, 53, 53)
        buttonText_color = QtGui.QColor(255, 255, 255)
        brightText_color = QtGui.QColor(255, 0, 0)
        link_color = QtGui.QColor(42, 130, 218)
        highlight_color = QtGui.QColor(42, 130, 218)
        highlightedText_color = QtGui.QColor(0, 0, 0)
        
        palette.setColor(QtGui.QPalette.Window, window_color)
        palette.setColor(QtGui.QPalette.WindowText, windowText_color)
        palette.setColor(QtGui.QPalette.Base, base_color)
        palette.setColor(QtGui.QPalette.AlternateBase, alternateBase_color)
        palette.setColor(QtGui.QPalette.ToolTipBase, toolTipBase_color)
        palette.setColor(QtGui.QPalette.ToolTipText, toolTipText_color)
        palette.setColor(QtGui.QPalette.Text, text_color)
        palette.setColor(QtGui.QPalette.Button, button_color)
        palette.setColor(QtGui.QPalette.ButtonText, buttonText_color)
        palette.setColor(QtGui.QPalette.BrightText, brightText_color)
        palette.setColor(QtGui.QPalette.Link, link_color)
        palette.setColor(QtGui.QPalette.Highlight, highlight_color)
        palette.setColor(QtGui.QPalette.HighlightedText, highlightedText_color)
        
        app.setPalette(palette)


def create_itest_client(device_name: str, vis_type: VisType = VisType.FULL, with_tasks: bool = True) -> Optional[ITestGridClient]:
    """
    Create and configure an iTest PSU grid client.
    
    Args:
        device_name: Tango device name
        vis_type: Visualization type (FULL or MIN)
        with_tasks: Whether to include task manager
    
    Returns:
        Configured client widget or None if failed
    """
    try:
        logger.info(f"Creating iTest client for device: {device_name}")
        
        # Create the enhanced grid client
        client = ITestGridClient(device_name)
        
        # Set window properties
        client.setWindowTitle(f"iTest PSU Grid Client - {device_name}")
        
        # Add task manager if requested and vis_type is FULL
        if with_tasks and vis_type == VisType.FULL:
            logger.info("Integrating task manager...")
            task_manager = integrate_task_manager(client)
            if task_manager:
                logger.info("✓ Task manager integrated successfully")
            else:
                logger.warning("⚠ Task manager integration failed")
        
        # Configure based on visualization type
        if vis_type == VisType.MIN:
            # For minimal view, hide some elements
            if hasattr(client, 'all_on_btn'):
                client.all_on_btn.hide()
            if hasattr(client, 'all_off_btn'):
                client.all_off_btn.hide()
            if hasattr(client, 'zero_all_btn'):
                client.zero_all_btn.hide()
            
            # Smaller window for minimal view
            client.resize(800, 600)
        else:
            # Full view - all features visible
            client.resize(1200, 800)
        
        logger.info(f"✓ iTest client created successfully for {device_name}")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create iTest client: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point for iTest PSU client"""
    # Handle legacy PyConlyse calling convention: script config_name [vis_type]
    if len(sys.argv) >= 2 and "--" not in " ".join(sys.argv):
        # Legacy mode: called from PyConlyse main app
        config_name = sys.argv[1]
        vis_type_str = sys.argv[2] if len(sys.argv) > 2 else "FULL"
        
        device_name = resolve_device_name(config_name)
        vis_type = VisType.FULL if vis_type_str == "FULL" else VisType.MIN
        with_tasks = (vis_type == VisType.FULL)  # Only include tasks in FULL mode
        
        logger.info(f"Legacy mode: {config_name} → {device_name} ({vis_type.value})")
        
        # Create QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("iTest PSU Grid Client")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("PyConlyse")
        
        # Apply dark theme
        apply_theme(app, "dark")
        
        try:
            # Create client
            client = create_itest_client(device_name, vis_type, with_tasks)
            
            if not client:
                QMessageBox.critical(
                    None, 
                    "iTest Client Error", 
                    f"Failed to create iTest client for device: {device_name}"
                )
                return 1
            
            # Show the client
            client.show()
            
            logger.info("✓ iTest client launched from PyConlyse")
            
            # Start event loop
            return app.exec_()
            
        except Exception as e:
            logger.error(f"Error running iTest client: {e}")
            QMessageBox.critical(
                None, 
                "iTest Client Error", 
                f"An error occurred:\n{str(e)}\n\nCheck console for details."
            )
            return 1
    
    else:
        # Modern mode: use argparse for standalone usage
        parser = argparse.ArgumentParser(
            description="iTest PSU Grid Client - Enhanced multi-slot power supply control",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # From PyConlyse (configuration name):
  %(prog)s ITestPSU/test FULL
  %(prog)s ITestPSU/bilt MIN
  
  # Standalone (device name):
  %(prog)s --standalone test/itest/psu01
  %(prog)s --standalone bilt/power/itest_main --no-tasks
            """
        )
        
        parser.add_argument(
            "config_or_device", 
            help="Configuration name (from PyConlyse) or Tango device name"
        )
        
        parser.add_argument(
            "vis_type", 
            nargs="?", 
            default="FULL",
            choices=["FULL", "MIN"],
            help="Visualization type (default: FULL)"
        )
        
        parser.add_argument(
            "--standalone", 
            action="store_true", 
            help="Run as standalone application (not called from PyConlyse)"
        )
        
        parser.add_argument(
            "--no-tasks", 
            action="store_true", 
            help="Disable task manager integration"
        )
        
        parser.add_argument(
            "--theme", 
            choices=["dark", "light"], 
            default="dark", 
            help="UI theme (default: dark)"
        )
        
        parser.add_argument(
            "--debug", 
            action="store_true", 
            help="Enable debug logging"
        )
        
        args = parser.parse_args()
        
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Resolve device name
        device_name = resolve_device_name(args.config_or_device)
        vis_type = VisType.FULL if args.vis_type == "FULL" else VisType.MIN
        with_tasks = not args.no_tasks
        
        logger.info("=" * 60)
        logger.info("iTest PSU Enhanced Grid Client")
        logger.info("=" * 60)
        logger.info(f"Config/Device: {args.config_or_device} → {device_name}")
        logger.info(f"Visualization: {vis_type.value}")
        logger.info(f"Task Manager: {'Yes' if with_tasks else 'No'}")
        logger.info(f"Theme: {args.theme}")
        logger.info(f"Standalone: {'Yes' if args.standalone else 'No'}")
        logger.info("=" * 60)
        
        # Create QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("iTest PSU Grid Client")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("PyConlyse")
        
        # Apply theme
        apply_theme(app, args.theme)
        
        try:
            # Create client
            client = create_itest_client(device_name, vis_type, with_tasks)
            
            if not client:
                QMessageBox.critical(
                    None, 
                    "iTest Client Error", 
                    f"Failed to create iTest client for device: {device_name}"
                )
                return 1
            
            # Show the client
            client.show()
            
            # Center on screen
            if args.standalone:
                screen = app.desktop().screenGeometry()
                size = client.geometry()
                client.move(
                    (screen.width() - size.width()) // 2,
                    (screen.height() - size.height()) // 2
                )
            
            logger.info("✓ iTest client launched successfully")
            logger.info("")
            logger.info("Client Features:")
            logger.info("  • Grid layout for all slots (flexible layout)")
            logger.info("  • Single DS controls multiple slots")
            logger.info("  • Live monitoring and batch operations")
            logger.info("  • Per-slot current control and measurements")
            if with_tasks and vis_type == VisType.FULL:
                logger.info("  • Task sequences and automation")
            logger.info("")
            
            if args.standalone:
                logger.info("Press Ctrl+C in terminal or close window to exit")
            
            # Start event loop
            return app.exec_()
            
        except Exception as e:
            logger.error(f"Error running iTest client: {e}")
            import traceback
            traceback.print_exc()
            
            QMessageBox.critical(
                None, 
                "iTest Client Error", 
                f"An error occurred:\n{str(e)}\n\nCheck console for details."
            )
            return 1


if __name__ == "__main__":
    sys.exit(main())
