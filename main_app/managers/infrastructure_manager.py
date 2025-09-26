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
from typing import Callable, Dict, List, Optional

# PyTango may not always be available or initialized at import time
try:
    from tango import Database  # type: ignore
except Exception:  # noqa: BLE001 - broad to avoid breaking runtime when tango missing
    Database = None  # type: ignore

from ..core.config import (
    INFRASTRUCTURE_STOP_ORDER,
    OFFLINE_MODE,
    SERVER_CLASS_BY_TYPE,
    Timeouts,
)

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
        # Cache for admin device discovery to avoid pounding the DB
        self._admin_devices_cache: Dict[str, List[str]] = {"devices": []}  # type: ignore[var-annotated]
        self._admin_devices_cache_ts: float = 0.0

    def start_infrastructure(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Start the complete Tango infrastructure.
        if OFFLINE_MODE:
            logger.info("OFFLINE_MODE: start_infrastructure skipped")
            return False

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

            # Observer-only: do not auto-start Astor here
            if progress_callback:
                progress_callback("Tango infrastructure started successfully")

            logger.info("Successfully started Tango Database and Starter")
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
            db_cmd = ["cmd.exe", "/c", f"{tango_root}\\bin\\start-db.bat"]
            logger.info(f"Starting Tango Database: {' '.join(db_cmd)}")

            db_process = subprocess.Popen(
                db_cmd,
                cwd=str(self.bin_path),
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
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
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
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

            astor_cmd = ["cmd.exe", "/c", f"{tango_root}\\bin\\start-astor.bat"]
            logger.info(f"Starting Astor: {' '.join(astor_cmd)}")

            astor_process = subprocess.Popen(
                astor_cmd,
                cwd=str(self.bin_path),
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

            self.processes["astor"] = astor_process
            logger.info("Astor GUI started")
            return True

        except Exception as e:
            logger.warning(f"Failed to start Astor (non-critical): {e}")
            return False

    def stop_infrastructure(self) -> bool:
        """Stop the complete Tango infrastructure.
        if OFFLINE_MODE:
            logger.info("OFFLINE_MODE: stop_infrastructure no-op")
            return True

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
        if OFFLINE_MODE:
            return False
        if timeout is None:
            timeout = Timeouts.DATABASE_CONNECTION

        # Determine host:port from environment (default to localhost:10000)
        tango_host_env = os.environ.get("TANGO_HOST", "")
        host = "127.0.0.1"
        port = 10000
        if tango_host_env:
            try:
                parts = tango_host_env.split(":")
                host = parts[0].strip() or host
                if len(parts) > 1 and parts[1].strip().isdigit():
                    port = int(parts[1].strip())
            except Exception:
                logger.debug(
                    f"Unable to parse TANGO_HOST='{tango_host_env}', using default {host}:{port}"
                )
        else:
            logger.debug("TANGO_HOST not set; using default 127.0.0.1:10000")

        # Fast TCP connectivity probe first (non-PyTango)
        try:
            with socket.create_connection((host, port), timeout=timeout):
                tcp_ok = True
        except Exception as e:
            logger.debug(f"TCP probe to {host}:{port} failed: {e}")
            tcp_ok = False

        if not tcp_ok:
            return False

        # If PyTango is available, verify database responds
        if Database is None:
            logger.debug(
                "PyTango Database not available; treating TCP reachability as Connected"
            )
            return True

        def _check_db():
            try:
                db = Database()
                db.get_info()  # should raise if DB unreachable/misconfigured
                return True
            except Exception as e:
                logger.debug(f"PyTango Database.get_info() failed: {e}")
                return False

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_check_db)
                ok = future.result(timeout=timeout)
                # Consider reachable if TCP is OK even when get_info has hiccups
                return ok or tcp_ok
        except concurrent.futures.TimeoutError:
            logger.debug(
                f"Tango DB check timed out after {timeout}s; falling back to TCP result {tcp_ok}"
            )
            return tcp_ok
        except Exception as e:
            logger.debug(
                f"Tango DB check failed: {e}; falling back to TCP result {tcp_ok}"
            )
            return tcp_ok

    def get_status(self) -> Dict[str, str]:
        """Get status of all infrastructure components (observer-friendly).

        Returns:
            Dict mapping component names to their status strings

        """
        status: Dict[str, str] = {}

        if OFFLINE_MODE:
            status["database"] = "Not started"
            status["starter"] = "Not started"
            status["tango_connectivity"] = "Disconnected"
            return status

        # Database: consider 'Running' if DB reachable, regardless of who started it
        db_connected = self.check_tango_running(timeout=Timeouts.DATABASE_CONNECTION)
        status["database"] = "Running" if db_connected else "Not started"

        # Starter: check OS process or admin devices regardless of who started it
        try:
            if self.check_starter_running():
                status["starter"] = "Running"
            else:
                # Fallback: probe admin devices; if any respond with an active state, consider running
                starters = self.get_starters_status()
                any_running = any(
                    str(s.get("state", "")).upper()
                    in ("ON", "MOVING", "STANDBY", "RUNNING")
                    for s in starters
                )
                status["starter"] = "Running" if any_running else "Not started"
        except Exception:
            status["starter"] = "Not started"

        # Overall connectivity
        status["tango_connectivity"] = "Connected" if db_connected else "Disconnected"

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
                shell=False,
                timeout=5.0,
            )
            return "Starter.exe" in result.stdout
        except Exception as e:
            logger.debug(f"Error checking Starter process: {e}")
            return False

    def _list_admin_devices(self, max_age: float = 5.0) -> List[str]:
        """List all admin devices (dserver/*) from the Tango DB with simple caching.

        Args:
            max_age: seconds to consider cache valid

        """
        try:
            import time

            if Database is None:
                return []
            # Use cache
            if (
                time.time() - self._admin_devices_cache_ts
            ) < max_age and self._admin_devices_cache.get("devices"):
                return list(self._admin_devices_cache.get("devices", []))
            db = Database()
            all_devs = db.get_device_exported("dserver/*")
            devs = list(all_devs)
            # Update cache
            self._admin_devices_cache = {"devices": devs}
            self._admin_devices_cache_ts = time.time()
            return devs
        except Exception as e:
            logger.debug(f"Failed to list admin devices: {e}")
            return []

    def _find_admin_device(self, server_class: str, instance: str) -> Optional[str]:
        """Find canonical admin device name from DB for a given server class/instance.

        Matching is case-insensitive on both server_class and instance.
        """
        try:
            # Normalize: map logical device type to server class name if needed
            mapped_class = SERVER_CLASS_BY_TYPE.get(server_class, server_class)
            candidates = self._list_admin_devices()
            sc_l = (mapped_class or "").lower()
            inst_l = (instance or "").lower()
            for dn in candidates:
                try:
                    _, srv, inst = dn.split("/", 2)
                except ValueError:
                    continue
                if srv.lower() == sc_l and inst.lower() == inst_l:
                    return dn
            return None
        except Exception as e:
            logger.debug(
                f"_find_admin_device failed for {server_class}/{instance}: {e}"
            )
            return None

    def get_starter_devices(self) -> List[str]:
        """Return a list of Starter admin device names (e.g., 'tango/admin/<host>').

        Returns:
            List[str]: Starter device names discovered via Tango DB. Empty if unavailable.

        """
        devices: List[str] = []
        if OFFLINE_MODE:
            return devices
        try:
            if Database is None:
                logger.debug(
                    "PyTango Database not available; cannot list starter devices"
                )
                return devices
            db = Database()
            # Get all exported devices and filter admin devices (Starter)
            all_devs = db.get_device_exported("*")
            devices = [dev for dev in all_devs if dev.startswith("tango/admin/")]
        except Exception as e:
            logger.debug(f"Failed to get starter devices: {e}")
        return devices

    def get_starters_status(self) -> List[Dict[str, str]]:
        """Return status info for discovered Starter devices.

        Each entry includes: { 'name': device_name, 'state': state_str }
        """
        starters: List[Dict[str, str]] = []
        if OFFLINE_MODE:
            return starters
        try:
            device_names = self.get_starter_devices()
            if not device_names:
                return starters
            try:
                from taurus import Device  # type: ignore
            except Exception:
                # If Taurus is not available, just return names without state
                for dn in device_names:
                    starters.append({"name": dn, "state": "Unknown"})
                return starters

            for dn in device_names:
                state_str = "Unknown"
                try:
                    dev = Device(dn)
                    st = dev.state()
                    # Map to simple string
                    state_str = str(st)
                except Exception as e:
                    logger.debug(f"Could not read state of {dn}: {e}")
                    state_str = "DOWN"
                starters.append({"name": dn, "state": state_str})
        except Exception as e:
            logger.debug(f"Failed to collect starters status: {e}")
        return starters

    def get_deviceserver_status(
        self, server_class: str, instance: str, timeout: Optional[float] = None
    ) -> str:
        """Check a specific DeviceServer status using its admin device.

        Returns one of: 'Running', 'Stopped', 'Error', 'Unknown'.
        """
        try:
            if OFFLINE_MODE:
                return "Unknown"
            if Database is None:
                return "Unknown"
            if timeout is None:
                timeout = Timeouts.DATABASE_CONNECTION
            try:
                from taurus import Device  # type: ignore
            except Exception:
                return "Unknown"

            # Resolve canonical admin device from DB instead of constructing it
            admin_name = self._find_admin_device(server_class, instance)
            if not admin_name:
                logger.debug(
                    f"Admin device not found in DB for {server_class}/{instance}"
                )
                return "Unknown"
            try:
                dev = Device(admin_name)
                st = dev.state()
                # Interpret state using string values to avoid PyTango DevState dependency
                st_str = str(st).upper()
                if st_str in ("ON", "RUNNING", "STANDBY", "MOVING"):
                    return "Running"
                if st_str in ("OFF", "INIT"):
                    return "Stopped"
                if st_str in ("FAULT", "ALARM", "UNKNOWN"):
                    return "Error"
                return st_str
            except Exception as e:
                # If we cannot contact the admin device, status is unknown (could be down or unreachable)
                logger.debug(f"Admin device check failed for {admin_name}: {e}")
                return "Unknown"
        except Exception as e:
            logger.debug(
                f"get_deviceserver_status error for {server_class}/{instance}: {e}"
            )
            return "Unknown"

    def get_deviceservers_status_map(
        self, device_configs: Dict[str, Dict]
    ) -> Dict[str, str]:
        """Get status for all configured DeviceServers.

        Args:
            device_configs: mapping of device_type -> { 'instances': [...] }

        Returns:
            Dict[str, str]: mapping 'ServerClass/Instance' -> status string

        """
        status_map: Dict[str, str] = {}
        try:
            pairs: List[tuple] = []
            for server_class, cfg in device_configs.items():
                for instance in cfg.get("instances", []):
                    pairs.append((server_class, instance))

            if not pairs:
                return status_map

            # Parallelize with a small pool
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(8, len(pairs))
            ) as ex:
                future_to_key = {}
                for sc, inst in pairs:
                    # Try resolving exact admin device name for better logging and correctness
                    admin_name = self._find_admin_device(sc, inst)
                    # Ensure we query with proper server class mapping
                    sc_query = SERVER_CLASS_BY_TYPE.get(sc, sc)
                    fut = ex.submit(self.get_deviceserver_status, sc_query, inst)
                    key = admin_name if admin_name else f"{sc}/{inst}"
                    future_to_key[fut] = key
                for fut, key in future_to_key.items():
                    try:
                        status_map[key] = fut.result(
                            timeout=Timeouts.DATABASE_CONNECTION + 0.5
                        )
                    except Exception as e:
                        logger.debug(f"Status check timeout/err for {key}: {e}")
                        status_map[key] = "Unknown"
        except Exception as e:
            logger.debug(f"get_deviceservers_status_map failed: {e}")
        return status_map

    def list_admin_servers_with_devices(
        self, max_age: float = 5.0
    ) -> List[Dict[str, object]]:
        """Build a DB-driven view of admin servers and their controlled devices.

        Returns:
            List of dicts: {
                'admin': 'dserver/DS_Netio_pdu/3_SD1',
                'server_class': 'DS_Netio_pdu',
                'instance': '3_SD1',
                'status': 'Running'|'Stopped'|'Error'|'Unknown',
                'devices': ['manip/sd1/pdu_sd1', ...]
            }

        """
        servers: List[Dict[str, object]] = []
        if OFFLINE_MODE:
            return servers
        try:
            admin_devs = self._list_admin_devices(max_age=max_age)
            if not admin_devs:
                return servers

            # Group by (server_class, instance)
            parsed = []
            for dn in admin_devs:
                try:
                    _, srv, inst = dn.split("/", 2)
                except ValueError:
                    continue
                parsed.append((dn, srv, inst))

            # Parallelize status checks and device collection
            def _collect(entry):
                admin_name, srv, inst = entry
                status = self.get_deviceserver_status(srv, inst)
                devs = self._list_devices_for_server(srv, inst)
                return {
                    "admin": admin_name,
                    "server_class": srv,
                    "instance": inst,
                    "status": status,
                    "devices": devs,
                }

            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(8, len(parsed))
            ) as ex:
                futs = [ex.submit(_collect, e) for e in parsed]
                for fut in futs:
                    try:
                        servers.append(
                            fut.result(timeout=Timeouts.DATABASE_CONNECTION + 1.0)
                        )
                    except Exception as e:
                        logger.debug(f"admin collection failed: {e}")
            return servers
        except Exception as e:
            logger.debug(f"list_admin_servers_with_devices failed: {e}")
            return servers

    def _list_devices_for_server(self, server_class: str, instance: str) -> List[str]:
        """Return list of device names controlled by a given server class/instance.

        Strategy:
            - Query DB for devices of class server_class
            - Filter by DeviceProxy.info().server_name or .server_id matching 'server_class/instance'
        """
        devices: List[str] = []
        if OFFLINE_MODE:
            return devices
        try:
            from tango import Database  # type: ignore

            db = Database()
            # Normalize class in case user passes logical type
            srv_class = SERVER_CLASS_BY_TYPE.get(server_class, server_class)
            try:
                class_devs = db.get_device_exported_for_class(srv_class)
            except Exception:
                # Fallback: broad scan if class-specific fails
                class_devs = [
                    d for d in db.get_device_exported("*") if d.count("/") == 2
                ]

            target = f"{srv_class}/{instance}".lower()

            import concurrent.futures

            def _match(dev_name: str) -> str:
                try:
                    db_local = Database()
                    info = db_local.get_device_info(dev_name)
                    # Try common attribute names for server id/name
                    server_name = getattr(info, "server_name", None)
                    if not server_name:
                        server_name = getattr(info, "server_id", None)
                    if not server_name:
                        server_name = getattr(info, "server", None)
                    if server_name and str(server_name).lower() == target:
                        return dev_name
                except Exception:
                    pass
                return ""

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                futs = [ex.submit(_match, d) for d in class_devs]
                for fut in futs:
                    try:
                        name = fut.result(timeout=Timeouts.DEVICE_STATE_READ)
                        if name:
                            devices.append(name)
                    except Exception:
                        continue
            return sorted(devices)
        except Exception as e:
            logger.debug(
                f"_list_devices_for_server failed for {server_class}/{instance}: {e}"
            )
            return devices
