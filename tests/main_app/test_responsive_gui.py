#!/usr/bin/env python3
"""Test version focusing on GUI responsiveness."""

import logging
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Add parent directory to path for imports
main_app_path = Path(__file__).parent
sys.path.insert(0, str(main_app_path.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleLogViewer(QTextEdit):
    """Simple log viewer without complex formatting."""

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumHeight(200)  # Limit height

    def add_log(self, message: str):
        """Add a simple log message."""
        self.append(message)
        # Keep only last 50 lines
        if self.document().blockCount() > 50:
            cursor = self.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 10)
            cursor.removeSelectedText()


class ResponsiveSignals(QObject):
    """Thread-safe signals for the responsive GUI."""

    log_message = pyqtSignal(str)


class ResponsiveMainWindow(QMainWindow):
    """Highly responsive main window."""

    def __init__(self):
        super().__init__()
        self.signals = ResponsiveSignals()
        self.signals.log_message.connect(self.on_log_message)

        self.setup_ui()
        logger.info("Responsive GUI initialized")

    def setup_ui(self):
        """Setup minimal UI for maximum responsiveness."""
        self.setWindowTitle("PyConlyse v2.0 - Responsive Test")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Status label
        self.status_label = QLabel("System ready - GUI is responsive")
        self.status_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 10px;"
        )
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.test_btn = QPushButton("🚀 Test Operation")
        self.test_btn.clicked.connect(self.test_operation)
        self.test_btn.setStyleSheet("QPushButton { font-size: 12px; padding: 8px; }")
        button_layout.addWidget(self.test_btn)

        self.log_btn = QPushButton("📝 Add Log Entry")
        self.log_btn.clicked.connect(self.add_test_log)
        button_layout.addWidget(self.log_btn)

        self.clear_btn = QPushButton("🗑️ Clear Logs")
        self.clear_btn.clicked.connect(self.clear_logs)
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        # Simple log viewer
        log_label = QLabel("System Logs:")
        log_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(log_label)

        self.log_viewer = SimpleLogViewer()
        layout.addWidget(self.log_viewer)

        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("GUI ready and responsive")

        # Add initial log
        self.add_log("GUI initialized successfully")

    @pyqtSlot(str)
    def on_log_message(self, message: str):
        """Handle log message from any thread."""
        self.log_viewer.add_log(message)

    def add_log(self, message: str):
        """Add log message (thread-safe)."""
        self.signals.log_message.emit(f"[{self.get_timestamp()}] {message}")

    def get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().strftime("%H:%M:%S")

    def test_operation(self):
        """Test operation that doesn't block GUI."""
        self.statusBar.showMessage("Running test operation...")
        self.add_log("Test operation started")

        # Simulate work without blocking
        QTimer.singleShot(100, lambda: self.complete_test_operation())

    def complete_test_operation(self):
        """Complete test operation."""
        self.add_log("Test operation completed successfully")
        self.statusBar.showMessage("Test operation completed - GUI remains responsive")

    def add_test_log(self):
        """Add a test log entry."""
        self.add_log("This is a test log entry to verify responsiveness")

    def clear_logs(self):
        """Clear all logs."""
        self.log_viewer.clear()
        self.add_log("Logs cleared")
        self.statusBar.showMessage("Logs cleared successfully")


def main():
    """Main entry point for responsive GUI test."""
    logger.info("Starting responsive GUI test...")

    app = QApplication(sys.argv)
    app.setApplicationName("PyConlyse Responsive Test")

    # Create and show window
    window = ResponsiveMainWindow()
    window.show()

    logger.info("Responsive GUI window shown successfully!")

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
