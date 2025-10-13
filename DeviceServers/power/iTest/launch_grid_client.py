#!/usr/bin/env python3
"""
Launch script for enhanced iTest PSU Grid Client

Usage:
    python launch_grid_client.py test/itest/psu01                    # Basic grid client
    python launch_grid_client.py test/itest/psu01 --with-tasks       # Include task manager
    python launch_grid_client.py test/itest/psu01 --config single_rack.json  # Use config file
"""

import sys
import argparse
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from PyQt5.QtWidgets import QApplication, QTabWidget
    from PyQt5.QtCore import Qt
    from PyQt5 import QtGui
    
    from DS_iTest_GridClient import ITestGridClient
    from ITestTaskManager import integrate_task_manager
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure PyQt5 and taurus are installed:")
    print("  pip install PyQt5 taurus")
    sys.exit(1)


def apply_dark_theme(app):
    """Apply a modern dark theme to the application"""
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


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced iTest PSU Grid Client - OWIS-style multi-slot control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s test/itest/psu01                          # Basic grid client
  %(prog)s test/itest/psu01 --with-tasks             # With task manager
  %(prog)s test/itest/psu01 --config single_rack.json # Use config file
  %(prog)s test/itest/psu01 --theme light           # Light theme
        """
    )
    
    parser.add_argument(
        "device_name", 
        help="Tango device name (e.g., test/itest/psu01)"
    )
    
    parser.add_argument(
        "--with-tasks", 
        action="store_true", 
        help="Include task manager for sequence execution"
    )
    
    parser.add_argument(
        "--config", 
        help="Configuration file to load (JSON format)"
    )
    
    parser.add_argument(
        "--theme", 
        choices=["dark", "light"], 
        default="dark", 
        help="UI theme (default: dark)"
    )
    
    parser.add_argument(
        "--update-rate", 
        type=int, 
        default=1000, 
        help="Update rate in milliseconds (default: 1000)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("iTest PSU Enhanced Grid Client")
    print("=" * 60)
    print(f"Device: {args.device_name}")
    print(f"Task Manager: {'Yes' if args.with_tasks else 'No'}")
    print(f"Theme: {args.theme}")
    print(f"Update Rate: {args.update_rate} ms")
    if args.config:
        print(f"Config File: {args.config}")
    print("=" * 60)
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("iTest PSU Grid Client")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("PyConlyse")
    
    # Apply theme
    if args.theme == "dark":
        apply_dark_theme(app)
    
    try:
        # Create main client
        client = ITestGridClient(args.device_name)
        
        # Apply custom update rate
        if hasattr(client, 'update_timer'):
            client.update_timer.start(args.update_rate)
        
        # Load configuration if specified
        if args.config:
            config_path = Path(__file__).parent / "config_examples" / args.config
            if config_path.exists():
                print(f"Loading configuration from {config_path}")
                # Configuration loading would be implemented here
            else:
                print(f"Warning: Config file {config_path} not found")
        
        # Add task manager if requested
        if args.with_tasks:
            print("Integrating task manager...")
            task_manager = integrate_task_manager(client)
            if task_manager:
                print("✓ Task manager integrated successfully")
            else:
                print("⚠ Task manager integration failed")
        
        # Show the client
        client.show()
        
        # Center on screen
        screen = app.desktop().screenGeometry()
        size = client.geometry()
        client.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
        
        print("✓ Grid client launched successfully")
        print("\nFeatures:")
        print("  • Grid layout (4 slots per row, like OWIS 4-axis)")
        print("  • Single DS controls multiple slots")
        print("  • Live monitoring and batch operations")
        print("  • Per-slot current control and measurements")
        if args.with_tasks:
            print("  • Task sequences and automation")
        print("\nPress Ctrl+C to exit")
        
        # Start event loop
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Error launching client: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()