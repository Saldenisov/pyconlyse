"""Entry point for the forked Treatment GUI.

This file was copied from ``gui.Treatment`` and adjusted to use the
local ``treatment_gui`` package instead of the global ``gui`` modules.
"""

import sys
import logging
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from .models.ClientGUIModels import TreatmentModel
from .controllers.TreatmentController import TreatmentController
from .treatment_config import get_data_folder


app_folder = Path(__file__).resolve().parents[2]


def _get_logger() -> logging.Logger:
    """Return a logger configured for the standalone Treatment GUI.

    If the root logger is already configured (e.g., by main.py), this will
    simply return a logger for this module that inherits the root configuration.
    Otherwise, it sets up a basic configuration for standalone usage.
    """

    logger = logging.getLogger("Treatment")
    
    # Check if root logger is already configured (by main.py)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Root logger is configured - just use it
        logger.info("Using existing root logger configuration")
        return logger
    
    # Root logger not configured - set up basic configuration for standalone usage
    if logger.handlers:
        # Already configured (avoid adding duplicate handlers when main() is
        # called multiple times, e.g. in tests).
        return logger

    logger.setLevel(logging.INFO)

    log_dir = app_folder / "LOG"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "Treatment.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Also log to stderr for convenience when running interactively
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def main() -> None:
    """Run the forked Treatment GUI."""

    logger = _get_logger()
    logger.info("Starting Treatment GUI (forked version)...")

    try:
        data_folder = get_data_folder()
        logger.info(f"Using data folder: {data_folder}")
    except Exception as e:
        logger.error(f"Failed to get data folder: {e}")
        logger.exception("Data folder error traceback:")
        # Use fallback
        data_folder = Path.home()
        logger.warning(f"Using fallback data folder: {data_folder}")

    try:
        app = QApplication(sys.argv)

        # Set an application-wide icon so the OS window/taskbar uses it even
        # before the main window is shown.
        icon_path = app_folder / "Treatment" / "resources" / "sumo2.svg"
        logger.info(f"Icon path resolved to: {icon_path}")
        if icon_path.is_file():
            logger.info("Icon file found; setting application icon.")
            try:
                app.setWindowIcon(QIcon(str(icon_path)))
            except Exception as e:
                logger.warning(f"Could not set application icon: {e}")
        else:
            logger.warning("Icon file not found; using default application icon.")

        logger.info("Creating TreatmentModel...")
        model = TreatmentModel(app_folder, data_folder=data_folder)
        logger.info("TreatmentModel created successfully")
        
        logger.info("Creating TreatmentController...")
        controller = TreatmentController(model)
        logger.info("TreatmentController created successfully")
        
        logger.info("Starting Qt event loop...")
        exit_code = app.exec_()
        logger.info(f"Qt event loop exited with code: {exit_code}")
        
    except Exception as e:
        logger.error("FATAL ERROR in Treatment GUI main()")
        logger.exception(f"Error: {e}")
        # Show error dialog if possible
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"The Treatment GUI encountered a fatal error:\n\n{str(e)}\n\nCheck the log file for details."
            )
        except:
            pass
        raise


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
