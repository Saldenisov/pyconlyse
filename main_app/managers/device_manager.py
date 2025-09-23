#!/usr/bin/env python3
"""Device Server Manager

Manages the lifecycle (start/stop/restart) of DeviceServers and provides
status monitoring capabilities.
"""

import logging
import subprocess
from pathlib import Path
from time import sleep
from typing import Dict, Optional

from ..core.config import DEVICE_SERVER_CONFIGS

logger = logging.getLogger(__name__)


class DeviceServerManager:
    """Manages DeviceServer lifecycle operations."""

    def __init__(self, bin_path: Optional[Path] = None):
        """Initialize the device server manager.

        Args:
            bin_path: Path to the bin directory. If None, uses current file's parent.

        """
        self.device_configs = DEVICE_SERVER_CONFIGS
        self.running_servers = {}
        self.bin_path = bin_path or Path(__file__).parent

    def start_deviceserver(
        self, device_type: str, instance: str, vis_type: str = "FULL"
    ) -> bool:
        """Start a DeviceServer using the unified startup script.

        Args:
            device_type: Type of device server (e.g., "BASLER", "STANDA")
            instance: Instance name (e.g., "V0", "Cam1")
            vis_type: Visualization type ("FULL", "MINIMAL", etc.)

        Returns:
            bool: True if DeviceServer started successfully

        """
        try:
            if device_type not in self.device_configs:
                logger.error(f"Unknown device type: {device_type}")
                return False

            # Check if server is already running
            server_key = f"{device_type}_{instance}"
            if server_key in self.running_servers:
                existing = self.running_servers[server_key]
                if existing["process"] and existing["process"].poll() is None:
                    logger.warning(
                        f"DeviceServer {device_type}/{instance} is already running"
                    )
                    return True

            script_path = self.bin_path / "start_deviceserver.cmd"
            if not script_path.exists():
                logger.error("DeviceServer startup script not found!")
                return False

            cmd = ["cmd.exe", "/c", str(script_path), device_type, instance, vis_type]
            logger.info(f"Starting DeviceServer: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                cwd=str(self.bin_path),
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

            # Store server information
            self.running_servers[server_key] = {
                "process": process,
                "device_type": device_type,
                "instance": instance,
                "vis_type": vis_type,
            }

            logger.info(f"DeviceServer {device_type}/{instance} started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start DeviceServer {device_type}/{instance}: {e}")
            return False

    def stop_deviceserver(self, device_type: str, instance: str) -> bool:
        """Stop a running DeviceServer.

        Args:
            device_type: Type of device server
            instance: Instance name

        Returns:
            bool: True if DeviceServer was stopped successfully

        """
        try:
            server_key = f"{device_type}_{instance}"

            if server_key not in self.running_servers:
                logger.warning(
                    f"DeviceServer {device_type}/{instance} not found in running servers"
                )
                return False

            server_info = self.running_servers[server_key]
            process = server_info["process"]

            if not process:
                logger.warning(
                    f"No process found for DeviceServer {device_type}/{instance}"
                )
                del self.running_servers[server_key]
                return False

            if process.poll() is not None:
                logger.info(
                    f"DeviceServer {device_type}/{instance} was already stopped"
                )
                del self.running_servers[server_key]
                return True

            # Attempt graceful termination
            logger.info(f"Stopping DeviceServer {device_type}/{instance}")
            process.terminate()

            # Wait for graceful shutdown
            try:
                process.wait(timeout=5.0)
                logger.info(f"DeviceServer {device_type}/{instance} stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if needed
                logger.warning(f"Force killing DeviceServer {device_type}/{instance}")
                process.kill()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    logger.error(
                        f"Failed to kill DeviceServer {device_type}/{instance}"
                    )
                    return False

            del self.running_servers[server_key]
            logger.info(f"DeviceServer {device_type}/{instance} stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to stop DeviceServer {device_type}/{instance}: {e}")
            return False

    def restart_deviceserver(
        self, device_type: str, instance: str, vis_type: str = "FULL"
    ) -> bool:
        """Restart a DeviceServer (stop then start).

        Args:
            device_type: Type of device server
            instance: Instance name
            vis_type: Visualization type

        Returns:
            bool: True if DeviceServer was restarted successfully

        """
        logger.info(f"Restarting DeviceServer {device_type}/{instance}")

        # Stop the server first
        stop_success = self.stop_deviceserver(device_type, instance)
        if not stop_success:
            logger.warning(
                f"Failed to stop DeviceServer {device_type}/{instance}, trying to start anyway"
            )

        # Wait a bit before restarting
        sleep(2)

        # Start the server
        start_success = self.start_deviceserver(device_type, instance, vis_type)

        if start_success:
            logger.info(f"DeviceServer {device_type}/{instance} restarted successfully")
        else:
            logger.error(f"Failed to restart DeviceServer {device_type}/{instance}")

        return start_success

    def get_running_servers(self) -> Dict[str, Dict]:
        """Get status information for all running DeviceServers.

        Returns:
            Dict mapping server keys to server information with status

        """
        status = {}

        # Clean up dead processes first
        dead_servers = []
        for server_key, server_info in self.running_servers.items():
            process = server_info["process"]
            if not process or process.poll() is not None:
                dead_servers.append(server_key)

        for server_key in dead_servers:
            del self.running_servers[server_key]

        # Build status dict
        for server_key, server_info in self.running_servers.items():
            process = server_info["process"]
            if process and process.poll() is None:
                status[server_key] = {**server_info, "status": "Running"}
            else:
                status[server_key] = {
                    **server_info,
                    "status": f"Stopped (exit code: {process.poll() if process else 'N/A'})",
                }

        return status

    def stop_all_servers(self) -> int:
        """Stop all running DeviceServers.

        Returns:
            int: Number of servers that were stopped

        """
        running_servers = list(self.running_servers.keys())
        stopped_count = 0

        for server_key in running_servers:
            server_info = self.running_servers[server_key]
            device_type = server_info["device_type"]
            instance = server_info["instance"]

            if self.stop_deviceserver(device_type, instance):
                stopped_count += 1

        logger.info(f"Stopped {stopped_count} DeviceServers")
        return stopped_count

    def start_all_configured_servers(self, vis_type: str = "FULL") -> int:
        """Start all configured DeviceServers.

        Args:
            vis_type: Visualization type to use for all servers

        Returns:
            int: Number of servers that were started

        """
        started_count = 0

        for device_type, config in self.device_configs.items():
            for instance in config["instances"]:
                if self.start_deviceserver(device_type, instance, vis_type):
                    started_count += 1

        logger.info(f"Started {started_count} DeviceServers")
        return started_count

    def get_server_status(self, device_type: str, instance: str) -> Optional[str]:
        """Get the status of a specific DeviceServer.

        Args:
            device_type: Type of device server
            instance: Instance name

        Returns:
            Optional[str]: Status string, or None if server not found

        """
        server_key = f"{device_type}_{instance}"

        if server_key not in self.running_servers:
            return "Not started"

        server_info = self.running_servers[server_key]
        process = server_info["process"]

        if not process:
            return "No process"

        if process.poll() is None:
            return "Running"
        return f"Stopped (exit code: {process.poll()})"

    def is_server_running(self, device_type: str, instance: str) -> bool:
        """Check if a specific DeviceServer is currently running.

        Args:
            device_type: Type of device server
            instance: Instance name

        Returns:
            bool: True if server is running

        """
        server_key = f"{device_type}_{instance}"

        if server_key not in self.running_servers:
            return False

        server_info = self.running_servers[server_key]
        process = server_info["process"]

        return process is not None and process.poll() is None

    def get_available_device_types(self) -> Dict[str, Dict]:
        """Get all available device types and their configurations.

        Returns:
            Dict mapping device types to their configurations

        """
        return self.device_configs.copy()

    def cleanup(self):
        """Clean up resources and stop all servers."""
        logger.info("Cleaning up DeviceServerManager")
        self.stop_all_servers()
