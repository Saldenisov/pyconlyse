#!/usr/bin/env python3
"""PyConlyse GUI Main Entry Point

This is the GUI-first entry point that starts the GUI immediately
and handles all backend connections asynchronously.
"""

import logging
import sys
from pathlib import Path

# Ensure we have the right path setup
main_app_path = Path(__file__).parent
sys.path.insert(0, str(main_app_path.parent))

# Import GUI window
from main_app.ui.main_window import main as gui_main

# Defer full logging setup to GUI after it shows for faster startup
logger = logging.getLogger(__name__)


def main():
    """Main entry point for GUI application."""
    logger.info("Starting PyConlyse GUI application...")
    # Attempt to initialize Tango to catch potential issues early
    # This is a placeholder and might require more specific Tango client initialization code
    # For example, calling a function that tries to connect to a known Tango device
    # or checks the Tango host/port configuration.
    try:
        from tango import DeviceProxy

        # Try connecting to a dummy device or a known device to check Tango connectivity
        # This line might need to be adjusted based on actual Tango device availability
        DeviceProxy("sys/tg_test/1").ping()
        logger.info("Tango connection test successful.")
    except Exception as e:
        logger.warning(f"Tango connection test failed: {e}")
        logger.warning(
            "This might indicate issues with Tango device servers or network configuration."
        )

    try:
        # Start the GUI application
        # This will return only when the application exits
        return gui_main()

    except Exception as e:
        logger.error(f"Failed to start GUI application: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
