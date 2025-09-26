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

# Import GUI window (simple, legacy-like modular GUI)
# Central logging setup
from main_app.core.logging_config import setup_pyconlyse_logging
from main_app.ui.simple_main_window import main as gui_main

logger = logging.getLogger(__name__)


def main():
    """Main entry point for GUI application."""
    # Initialize logging early so all GUI logs go to LOGS/GUI
    try:
        log_dir = Path(__file__).parent.parent / "LOGS" / "GUI"
        setup_pyconlyse_logging(log_dir)
    except Exception:
        # If logging setup fails, continue with console logging
        pass

    logger.info(
        "Starting PyConlyse GUI application (no DS connections during startup)."
    )
    # NOTE: DS/Tango connectivity checks are intentionally deferred until after the GUI is shown.
    # If you later need a connectivity probe, use Taurus (e.g., taurus.Device) in deferred code,
    # not PyTango's DeviceProxy.

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
