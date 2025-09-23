#!/usr/bin/env python3
"""Async Connection Manager for PyConlyse

Handles all database connections, infrastructure startup, and device server management
in background threads to keep the GUI responsive.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Status of connections and operations."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class StatusUpdate:
    """Status update message."""

    component: str
    status: ConnectionStatus
    message: str
    timestamp: float
    details: Optional[Dict[str, Any]] = None


class AsyncConnectionManager:
    """Manages all background operations and connections."""

    def __init__(self, bin_path: Path):
        """Initialize the async connection manager.

        Args:
            bin_path: Path to the bin directory

        """
        self.bin_path = bin_path
        self.status_queue = queue.Queue()
        self.status_callbacks = []

        # Component status tracking
        self.component_status = {
            "database": ConnectionStatus.DISCONNECTED,
            "starter": ConnectionStatus.DISCONNECTED,
            "tango_connectivity": ConnectionStatus.DISCONNECTED,
        }

        # Thread management
        self.threads = {}
        self.shutdown_event = threading.Event()
        self.managers_initialized = False

        # Will be initialized in background
        self.infrastructure_mgr = None
        self.device_mgr = None

        logger.info("AsyncConnectionManager initialized")

    def add_status_callback(self, callback: Callable[[StatusUpdate], None]):
        """Add a callback for status updates."""
        self.status_callbacks.append(callback)

    def _notify_status_update(
        self,
        component: str,
        status: ConnectionStatus,
        message: str,
        details: Optional[Dict] = None,
    ):
        """Notify all callbacks of a status update."""
        self.component_status[component] = status
        update = StatusUpdate(component, status, message, time.time(), details)

        # Add to queue for GUI polling if needed
        try:
            self.status_queue.put_nowait(update)
        except queue.Full:
            pass  # Don't block if queue is full

        # Call all callbacks
        for callback in self.status_callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def start_background_initialization(self):
        """Start background initialization of all components."""
        if "init" not in self.threads:
            self.threads["init"] = threading.Thread(
                target=self._initialize_managers,
                name="ManagerInitialization",
                daemon=True,
            )
            self.threads["init"].start()
            logger.info("Started background manager initialization")

    def _initialize_managers(self):
        """Initialize managers in background thread."""
        try:
            logger.info("Initializing managers in background...")
            self._notify_status_update(
                "system",
                ConnectionStatus.STARTING,
                "Initializing PyConlyse managers...",
            )

            # Import managers (may take time due to Tango imports)
            from ..managers.device_manager import DeviceServerManager
            from ..managers.infrastructure_manager import TangoInfrastructureManager

            # Initialize managers
            self.infrastructure_mgr = TangoInfrastructureManager(self.bin_path)
            self.device_mgr = DeviceServerManager(self.bin_path)

            self.managers_initialized = True

            self._notify_status_update(
                "system",
                ConnectionStatus.CONNECTED,
                "Managers initialized successfully",
            )

            logger.info("Managers initialized successfully")

            # Start connection checking
            self.start_connection_monitoring()

        except Exception as e:
            logger.error(f"Failed to initialize managers: {e}")
            self._notify_status_update(
                "system", ConnectionStatus.ERROR, f"Manager initialization failed: {e}"
            )

    def start_connection_monitoring(self):
        """Start monitoring Tango database connection."""
        if "monitor" not in self.threads and self.managers_initialized:
            self.threads["monitor"] = threading.Thread(
                target=self._monitor_connections, name="ConnectionMonitor", daemon=True
            )
            self.threads["monitor"].start()
            logger.info("Started connection monitoring")

    def _monitor_connections(self):
        """Monitor database and infrastructure connections in background."""
        while not self.shutdown_event.is_set():
            try:
                if self.infrastructure_mgr:
                    # Check infrastructure status
                    status = self.infrastructure_mgr.get_status()

                    for component, state in status.items():
                        if component in self.component_status:
                            if state == "Running":
                                new_status = ConnectionStatus.RUNNING
                            elif state == "Connected":
                                new_status = ConnectionStatus.CONNECTED
                            elif state == "Not started":
                                new_status = ConnectionStatus.STOPPED
                            else:
                                new_status = ConnectionStatus.DISCONNECTED

                            # Only notify if status changed
                            if self.component_status[component] != new_status:
                                self._notify_status_update(
                                    component,
                                    new_status,
                                    f"{component.title()}: {state}",
                                )

                # Wait before next check
                self.shutdown_event.wait(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in connection monitoring: {e}")
                # Wait a bit longer on error
                self.shutdown_event.wait(10)

    def start_infrastructure_async(self, progress_callback: Optional[Callable] = None):
        """Start Tango infrastructure asynchronously."""
        if not self.managers_initialized:
            logger.warning("Managers not yet initialized, cannot start infrastructure")
            return False

        if "infra_start" in self.threads and self.threads["infra_start"].is_alive():
            logger.warning("Infrastructure startup already in progress")
            return False

        def progress_wrapper(message):
            logger.info(f"Infrastructure: {message}")
            self._notify_status_update(
                "infrastructure", ConnectionStatus.STARTING, message
            )
            if progress_callback:
                progress_callback(message)

        self.threads["infra_start"] = threading.Thread(
            target=self._start_infrastructure_worker,
            args=(progress_wrapper,),
            name="InfrastructureStart",
            daemon=True,
        )
        self.threads["infra_start"].start()

        logger.info("Started infrastructure startup in background")
        return True

    def _start_infrastructure_worker(self, progress_callback):
        """Worker thread for starting infrastructure."""
        try:
            logger.info("Starting Tango infrastructure in background...")
            self._notify_status_update(
                "infrastructure",
                ConnectionStatus.STARTING,
                "Starting Tango infrastructure...",
            )

            success = self.infrastructure_mgr.start_infrastructure(progress_callback)

            if success:
                self._notify_status_update(
                    "infrastructure",
                    ConnectionStatus.RUNNING,
                    "Infrastructure started successfully",
                )
                logger.info("Infrastructure started successfully")
            else:
                self._notify_status_update(
                    "infrastructure",
                    ConnectionStatus.ERROR,
                    "Failed to start infrastructure",
                )
                logger.error("Failed to start infrastructure")

        except Exception as e:
            logger.error(f"Error starting infrastructure: {e}")
            self._notify_status_update(
                "infrastructure",
                ConnectionStatus.ERROR,
                f"Infrastructure startup error: {e}",
            )

    def stop_infrastructure_async(self):
        """Stop Tango infrastructure asynchronously."""
        if not self.managers_initialized:
            return False

        if "infra_stop" in self.threads and self.threads["infra_stop"].is_alive():
            return False

        self.threads["infra_stop"] = threading.Thread(
            target=self._stop_infrastructure_worker,
            name="InfrastructureStop",
            daemon=True,
        )
        self.threads["infra_stop"].start()
        return True

    def _stop_infrastructure_worker(self):
        """Worker thread for stopping infrastructure."""
        try:
            logger.info("Stopping Tango infrastructure...")
            self._notify_status_update(
                "infrastructure",
                ConnectionStatus.STOPPING,
                "Stopping infrastructure...",
            )

            success = self.infrastructure_mgr.stop_infrastructure()

            if success:
                self._notify_status_update(
                    "infrastructure",
                    ConnectionStatus.STOPPED,
                    "Infrastructure stopped successfully",
                )
            else:
                self._notify_status_update(
                    "infrastructure",
                    ConnectionStatus.ERROR,
                    "Failed to stop infrastructure",
                )

        except Exception as e:
            logger.error(f"Error stopping infrastructure: {e}")
            self._notify_status_update(
                "infrastructure",
                ConnectionStatus.ERROR,
                f"Infrastructure stop error: {e}",
            )

    def start_device_server_async(
        self, device_type: str, instance: str, vis_type: str = "FULL"
    ):
        """Start device server asynchronously."""
        if not self.managers_initialized:
            return False

        thread_name = f"DeviceStart_{device_type}_{instance}"
        if thread_name in self.threads and self.threads[thread_name].is_alive():
            return False

        self.threads[thread_name] = threading.Thread(
            target=self._start_device_server_worker,
            args=(device_type, instance, vis_type),
            name=thread_name,
            daemon=True,
        )
        self.threads[thread_name].start()
        return True

    def _start_device_server_worker(
        self, device_type: str, instance: str, vis_type: str
    ):
        """Worker thread for starting device server."""
        try:
            server_name = f"{device_type}/{instance}"
            logger.info(f"Starting device server {server_name}...")

            self._notify_status_update(
                "devices", ConnectionStatus.STARTING, f"Starting {server_name}..."
            )

            success = self.device_mgr.start_deviceserver(
                device_type, instance, vis_type
            )

            if success:
                self._notify_status_update(
                    "devices",
                    ConnectionStatus.RUNNING,
                    f"Device server {server_name} started",
                )
                logger.info(f"Device server {server_name} started successfully")
            else:
                self._notify_status_update(
                    "devices", ConnectionStatus.ERROR, f"Failed to start {server_name}"
                )
                logger.error(f"Failed to start device server {server_name}")

        except Exception as e:
            logger.error(f"Error starting device server {device_type}/{instance}: {e}")
            self._notify_status_update(
                "devices", ConnectionStatus.ERROR, f"Device server error: {e}"
            )

    def get_status_update(self) -> Optional[StatusUpdate]:
        """Get next status update from queue (non-blocking)."""
        try:
            return self.status_queue.get_nowait()
        except queue.Empty:
            return None

    def get_all_status_updates(self) -> list:
        """Get all pending status updates."""
        updates = []
        while True:
            update = self.get_status_update()
            if update is None:
                break
            updates.append(update)
        return updates

    def get_current_status(self) -> Dict[str, ConnectionStatus]:
        """Get current status of all components."""
        return self.component_status.copy()

    def is_managers_ready(self) -> bool:
        """Check if managers are initialized and ready."""
        return self.managers_initialized

    def shutdown(self):
        """Shutdown all background threads."""
        logger.info("Shutting down async connection manager...")
        self.shutdown_event.set()

        # Wait for threads to finish
        for name, thread in self.threads.items():
            if thread.is_alive():
                logger.info(f"Waiting for {name} thread to finish...")
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"Thread {name} did not finish gracefully")

        logger.info("Async connection manager shutdown complete")
