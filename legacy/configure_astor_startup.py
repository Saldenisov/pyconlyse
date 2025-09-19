#!/usr/bin/env python3
"""PYCONLYSE - Astor DeviceServer Configuration Script

This script configures Astor to automatically manage DeviceServer startup
instead of relying on manual batch files. It reads the Tango database
configuration and sets up proper startup commands for each DeviceServer.

Usage:
    python configure_astor_startup.py [--dry-run] [--host HOST]

Arguments:
    --dry-run    Show what would be configured without making changes
    --host HOST  Specify Tango host (default: from TANGO_HOST env var)

"""

import argparse
import logging
import os
import sys
from typing import Dict, List, Optional

try:
    import tango
    from tango import Database, DevFailed, DeviceProxy
except ImportError:
    print("ERROR: PyTango is not installed!")
    print("Please install it with: conda install -c tango-controls pytango")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("astor_config.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class AstorConfigurator:
    """Configure Astor for automatic DeviceServer management"""

    def __init__(self, host: Optional[str] = None, dry_run: bool = False):
        self.host = host or os.environ.get("TANGO_HOST", "localhost:10000")
        self.dry_run = dry_run
        self.pyconlyse_root = os.environ.get("PYCONLYSE", r"C:\dev\pyconlyse")
        self.pyconlyse_env = os.environ.get("PYCONLYSE_ENV", "pyconlyse")

        # Device server configurations
        self.device_configs = {
            "DS_ANDOR_CCD": {
                "path": "DeviceServers/ANDOR_CCD",
                "script": "DS_ANDOR_CCD.py",
                "instances": ["1_ANDOR_CCD1"],  # From the batch files we saw
            },
            "DS_BASLER": {
                "path": "DeviceServers/BASLER",
                "script": "DS_Basler_camera.py",
                "instances": [],  # Will be populated from DB
            },
            "DS_OWIS_PS90": {
                "path": "DeviceServers/OWIS",
                "script": "DS_OWIS_PS90.py",
                "instances": ["1"],  # From the batch files
            },
            "DS_Archive": {
                "path": "DeviceServers/ARCHIVE",
                "script": "DS_Archive.py",
                "instances": [],
            },
            "DS_Standa_Motor": {
                "path": "DeviceServers/STANDA",
                "script": "DS_Standa_Motor.py",
                "instances": [],
            },
            "DS_NetIO_PDU": {
                "path": "DeviceServers/NETIO",
                "script": "DS_NetIO_PDU.py",
                "instances": [],
            },
            "DS_TopDirect_Motor": {
                "path": "DeviceServers/TopDirect",
                "script": "DS_TopDirect_Motor.py",
                "instances": [],
            },
            "DS_LaserPointing": {
                "path": "DeviceServers/LaserPointing",
                "script": "DS_LaserPointing.py",
                "instances": [],
            },
        }

        try:
            logger.info(f"Connecting to Tango Database at {self.host}")
            self.db = Database()
            logger.info("Successfully connected to Tango Database")
        except Exception as e:
            logger.error(f"Failed to connect to Tango Database: {e}")
            raise

    def get_device_servers_from_db(self) -> Dict[str, List[str]]:
        """Get all registered device servers and their instances from the database"""
        servers_info = {}

        try:
            # Get all server instances
            server_list = self.db.get_server_list()
            logger.info(f"Found {len(server_list)} servers in database")

            for server in server_list:
                if "/" in server:
                    server_class, instance = server.split("/", 1)
                    if server_class in self.device_configs:
                        if server_class not in servers_info:
                            servers_info[server_class] = []
                        servers_info[server_class].append(instance)
                        logger.debug(f"Found server: {server_class}/{instance}")

            return servers_info

        except Exception as e:
            logger.error(f"Failed to get server list from database: {e}")
            return {}

    def generate_startup_command(self, server_class: str, instance: str) -> str:
        """Generate the startup command for a DeviceServer"""
        config = self.device_configs.get(server_class)
        if not config:
            raise ValueError(f"Unknown server class: {server_class}")

        server_path = os.path.join(self.pyconlyse_root, config["path"]).replace(
            "\\", "\\\\"
        )
        script_name = config["script"]

        # Create the command that will be used by Astor/Starter
        cmd = (
            f'cmd /c "cd "{server_path}" & '
            f"conda activate {self.pyconlyse_env} & "
            f'python {script_name} {instance}"'
        )

        return cmd

    def configure_starter(
        self, server_class: str, instances: List[str], starter_name: str = "everest"
    ) -> bool:
        """Configure the Tango Starter to manage DeviceServers"""
        try:
            starter_device = f"tango/admin/{starter_name}"
            logger.info(f"Configuring Starter device: {starter_device}")

            if self.dry_run:
                logger.info("[DRY RUN] Would configure Starter with:")
                for instance in instances:
                    cmd = self.generate_startup_command(server_class, instance)
                    server_name = f"{server_class}/{instance}"
                    logger.info(f"  Server: {server_name}")
                    logger.info(f"  Command: {cmd}")
                return True

            # Get the Starter device proxy
            try:
                starter = DeviceProxy(starter_device)

                # For each instance, add it to the Starter configuration
                for instance in instances:
                    server_name = f"{server_class}/{instance}"
                    cmd = self.generate_startup_command(server_class, instance)

                    logger.info(f"Adding server {server_name} to Starter")

                    # Add server to Starter (this depends on your Starter configuration)
                    # The exact method may vary depending on your Tango/Starter version
                    try:
                        # Set the command for the server
                        starter.write_attribute("ServerName", server_name)
                        starter.write_attribute("ServerCommand", cmd)
                        starter.command_inout("AddServer")
                        logger.info(f"Successfully added {server_name} to Starter")

                    except Exception as e:
                        logger.warning(f"Could not add {server_name} to Starter: {e}")
                        logger.info("You may need to configure this manually in Astor")

            except DevFailed as e:
                logger.error(f"Could not access Starter device {starter_device}: {e}")
                return False

        except Exception as e:
            logger.error(f"Failed to configure Starter: {e}")
            return False

        return True

    def create_astor_configuration_file(
        self, servers_info: Dict[str, List[str]]
    ) -> None:
        """Create a configuration file that can be imported into Astor"""
        config_file = os.path.join(
            self.pyconlyse_root, "bin", "astor_device_config.txt"
        )

        logger.info(f"Creating Astor configuration file: {config_file}")

        with open(config_file, "w") as f:
            f.write("# PYCONLYSE DeviceServer Configuration for Astor\n")
            f.write("# This file contains startup commands for all DeviceServers\n")
            f.write("# Import this into Astor to configure automatic startup\n\n")

            for server_class, instances in servers_info.items():
                f.write(f"# {server_class}\n")
                for instance in instances:
                    server_name = f"{server_class}/{instance}"
                    cmd = self.generate_startup_command(server_class, instance)
                    f.write(f"{server_name}:\n")
                    f.write(f"  Command: {cmd}\n")
                    f.write("  AutoStart: true\n")
                    f.write("  Host: everest\n\n")

        logger.info(f"Configuration file created successfully: {config_file}")
        print(f"\nIMPORTANT: Import this file into Astor: {config_file}")

    def run(self) -> None:
        """Main configuration process"""
        logger.info("Starting Astor configuration process")

        # Get servers from database
        servers_info = self.get_device_servers_from_db()

        if not servers_info:
            logger.warning("No known DeviceServers found in database")
            return

        logger.info(f"Found {len(servers_info)} server classes to configure:")
        for server_class, instances in servers_info.items():
            logger.info(f"  {server_class}: {len(instances)} instances")

        # Configure each server class
        success_count = 0
        for server_class, instances in servers_info.items():
            if instances:
                try:
                    if self.configure_starter(server_class, instances):
                        success_count += 1
                    else:
                        logger.error(f"Failed to configure {server_class}")
                except Exception as e:
                    logger.error(f"Error configuring {server_class}: {e}")

        # Create configuration file for manual import
        self.create_astor_configuration_file(servers_info)

        logger.info(
            f"Configuration completed: {success_count}/{len(servers_info)} server classes configured"
        )

        if not self.dry_run:
            print("\nNext steps:")
            print("1. Open Astor GUI")
            print("2. Import the configuration file if automatic configuration failed")
            print("3. Enable auto-start for the DeviceServers")
            print("4. Remove or disable the old manual startup batch files")


def main():
    parser = argparse.ArgumentParser(
        description="Configure Astor for automatic DeviceServer startup management"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be configured without making changes",
    )
    parser.add_argument("--host", help="Tango host (default: from TANGO_HOST env var)")

    args = parser.parse_args()

    try:
        configurator = AstorConfigurator(host=args.host, dry_run=args.dry_run)
        configurator.run()
    except KeyboardInterrupt:
        print("\nConfiguration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
