#!/usr/bin/env python3
"""PyConlyse Main Application Entry Point

This is the main entry point for the modular PyConlyse application.
It orchestrates the startup sequence and coordinates between components.
"""

import logging
import sys
from pathlib import Path

# Add main_app parent directory to path for package imports
main_app_path = Path(__file__).parent
sys.path.insert(0, str(main_app_path.parent))

# Import as a package
from main_app.core.config import *
from main_app.managers.device_manager import DeviceServerManager
from main_app.managers.infrastructure_manager import TangoInfrastructureManager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PyConlyseApplication:
    """Main PyConlyse Application class that coordinates all components."""

    def __init__(self, bin_path: Path = None):
        """Initialize the application with component managers.

        Args:
            bin_path: Path to the bin directory containing batch files

        """
        # Use parent directory (bin) as default bin_path
        self.bin_path = bin_path or main_app_path.parent / "bin"

        # Initialize managers
        self.infrastructure_mgr = TangoInfrastructureManager(self.bin_path)
        self.device_mgr = DeviceServerManager(self.bin_path)

        logger.info(f"PyConlyse Application initialized with bin path: {self.bin_path}")

    def start_infrastructure(self, progress_callback=None):
        """Start the Tango infrastructure."""
        logger.info("Starting Tango infrastructure...")
        return self.infrastructure_mgr.start_infrastructure(progress_callback)

    def start_device_server(
        self, device_type: str, instance: str, vis_type: str = "FULL"
    ):
        """Start a specific device server."""
        logger.info(f"Starting device server: {device_type}/{instance}")
        return self.device_mgr.start_deviceserver(device_type, instance, vis_type)

    def start_all_device_servers(self):
        """Start all configured device servers."""
        logger.info("Starting all configured device servers...")
        return self.device_mgr.start_all_configured_servers()

    def stop_infrastructure(self):
        """Stop the Tango infrastructure."""
        logger.info("Stopping Tango infrastructure...")
        return self.infrastructure_mgr.stop_infrastructure()

    def stop_all_device_servers(self):
        """Stop all running device servers."""
        logger.info("Stopping all device servers...")
        return self.device_mgr.stop_all_servers()

    def get_status(self):
        """Get complete application status."""
        return {
            "infrastructure": self.infrastructure_mgr.get_status(),
            "devices": self.device_mgr.get_running_servers(),
        }

    def shutdown(self):
        """Graceful shutdown of all components."""
        logger.info("Shutting down PyConlyse application...")

        # Stop device servers first
        self.stop_all_device_servers()

        # Then stop infrastructure
        self.stop_infrastructure()

        logger.info("PyConlyse application shutdown complete")


def main():
    """Main entry point for the application."""
    logger.info("Starting PyConlyse Application v2.0")

    try:
        # Create application instance
        app = PyConlyseApplication()

        # Print status
        status = app.get_status()
        logger.info("Application Status:")
        logger.info(f"Infrastructure: {status['infrastructure']}")
        logger.info(f"Device servers: {len(status['devices'])} running")

        # For now, just demonstrate the components are working
        logger.info("PyConlyse application ready!")
        logger.info("Use the managers directly or extend this entry point as needed.")

        return 0

    except Exception as e:
        logger.error(f"Failed to start PyConlyse application: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
