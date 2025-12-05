"""Entry point for the standalone Treatment GUI project.

This module simply wires the repository root into ``sys.path`` and then
reuses the existing ``gui.Treatment.main`` entry point. This allows
running the Treatment GUI from a dedicated ``Treatment/`` project
without duplicating any of the core implementation.
"""

from __future__ import annotations

import sys
import logging
import platform
from pathlib import Path
from datetime import datetime


def _setup_logging() -> tuple[logging.Logger, Path]:
    """Configure comprehensive logging for the Treatment GUI application.
    
    This configures the ROOT logger so all modules in the application
    automatically inherit the configuration. All modules using 
    logging.getLogger(__name__) will write to both console and file.
    
    Returns:
        Tuple of (logger instance for main module, log file path).
    """
    # Ensure LOG directory exists
    log_dir = Path(__file__).resolve().parents[1] / "LOG"
    log_dir.mkdir(exist_ok=True)
    
    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"treatment_session_{timestamp}.log"
    
    # Get the ROOT logger (empty string means root)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers (in case of reinitialization)
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)-8s] %(name)-30s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler - captures ALL logs (DEBUG and above)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler - shows INFO and above (less verbose)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(console_handler)
    
    # Get logger for this module
    logger = logging.getLogger(__name__)
    
    # Log startup information
    logger.info("="*80)
    logger.info("Treatment GUI Application Starting")
    logger.info("="*80)
    logger.info(f"Log file: {log_file}")
    logger.info(f"Root logger configured - all modules will log to this file")
    logger.info(f"File log level: DEBUG (all messages)")
    logger.info(f"Console log level: INFO (less verbose)")
    logger.info("")
    logger.info("System Information:")
    logger.info(f"  Python version: {sys.version.split()[0]}")
    logger.info(f"  Python executable: {sys.executable}")
    logger.info(f"  Platform: {platform.platform()}")
    logger.info(f"  Architecture: {platform.machine()}")
    logger.info(f"  Processor: {platform.processor()}")
    logger.info(f"  Working directory: {Path.cwd()}")
    logger.info(f"  Script location: {Path(__file__).resolve()}")
    logger.info("")
    
    return logger, log_file


def _ensure_repo_root_on_sys_path(logger: logging.Logger) -> Path:
    """Return the repository root and make sure it is first on ``sys.path``.

    The repo root is assumed to be the parent directory of this
    ``Treatment`` package, i.e. ``.../pyconlyse``.
    
    Args:
        logger: Logger instance for logging operations.
    
    Returns:
        Path to the repository root.
    """
    logger.info("Setting up Python path...")
    logger.debug(f"Initial sys.path: {sys.path}")
    
    repo_root = Path(__file__).resolve().parents[1]
    repo_str = str(repo_root)
    
    logger.info(f"Repository root: {repo_root}")
    logger.info(f"Repository exists: {repo_root.exists()}")
    logger.info(f"Repository is directory: {repo_root.is_dir()}")
    
    if repo_str not in sys.path:
        logger.info(f"Adding repository root to sys.path: {repo_str}")
        sys.path.insert(0, repo_str)
    else:
        logger.info(f"Repository root already in sys.path at index {sys.path.index(repo_str)}")
    
    logger.debug(f"Final sys.path: {sys.path}")
    
    # Verify critical directories exist
    treatment_dir = repo_root / "Treatment"
    gui_dir = repo_root / "gui"
    
    logger.info(f"Treatment directory: {treatment_dir}")
    logger.info(f"Treatment directory exists: {treatment_dir.exists()}")
    logger.info(f"GUI directory: {gui_dir}")
    logger.info(f"GUI directory exists: {gui_dir.exists()}")
    
    return repo_root


def main() -> int:
    """Run the Treatment GUI using the forked implementation under ``Treatment``.
    
    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    logger = None
    
    try:
        # Setup logging first - this configures the root logger for ALL modules
        logger, log_file = _setup_logging()
        logger.info("Root logger initialized successfully")
        logger.info("All application modules will now log to the same file")
        
        # Setup Python path
        repo_root = _ensure_repo_root_on_sys_path(logger)
        logger.info("Python path configuration complete")
        
        # Import Treatment module
        logger.info("Importing Treatment.treatment_gui.Treatment module...")
        try:
            from Treatment.treatment_gui.Treatment import main as treatment_main
            logger.info("Treatment module imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import Treatment module: {e}")
            logger.exception("Import traceback:")
            raise
        
        # Check for required dependencies
        logger.info("Checking required dependencies...")
        required_modules = [
            'PyQt5',
            'numpy',
            'matplotlib',
            'h5py',
        ]
        
        for module_name in required_modules:
            try:
                __import__(module_name)
                logger.info(f"✓ {module_name} is available")
            except ImportError:
                logger.warning(f"✗ {module_name} is NOT available (may cause issues)")
        
        # Launch the GUI
        logger.info("="*80)
        logger.info("Launching Treatment GUI...")
        logger.info("="*80)
        
        treatment_main()
        
        logger.info("="*80)
        logger.info("Treatment GUI closed normally")
        logger.info("="*80)
        return 0
        
    except KeyboardInterrupt:
        if logger:
            logger.warning("Application interrupted by user (Ctrl+C)")
        return 130  # Standard exit code for Ctrl+C
        
    except Exception as e:
        if logger:
            logger.error("="*80)
            logger.error("FATAL ERROR: Application crashed")
            logger.error("="*80)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {e}")
            logger.exception("Full traceback:")
        else:
            # Fallback if logger not initialized
            print(f"FATAL ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        return 1
        
    finally:
        if logger:
            logger.info(f"Application exiting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    raise SystemExit(main())
