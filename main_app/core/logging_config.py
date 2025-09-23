#!/usr/bin/env python3
"""Logging Configuration for PyConlyse

Provides centralized logging configuration with file output and GUI integration.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class GuiLogHandler(logging.Handler):
    """Custom log handler that can emit signals to GUI components."""

    def __init__(self):
        super().__init__()
        self.gui_callback = None

    def set_gui_callback(self, callback):
        """Set callback function for GUI log updates."""
        self.gui_callback = callback

    def emit(self, record):
        """Emit log record to GUI if callback is set."""
        if self.gui_callback:
            try:
                msg = self.format(record)
                self.gui_callback(record.levelname, msg, record.created)
            except Exception:
                # Avoid recursive errors in logging
                pass


class PyConlyseLogger:
    """Centralized logging manager for PyConlyse application."""

    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize the logging system.

        Args:
            log_dir: Directory for log files. If None, defaults to <repo_root>/LOGS/GUI

        """
        # Default logs for GUI go to <repo_root>/LOGS/GUI
        default_gui_logs = Path(__file__).parent.parent.parent / "LOGS" / "GUI"
        self.log_dir = log_dir or default_gui_logs
        # Ensure directory exists (create parents if needed)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create GUI handler for real-time log display
        self.gui_handler = GuiLogHandler()
        self.setup_logging()

    def setup_logging(self):
        """Configure the logging system with file and GUI output."""
        # Create formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        gui_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create log files with timestamps
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Main application log (detailed)
        main_log_file = self.log_dir / f"pyconlyse_main_{timestamp}.log"
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        main_handler.setFormatter(detailed_formatter)
        main_handler.setLevel(logging.DEBUG)

        # Infrastructure operations log
        infra_log_file = self.log_dir / f"pyconlyse_infrastructure_{timestamp}.log"
        infra_handler = logging.handlers.RotatingFileHandler(
            infra_log_file, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        infra_handler.setFormatter(detailed_formatter)
        infra_handler.setLevel(logging.INFO)

        # Device server operations log
        device_log_file = self.log_dir / f"pyconlyse_devices_{timestamp}.log"
        device_handler = logging.handlers.RotatingFileHandler(
            device_log_file, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        device_handler.setFormatter(detailed_formatter)
        device_handler.setLevel(logging.INFO)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Attach file handlers (avoid duplicates)
        if not any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            and h.baseFilename == str(main_log_file)
            for h in root_logger.handlers
        ):
            root_logger.addHandler(main_handler)

        # Add console handler only if there isn't one already
        has_console = any(
            isinstance(h, logging.StreamHandler) for h in root_logger.handlers
        )
        if not has_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(simple_formatter)
            console_handler.setLevel(logging.INFO)
            root_logger.addHandler(console_handler)

        # Setup GUI handler (avoid duplicates)
        if not any(h is self.gui_handler for h in root_logger.handlers):
            self.gui_handler.setFormatter(gui_formatter)
            self.gui_handler.setLevel(logging.INFO)
            root_logger.addHandler(self.gui_handler)

        # Configure specific loggers (attach once)
        infra_logger = logging.getLogger("main_app.managers.infrastructure_manager")
        if not any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            and getattr(h, "baseFilename", None) == str(infra_log_file)
            for h in infra_logger.handlers
        ):
            infra_logger.addHandler(infra_handler)

        device_logger = logging.getLogger("main_app.managers.device_manager")
        if not any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            and getattr(h, "baseFilename", None) == str(device_log_file)
            for h in device_logger.handlers
        ):
            device_logger.addHandler(device_handler)

        # Log startup
        logging.info("PyConlyse logging system initialized")
        logging.info(f"Log directory: {self.log_dir}")
        logging.info(f"Main log: {main_log_file}")
        logging.info(f"Infrastructure log: {infra_log_file}")
        logging.info(f"Device log: {device_log_file}")

    def set_gui_callback(self, callback):
        """Set callback for GUI log updates."""
        self.gui_handler.set_gui_callback(callback)

    def get_recent_logs(self, level: str = "INFO", count: int = 100) -> list:
        """Get recent log entries (placeholder for future implementation)."""
        # This could read from log files and return recent entries
        return []


# Global logging instance
_logger_instance = None


def setup_pyconlyse_logging(log_dir: Optional[Path] = None) -> PyConlyseLogger:
    """Setup and return the global PyConlyse logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PyConlyseLogger(log_dir)
    return _logger_instance


def get_pyconlyse_logger() -> Optional[PyConlyseLogger]:
    """Get the current PyConlyse logger instance."""
    return _logger_instance
