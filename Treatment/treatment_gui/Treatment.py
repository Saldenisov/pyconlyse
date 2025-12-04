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

    This replaces the original dependency on ``logs_pack.initialize_logger``
    so that the forked GUI can run without the external ``logs_pack``
    package being installed.
    """

    logger = logging.getLogger("Treatment")
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

    data_folder = get_data_folder()
    logger.info(f"Using data folder: {data_folder}")

    app = QApplication(sys.argv)

    # Set an application-wide icon so the OS window/taskbar uses it even
    # before the main window is shown.
    icon_path = app_folder / "Treatment" / "resources" / "sumo2.svg"
    logger.info(f"Icon path resolved to: {icon_path}")
    if icon_path.is_file():
        logger.info("Icon file found; setting application icon.")
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        logger.warning("Icon file not found; using default application icon.")

    TreatmentController(TreatmentModel(app_folder, data_folder=data_folder))

    app.exec_()


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
