#!/usr/bin/env python3
"""Taurus Deprecation Warning Fix

This module provides utilities to handle Taurus deprecation warnings
and improve error handling for device connections.

Author: PyConlyse Team
Version: 1.0
"""

import logging
import warnings
from typing import Any, List

from taurus import Device


def suppress_taurus_deprecation_warnings():
    """Suppress known Taurus deprecation warnings that cannot be fixed
    in user code (they are internal to the Taurus library).
    """
    # Filter out the specific deprecation warning about getConfig()
    warnings.filterwarnings(
        "ignore",
        message="getConfig is deprecated since 4.0. Use self instead",
        category=DeprecationWarning,
        module="taurus.qt.qtgui.input.tauruscheckbox",
    )

    # Also filter out any other Taurus getConfig warnings
    warnings.filterwarnings(
        "ignore", message=".*getConfig is deprecated.*", category=DeprecationWarning
    )

    logging.info("Taurus deprecation warnings suppressed")


def safe_device_attribute_access(
    device: Device, attribute_name: str, default_value: Any = None
) -> Any:
    """Safely access a device attribute with proper error handling.

    Args:
        device: Taurus Device instance
        attribute_name: Name of the attribute to access
        default_value: Default value to return if access fails

    Returns:
        The attribute value or default_value if access fails

    """
    try:
        if hasattr(device, attribute_name):
            value = getattr(device, attribute_name)
            # Convert to list if it's a taurus attribute value
            if hasattr(value, "__iter__") and not isinstance(value, str):
                return list(value)
            return value
        logging.warning(f"Device {device} does not have attribute '{attribute_name}'")
        return default_value
    except Exception as e:
        logging.exception(
            f"Failed to access attribute '{attribute_name}' on device {device}: {e}"
        )
        return default_value


def check_device_connection(device: Device) -> bool:
    """Check if a device is properly connected and responsive.

    This function avoids calling attributes as callables (e.g., state()) and
    prefers using a Tango DeviceProxy ping when available.

    Args:
        device: Taurus Device instance

    Returns:
        True if device appears reachable, False otherwise

    """
    if device is None:
        return False

    # Try common ways to access a Tango DeviceProxy and ping it
    try:
        # Direct ping on device (if available)
        ping = getattr(device, "ping", None)
        if callable(ping):
            ping()
            return True
    except Exception:
        # fall through to other methods
        pass

    # Try to get an underlying DeviceProxy from Taurus wrapper
    proxy_candidates = []
    try:
        if hasattr(device, "getDeviceProxy") and callable(device.getDeviceProxy):
            proxy_candidates.append(device.getDeviceProxy())
    except Exception:
        pass

    for attr in ("device", "dev", "proxy"):
        try:
            if hasattr(device, attr):
                proxy_candidates.append(getattr(device, attr))
        except Exception:
            pass

    for dp in proxy_candidates:
        try:
            if dp is None:
                continue
            ping = getattr(dp, "ping", None)
            if callable(ping):
                ping()
                return True
        except Exception:
            continue

    # As a last resort, attempt to read a simple property which goes via DB
    try:
        if hasattr(device, "get_property") and callable(device.get_property):
            # Reading a property does not guarantee device process is up,
            # but it validates basic DB connectivity and model correctness.
            _ = device.get_property("state")
            # Do not assume this means device process is reachable
            # Return False to be conservative
    except Exception as e:
        logging.exception(f"Device connection check failed for {device}: {e}")
        return False

    # Conservative default: not connected
    return False


def get_device_ids_safely(device: Device) -> List[int]:
    """Safely get device IDs with proper error handling.

    Args:
        device: Taurus Device instance

    Returns:
        List of device IDs or empty list if access fails

    """
    ids = safe_device_attribute_access(device, "ids", [])
    if isinstance(ids, (list, tuple)):
        return [int(id_val) for id_val in ids if id_val is not None]
    return []


def get_device_names_safely(device: Device) -> List[str]:
    """Safely get device names with proper error handling.

    Args:
        device: Taurus Device instance

    Returns:
        List of device names or empty list if access fails

    """
    names = safe_device_attribute_access(device, "names", [])
    if isinstance(names, (list, tuple)):
        return [str(name) for name in names if name is not None]
    return []


def get_device_states_safely(device: Device) -> List[bool]:
    """Safely get device states with proper error handling.

    Args:
        device: Taurus Device instance

    Returns:
        List of device states or empty list if access fails

    """
    states = safe_device_attribute_access(device, "states", [])
    if isinstance(states, (list, tuple)):
        return [bool(state) for state in states if state is not None]
    return []
