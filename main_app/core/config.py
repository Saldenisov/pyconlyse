#!/usr/bin/env python3
"""Configuration module for PYCONLYSE Main Control Interface

Contains device configurations, constants, and settings used across the application.
"""

from typing import Dict, List

# Application constants
APP_NAME = "PYCONLYSE Control Center"
APP_VERSION = "2.0"
LOG_FILE = "main_ctrl.log"
MAX_LOG_LINES = 100


# Timeout settings (in seconds)
class Timeouts:
    DATABASE_CONNECTION = 5.0
    DEVICE_OPERATION = 5.0
    DEVICE_STATE_READ = 2.0
    SUBPROCESS_START = 2.0
    DEVICE_INIT = 10.0
    ZMQ_RECEIVE = 1.0
    THREAD_SHUTDOWN = 1000  # milliseconds


# ZMQ Configuration
class ZMQConfig:
    ELYSE_DATA_ADDRESS = "tcp://129.175.100.128:6050"
    ELYSE_DATA_FALLBACK = "tcp://127.0.0.1:6051"
    ELYSE_PUSH_ADDRESS = "tcp://127.0.0.1:5556"
    LINGER_TIME = 1000  # milliseconds


# Device Server Configurations
DEVICE_SERVER_CONFIGS = {
    "ANDOR_CCD": {"instances": ["V0"], "script": "ANDOR_CCD"},
    "BASLER": {"instances": ["V0", "Cam1", "Cam2", "Cam3"], "script": "BASLER"},
    "ARCHIVE": {"instances": ["Main"], "script": "ARCHIVE"},
    "OWIS": {"instances": ["V0", "VD2", "all"], "script": "OWIS_PS90"},
    "STANDA": {
        "instances": ["alignment", "V0", "V0_short", "ELYSE", "OPA"],
        "script": "STANDA",
    },
    "NETIO": {"instances": ["all", "V0", "VD2"], "script": "NETIO"},
    "TOPDIRECT": {"instances": ["VD2", "all"], "script": "TOPDIRECT"},
    "LASER_POINTING": {
        "instances": ["Cam1", "Cam2", "Cam3", "V0", "3P"],
        "script": "LASER_POINTING",
    },
}

# Tango server patterns for device discovery
TANGO_SERVERS = ["ELYSE", "manip"]

# TEMPORARY: Offline mode to block connections to Tango DB/Device Servers
# Set to False to re-enable connections later.
OFFLINE_MODE = False

# Mapping from logical device types to Tango server class names (admin devices)
SERVER_CLASS_BY_TYPE: Dict[str, str] = {
    "ANDOR_CCD": "DS_ANDOR_CCD",
    "BASLER": "DS_Basler_camera",
    "ARCHIVE": "DS_Archive",
    "OWIS": "DS_OWIS_PS90",
    "STANDA": "DS_Standa_Motor",
    "NETIO": "DS_Netio_pdu",
    "TOPDIRECT": "DS_TopDirect_Motor",
    "LASER_POINTING": "DS_LaserPointing",
}


# RPI GPIO Configuration
class RPIConfig:
    DEVICE_NAME = "manip/v0/rpi4_gpio_v0"
    LIGHT_PIN = 3
    LASER_PIN = 4


# UI Configuration
class UIConfig:
    MIN_WIDTH = 800
    MIN_HEIGHT = 600
    STATUS_UPDATE_INTERVAL = 5000  # milliseconds
    DEVICE_GRID_COLUMNS = 3
    LOG_DISPLAY_HEIGHT = 200


# Infrastructure component start order (Astor removed; observer-only)
INFRASTRUCTURE_START_ORDER = ["database", "starter"]
INFRASTRUCTURE_STOP_ORDER = ["starter", "database"]


# Auto-start delays (milliseconds)
class AutoStartDelays:
    TANGO_CHECK = 2000
    ASTOR_START = 5000
    ASTOR_CONFIG = 15000
    MANUAL_ASTOR_CONFIG = 10000


# Icon paths (relative to bin directory)
ICON_PATHS = {
    "main": "icons/main_icon.png",
    "start": "icons/DL.svg",
    "stop": "icons/rect20454.png",
    "configure": "icons/experiment.svg",
    "close": "icons/close.png",
    "info": "icons/info.png",
    "light": "icons/light.png",
    "laser": "icons/laser.svg",
    "layout": "icons/layout.svg",
}


def get_device_server_config(device_type: str) -> Dict:
    """Get configuration for a specific device server type."""
    return DEVICE_SERVER_CONFIGS.get(device_type, {})


def get_all_device_types() -> List[str]:
    """Get list of all configured device server types."""
    return list(DEVICE_SERVER_CONFIGS.keys())


def get_instances_for_device(device_type: str) -> List[str]:
    """Get list of instances for a specific device type."""
    config = get_device_server_config(device_type)
    return config.get("instances", [])
