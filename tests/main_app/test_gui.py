#!/usr/bin/env python3
"""Simple test for the GUI application that runs for a few seconds."""

import logging
import sys
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

# Add parent directory to path for imports
main_app_path = Path(__file__).parent
sys.path.insert(0, str(main_app_path.parent))

from main_app.ui.main_window import PyConlyseMainWindow

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Test the GUI application by running it for a few seconds."""
    logger.info("Starting PyConlyse GUI test...")

    app = QApplication(sys.argv)

    # Create main window
    window = PyConlyseMainWindow()
    window.show()

    logger.info("GUI window shown successfully!")

    # Create a timer to close the application after 5 seconds
    close_timer = QTimer()
    close_timer.singleShot(
        5000,
        lambda: [
            logger.info("Test completed successfully - GUI is working!"),
            app.quit(),
        ],
    )

    logger.info("Running GUI for 5 seconds to demonstrate functionality...")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
