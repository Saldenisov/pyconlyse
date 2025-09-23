#!/usr/bin/env python3
"""PYCONLYSE Client Manager - Centralized client management system

This module provides centralized management for all device clients,
allowing them to be launched programmatically from the main control interface
instead of using subprocess calls to separate scripts.

Author: PYCONLYSE Team
Version: 2.0 (Refactored)
"""

import logging
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Type

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QIcon
from taurus.qt.qtgui.application import TaurusApplication

# Add project root to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from DeviceServers.shared.DS_Widget import VisType

# Configure logging
logger = logging.getLogger(__name__)


class ClientRegistry:
    """Registry containing all client configurations"""

    # Import statements for widgets and panels
    IMPORTS = {
        "NETIO": {
            "panel": ("gui.Panels", "NetioPanel"),
            "widget": ("DeviceServers.power.netio.DS_NETIO_Widget", "Netio_pdu"),
        },
        "STANDA": {
            "panel": ("gui.Panels", "StandaPanel"),
            "widget": ("DeviceServers.motion.standa.DS_STANDA_Widget", "Standa_motor"),
        },
        "EXPERIMENT": {
            "panel": ("gui.Panels", "ExperimentPanel"),
            "widget": (
                "DeviceServers.control.experiment.DS_Experiment_Widget",
                "Experiment",
            ),
        },
        "BASLER": {
            "panel": ("gui.Panels", "BaslerPanel"),
            "widget": (
                "DeviceServers.cameras.basler.DS_BASLER_Widget",
                "Basler_camera",
            ),
        },
        "OWIS": {
            "panel": ("gui.Panels", "OWISPanel"),
            "widget": ("DeviceServers.motion.owis.DS_OWIS_widget", "OWIS_motor"),
        },
        "LASER_POINTING": {
            "panel": ("gui.Panels", "LaserPointingPanel"),
            "widget": (
                "DeviceServers.control.laser_pointing.DS_LaserPointing_Widget",
                "LaserPointing",
            ),
        },
        "ANDOR_CCD": {
            "panel": ("gui.Panels", "AndorPanel"),
            "widget": ("DeviceServers.cameras.andor.DS_ANDOR_CCD_Widget", "Andor_CCD"),
        },
        "AVANTES_CCD": {
            "panel": ("gui.Panels", "AvantesPanel"),
            "widget": (
                "DeviceServers.cameras.avantes.DS_AVANTES_CCD_Widget",
                "Avantes_CCD",
            ),
        },
        "ARCHIVE": {
            "panel": ("gui.Panels", "ArchivePanel"),
            "widget": ("DeviceServers.data.archive.DS_Archive_Widget", "Archive"),
        },
        "TOPDIRECT": {
            "panel": ("gui.Panels", "TopDirectPanel"),
            "widget": (
                "DeviceServers.motion.topdirect.DS_TOPDIRECT_Widget",
                "TopDirect",
            ),
        },
    }

    # Client configurations extracted from individual client files
    CONFIGURATIONS = {
        "NETIO": {
            "title": "NETIO Power Distribution",
            "icon": "icons/NETIO.ico",
            "layouts": {
                "V0": {
                    "selection": [
                        "manip/V0/PDU_VO",
                        "manip/SD1/PDU_SD1",
                        "manip/SD2/PDU_SD2",
                    ],
                    "width": 1,
                },
                "VD2": {
                    "selection": ["manip/VD2/PDU_VD2", "manip/SD2/PDU_SD2"],
                    "width": 1,
                },
                "all": {
                    "selection": [
                        "manip/V0/PDU_VO",
                        "manip/VD2/PDU_VD2",
                        "manip/SD1/PDU_SD1",
                        "manip/SD2/PDU_SD2",
                        "manip/ELYSE/PDU_ELYSE",
                    ],
                    "width": 1,
                },
            },
        },
        "STANDA": {
            "title": "STANDA Motion Control",
            "icon": "icons/STANDA.svg",
            "layouts": {
                "ELYSE": {
                    "selection": [
                        "elyse/motorized_devices/de1",
                        "manip/V0/F1",
                        "elyse/motorized_devices/mme_x",
                        "elyse/motorized_devices/mme_y",
                        "elyse/motorized_devices/mm1_x",
                        "elyse/motorized_devices/mm1_y",
                        "elyse/motorized_devices/mm2_x",
                        "elyse/motorized_devices/mm2_y",
                    ],
                    "width": 4,
                },
                "V0": {
                    "selection": [
                        "manip/V0/mm3_x",
                        "manip/V0/mm3_y",
                        "manip/V0/mm4_x",
                        "manip/V0/mm4_y",
                        "manip/V0/dv01",
                        "manip/V0/dv02",
                        "manip/V0/dv03",
                        "manip/V0/dv04",
                        "manip/V0/s1",
                        "manip/V0/s2",
                        "manip/V0/s3",
                        "manip/V0/L-2_1",
                        "manip/V0/opa_x",
                        "manip/V0/opa_y",
                        "manip/v0/ts_sc_m",
                        "manip/v0/ts_opa_m",
                    ],
                    "width": 4,
                },
                "V0_short": {
                    "selection": ["manip/V0/dv04", "manip/V0/L-2_1"],
                    "width": 2,
                },
                "alignment": {
                    "selection": [
                        "elyse/motorized_devices/de1",
                        "elyse/motorized_devices/de2",
                        "manip/V0/dv01",
                        "manip/V0/dv02",
                        "elyse/motorized_devices/mm1_x",
                        "elyse/motorized_devices/mm1_y",
                        "elyse/motorized_devices/mm2_x",
                        "elyse/motorized_devices/mm2_y",
                        "manip/V0/mm3_x",
                        "manip/V0/mm3_y",
                        "manip/V0/mm4_x",
                        "manip/V0/mm4_y",
                        "manip/V0/s1",
                        "manip/V0/s2",
                        "manip/V0/L-2_1",
                        "manip/V0/dv03",
                    ],
                    "width": 4,
                },
                "OPA": {"selection": ["manip/v0/opa_x", "manip/v0/opa_y"], "width": 2},
            },
        },
        "EXPERIMENT": {
            "title": "Experiment Control",
            "icon": "icons/experiment.svg",
            "layouts": {
                "Pump-Probe": {"selection": ["manip/cr/pulse-probe"], "width": 1},
                "3P": {"selection": ["manip/cr/pulse-repump-probe"], "width": 1},
                "Streak-camera": {
                    "selection": ["manip/cr/pulse-probe-streak"],
                    "width": 1,
                },
            },
        },
        "BASLER": {
            "title": "Basler Cameras",
            "icon": "icons/basler_camera.svg",
            "layouts": {
                "V0": {
                    "selection": ["manip/V0/Cam1_V0", "manip/V0/Cam2_V0"],
                    "width": 2,
                },
                "all": {
                    "selection": [
                        "manip/V0/Cam1_V0",
                        "manip/V0/Cam2_V0",
                        "manip/V0/Cam3_V0",
                    ],
                    "width": 3,
                },
                "Cam1": {"selection": ["manip/V0/Cam1_V0"], "width": 1},
                "Cam2": {"selection": ["manip/V0/Cam2_V0"], "width": 1},
                "Cam3": {"selection": ["manip/V0/Cam3_V0"], "width": 1},
            },
        },
        "OWIS": {
            "title": "OWIS Motion Control",
            "icon": "icons/OWIS.png",
            "layouts": {
                "V0": {
                    "selection": [("manip/general/DS_OWIS_PS90", [2, 3, 4])],
                    "width": 1,
                },
                "VD2": {"selection": [("manip/general/DS_OWIS_PS90", [1])], "width": 1},
                "all": {
                    "selection": [("manip/general/DS_OWIS_PS90", [1, 2, 3, 4])],
                    "width": 1,
                },
            },
        },
        "LASER_POINTING": {
            "title": "Laser Pointing Control",
            "icon": "icons/laser_pointing.svg",
            "layouts": {
                "V0": {
                    "selection": [
                        "manip/v0/laserpointing-cam1",
                        "manip/v0/laserpointing-cam2",
                    ],
                    "width": 2,
                },
                "3P": {
                    "selection": [
                        "manip/v0/laserpointing-cam1",
                        "manip/v0/laserpointing-cam2",
                        "manip/v0/laserpointing-cam3",
                    ],
                    "width": 3,
                },
                "Cam1": {"selection": ["manip/v0/laserpointing-cam1"], "width": 1},
                "Cam2": {"selection": ["manip/v0/laserpointing-cam2"], "width": 1},
                "Cam3": {"selection": ["manip/v0/laserpointing-cam3"], "width": 1},
            },
        },
        "ANDOR_CCD": {
            "title": "Andor CCD Camera",
            "icon": "icons/Andor_CCD.svg",
            "layouts": {
                "V0": {"selection": ["manip/V0/Andor_CCD_V0"], "width": 1},
            },
        },
        "AVANTES_CCD": {
            "title": "Avantes Spectrometer",
            "icon": "icons/AVANTES_CCD.svg",
            "layouts": {
                "Spectrometer": {
                    "selection": ["manip/spectrometer/avantes_ccd"],
                    "width": 1,
                },
            },
        },
        "ARCHIVE": {
            "title": "Data Archive",
            "icon": "icons/archive.svg",
            "layouts": {
                "Main": {"selection": ["manip/archive/main"], "width": 1},
            },
        },
        "TOPDIRECT": {
            "title": "TopDirect Motor Control",
            "icon": "icons/TopDirect.svg",
            "layouts": {
                "VD2": {"selection": ["manip/VD2/topdirect"], "width": 1},
                "all": {
                    "selection": ["manip/VD2/topdirect", "manip/general/topdirect"],
                    "width": 1,
                },
            },
        },
    }


class ClientInstance:
    """Represents a running client instance"""

    def __init__(
        self, client_type: str, instance: str, panel_widget, vis_type: VisType
    ):
        self.client_type = client_type
        self.instance = instance
        self.panel_widget = panel_widget
        self.vis_type = vis_type
        self.is_active = True

    def close(self):
        """Close the client instance"""
        try:
            if self.panel_widget and self.is_active:
                self.panel_widget.close()
                self.is_active = False
                logger.info(f"Closed client {self.client_type}/{self.instance}")
        except Exception as e:
            logger.error(
                f"Error closing client {self.client_type}/{self.instance}: {e}"
            )


class ClientManager(QObject):
    """Manages all device clients - launching, tracking, and lifecycle management"""

    # Signals
    client_launched = pyqtSignal(str, str)  # client_type, instance
    client_closed = pyqtSignal(str, str)  # client_type, instance
    client_error = pyqtSignal(str, str, str)  # client_type, instance, error

    def __init__(self):
        super().__init__()
        self.registry = ClientRegistry()
        self.active_clients: Dict[str, ClientInstance] = {}
        self.loaded_classes = {}  # Cache for dynamically loaded classes

    def _import_class(self, module_path: str, class_name: str) -> Optional[Type]:
        """Dynamically import a class"""
        try:
            cache_key = f"{module_path}.{class_name}"
            if cache_key in self.loaded_classes:
                return self.loaded_classes[cache_key]

            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            self.loaded_classes[cache_key] = cls
            return cls

        except Exception as e:
            logger.error(f"Failed to import {class_name} from {module_path}: {e}")
            return None

    def get_available_clients(self) -> Dict[str, Dict]:
        """Get all available client types and their configurations"""
        return self.registry.CONFIGURATIONS

    def get_client_instances(self, client_type: str) -> List[str]:
        """Get available instances for a client type"""
        if client_type in self.registry.CONFIGURATIONS:
            return list(self.registry.CONFIGURATIONS[client_type]["layouts"].keys())
        return []

    def is_client_running(self, client_type: str, instance: str) -> bool:
        """Check if a client instance is currently running"""
        key = f"{client_type}_{instance}"
        return key in self.active_clients and self.active_clients[key].is_active

    def launch_client(
        self, client_type: str, instance: str, vis_type: VisType = VisType.FULL
    ) -> bool:
        """Launch a device client"""
        try:
            # Check if already running
            key = f"{client_type}_{instance}"
            if self.is_client_running(client_type, instance):
                logger.warning(f"Client {client_type}/{instance} is already running")
                return False

            # Validate client type and instance
            if client_type not in self.registry.CONFIGURATIONS:
                logger.error(f"Unknown client type: {client_type}")
                return False

            config = self.registry.CONFIGURATIONS[client_type]
            if instance not in config["layouts"]:
                logger.error(
                    f"Unknown instance '{instance}' for client type '{client_type}'"
                )
                return False

            # Import required classes
            import_info = self.registry.IMPORTS[client_type]
            panel_class = self._import_class(
                import_info["panel"][0], import_info["panel"][1]
            )
            widget_class = self._import_class(
                import_info["widget"][0], import_info["widget"][1]
            )

            if not panel_class or not widget_class:
                logger.error(f"Failed to import classes for {client_type}")
                return False

            # Get layout configuration
            layout_config = config["layouts"][instance]
            selection = layout_config["selection"]
            width = layout_config["width"]

            # Create the client panel
            logger.info(
                f"Launching {client_type} client: {instance} (vis: {vis_type.value})"
            )

            panel = panel_class(
                choice=selection,
                widget_class=widget_class,
                title=f"{config['title']} - {instance}",
                icon=QIcon(config["icon"]),
                width=width,
                vis_type=vis_type,
            )

            # Store the client instance
            client_instance = ClientInstance(client_type, instance, panel, vis_type)
            self.active_clients[key] = client_instance

            # Show the panel
            panel.show()

            # Connect close event to cleanup
            if hasattr(panel, "closeEvent"):
                original_close = panel.closeEvent

                def close_wrapper(event):
                    original_close(event)
                    self._cleanup_client(key)

                panel.closeEvent = close_wrapper

            logger.info(f"Successfully launched {client_type}/{instance}")
            self.client_launched.emit(client_type, instance)
            return True

        except Exception as e:
            logger.error(f"Failed to launch client {client_type}/{instance}: {e}")
            logger.debug(traceback.format_exc())
            self.client_error.emit(client_type, instance, str(e))
            return False

    def close_client(self, client_type: str, instance: str) -> bool:
        """Close a specific client instance"""
        try:
            key = f"{client_type}_{instance}"
            if key in self.active_clients:
                self.active_clients[key].close()
                self._cleanup_client(key)
                return True
            logger.warning(
                f"Client {client_type}/{instance} not found in active clients"
            )
            return False

        except Exception as e:
            logger.error(f"Failed to close client {client_type}/{instance}: {e}")
            return False

    def close_all_clients(self):
        """Close all active client instances"""
        clients_to_close = list(self.active_clients.keys())
        for key in clients_to_close:
            client = self.active_clients[key]
            client.close()
            self._cleanup_client(key)

        logger.info(f"Closed {len(clients_to_close)} clients")

    def _cleanup_client(self, key: str):
        """Clean up a client instance"""
        if key in self.active_clients:
            client = self.active_clients[key]
            self.client_closed.emit(client.client_type, client.instance)
            del self.active_clients[key]

    def get_active_clients(self) -> Dict[str, ClientInstance]:
        """Get all currently active clients"""
        return {k: v for k, v in self.active_clients.items() if v.is_active}

    def get_client_info(self, client_type: str) -> Optional[Dict]:
        """Get detailed information about a client type"""
        return self.registry.CONFIGURATIONS.get(client_type)


# Standalone client launcher function for backward compatibility
def launch_standalone_client(
    client_type: str, instance: str, vis_type: VisType = VisType.FULL
):
    """Launch a client as a standalone application (for backward compatibility)"""
    try:
        # Create TaurusApplication
        app = TaurusApplication(sys.argv, cmd_line_parser=None)

        # Create client manager
        client_manager = ClientManager()

        # Launch the client
        success = client_manager.launch_client(client_type, instance, vis_type)

        if success:
            logger.info(f"Starting standalone {client_type} client: {instance}")
            sys.exit(app.exec_())
        else:
            logger.error(f"Failed to launch standalone client {client_type}/{instance}")
            return False

    except Exception as e:
        logger.error(f"Failed to start standalone client: {e}")
        logger.debug(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Command line interface for testing
    if len(sys.argv) >= 3:
        client_type = sys.argv[1]
        instance = sys.argv[2]
        vis_type = VisType.FULL

        if len(sys.argv) >= 4:
            try:
                vis_type = VisType(sys.argv[3])
            except ValueError:
                logger.warning(f"Invalid vis_type '{sys.argv[3]}', using FULL")

        launch_standalone_client(client_type, instance, vis_type)
    else:
        print("Usage: python ClientManager.py <client_type> <instance> [vis_type]")
        print("Available client types:")
        registry = ClientRegistry()
        for client_type, config in registry.CONFIGURATIONS.items():
            instances = list(config["layouts"].keys())
            print(f"  {client_type}: {instances}")
