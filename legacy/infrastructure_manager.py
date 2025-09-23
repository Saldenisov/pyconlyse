#!/usr/bin/env python3
"""Tango Infrastructure Manager

Handles startup, monitoring, and management of Tango infrastructure components:
- Database server
- Starter service
- Astor GUI

Features timeout protection and proper error handling.
"""

import concurrent.futures
import logging
import os
import socket
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional

from config import INFRASTRUCTURE_START_ORDER, INFRASTRUCTURE_STOP_ORDER, Timeouts
from tango import Database

logger = logging.getLogger(__name__)


class TangoInfrastructureManager:
    """Manages Tango infrastructure startup and monitoring with timeout protection."""

    def __init__(self, bin_path: Optional[Path] = None):
        """Initialize the infrastructure manager.

        Args:
            bin_path: Path to the bin directory. If None, uses current file's parent.

        """
        self.processes = {}
        self.is_running = False
        self.bin_path = bin_path or Path(__file__).parent

    def start_infrastructure(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Start the complete Tango infrastructure.

        Args:
            progress_callback: Optional callback to report progress messages

        Returns:
            bool: True if startup was successful, False otherwise

        """
        try:
            if self.is_running:
                logger.warning("Tango infrastructure is already running")
                return True

            success = self._start_database_and_starter(progress_callback)
            if success:
                self.is_running = True
                logger.info("Tango infrastructure startup completed successfully")
            return success

        except Exception as e:
            logger.error(f"Failed to start Tango infrastructure: {e}")
            return False

    def _start_database_and_starter(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Start Database and Starter processes with timeout protection.

        Args:
            progress_callback: Optional callback to report progress

        Returns:
            bool: True if both components started successfully

        """
        try:
            tango_root = os.environ.get("TANGO_ROOT")
            if not tango_root:
                logger.error("TANGO_ROOT environment variable not set!")
                return False

            # Step 1: Start Tango Database
            if progress_callback:
                progress_callback("Starting Tango Database...")

            if not self._start_database(tango_root):
                return False

            # Wait for database to initialize
            import time

            time.sleep(5)

            # Step 2: Start Tango Starter
            if progress_callback:
                progress_callback("Starting Tango Starter...")

            if not self._start_starter(tango_root):
                return False

            # Step 3: Start Astor (optional)
            if progress_callback:
                progress_callback("Starting Astor...")

            self._start_astor(tango_root)  # Don't fail if Astor doesn't start

            if progress_callback:
                progress_callback("Tango infrastructure started successfully")

            logger.info("Successfully started Tango Database, Starter, and Astor")
            return True

        except Exception as e:
            logger.error(f"Failed to start database and starter: {e}")
            return False

    def _start_database(self, tango_root: str) -> bool:
        """Start the Tango Database process.

        Args:
            tango_root: Path to TANGO_ROOT directory

        Returns:
            bool: True if database started successfully

        """
        try:
            db_cmd = ["cmd", "/c", f"{tango_root}\\bin\\start-db.bat"]
            logger.info(f"Starting Tango Database: {' '.join(db_cmd)}")

            db_process = subprocess.Popen(
                db_cmd,
                cwd=str(self.bin_path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait briefly to see if process starts successfully
            try:
                db_process.wait(timeout=Timeouts.SUBPROCESS_START)
                # If we get here, process exited quickly (likely error)
                if db_process.returncode != 0:
                    logger.warning(
                        f"Database process exited with code {db_process.returncode}"
                    )
            except subprocess.TimeoutExpired:
                # Process is still running, which is expected
                logger.info("Database process started and running")

            self.processes["database"] = db_process
            return True

        except Exception as e:
            logger.error(f"Failed to start database process: {e}")
            return False

    def _start_starter(self, tango_root: str) -> bool:
        """Start the Tango Starter process.

        Args:
            tango_root: Path to TANGO_ROOT directory

        Returns:
            bool: True if starter started successfully

        """
        try:
            hostname = socket.gethostname().lower()
            starter_cmd = [f"{tango_root}\\bin\\Starter.exe", hostname]
            logger.info(f"Starting Tango Starter: {' '.join(starter_cmd)}")

            starter_process = subprocess.Popen(
                starter_cmd,
                cwd=str(self.bin_path),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait briefly to see if process starts successfully
            try:
                starter_process.wait(timeout=Timeouts.SUBPROCESS_START)
                # If we get here, process exited quickly (likely error)
                if starter_process.returncode != 0:
                    logger.warning(
                        f"Starter process exited with code {starter_process.returncode}"
                    )
            except subprocess.TimeoutExpired:
                # Process is still running, which is expected
                logger.info("Starter process started and running")

            self.processes["starter"] = starter_process
            return True

        except Exception as e:
            logger.error(f"Failed to start starter process: {e}")
            return False

    def _start_astor(self, tango_root: str) -> bool:
        """Start the Astor GUI (optional component).

        Args:
            tango_root: Path to TANGO_ROOT directory

        Returns:
            bool: True if astor started successfully

        """
        try:
            import time

            time.sleep(3)  # Wait for Starter to initialize

            astor_cmd = ["cmd", "/c", f"{tango_root}\\bin\\start-astor.bat"]
            logger.info(f"Starting Astor: {' '.join(astor_cmd)}")

            astor_process = subprocess.Popen(
                astor_cmd,
                cwd=str(self.bin_path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.processes["astor"] = astor_process
            logger.info("Astor GUI started")
            return True

        except Exception as e:
            logger.warning(f"Failed to start Astor (non-critical): {e}")
            return False

    def stop_infrastructure(self) -> bool:
        """Stop the complete Tango infrastructure.

        Returns:
            bool: True if shutdown was successful

        """
        try:
            stopped_components = []

            # Stop components in reverse order
            for component in INFRASTRUCTURE_STOP_ORDER:
                if self._stop_component(component):
                    stopped_components.append(component)

            # Clear all processes
            self.processes.clear()
            self.is_running = False

            logger.info(
                f"Tango infrastructure stopped. Components: {', '.join(stopped_components)}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to stop Tango infrastructure: {e}")
            return False

    def _stop_component(self, component: str) -> bool:
        """Stop a specific infrastructure component.

        Args:
            component: Name of the component to stop

        Returns:
            bool: True if component was stopped

        """
        try:
            if component not in self.processes:
                logger.info(f"{component} was not started by this manager")
                return False

            process = self.processes[component]
            if not process or process.poll() is not None:
                logger.info(f"{component} process was already stopped")
                return True

            logger.info(f"Terminating {component} process")
            process.terminate()

            # Wait a bit for graceful shutdown
            import time

            time.sleep(2)

            # Force kill if still running
            if process.poll() is None:
                logger.info(f"Force killing {component} process")
                process.kill()

            return True

        except Exception as e:
            logger.warning(f"Error stopping {component}: {e}")
            return False

    def check_tango_running(self, timeout: float = None) -> bool:
        """Check if Tango database is accessible with timeout protection.

        Args:
            timeout: Connection timeout in seconds. Uses default if None.

        Returns:
            bool: True if Tango database is accessible

        """
        if timeout is None:
            timeout = Timeouts.DATABASE_CONNECTION

        def _check_db():
            try:
                db = Database()
                db.get_info()
                return True
            except Exception as e:
                logger.debug(f"Tango DB not accessible: {e}")
                return False

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_check_db)
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.debug(f"Tango DB check timed out after {timeout}s")
            return False
        except Exception as e:
            logger.debug(f"Tango DB check failed: {e}")
            return False

    def get_status(self) -> Dict[str, str]:
        """Get status of all infrastructure components.

        Returns:
            Dict mapping component names to their status strings

        """
        status = {}

        for component in INFRASTRUCTURE_START_ORDER:
            if component in self.processes:
                process = self.processes[component]
                if process:
                    if process.poll() is None:
                        status[component] = "Running"
                    else:
                        status[component] = f"Stopped (exit code: {process.poll()})"
                else:
                    status[component] = "Not started"
            else:
                status[component] = "Not started"

        # Add overall connectivity status
        status["tango_connectivity"] = (
            "Connected" if self.check_tango_running(timeout=2.0) else "Disconnected"
        )

        return status

    def check_starter_running(self) -> bool:
        """Check if Tango Starter process is running on the system.

        Returns:
            bool: True if Starter.exe process is found

        """
        try:
            result = subprocess.run(
                ["tasklist", "/fi", "imagename eq Starter.exe"],
                check=False,
                capture_output=True,
                text=True,
                shell=True,
                timeout=5.0,
            )
            return "Starter.exe" in result.stdout
        except Exception as e:
            logger.debug(f"Error checking Starter process: {e}")
            return False
