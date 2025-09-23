#!/usr/bin/env python3
"""Demo script showing how to use the modular PyConlyse components.

This script demonstrates the proper way to initialize and use the
TangoInfrastructureManager and DeviceServerManager classes.
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import *
from device_manager import DeviceServerManager
from infrastructure_manager import TangoInfrastructureManager


def demo_configuration():
    """Demonstrate configuration access."""
    print("=== Configuration Demo ===")
    print(f"Available device types: {get_all_device_types()}")
    print(f"Database connection timeout: {Timeouts.DATABASE_CONNECTION}s")
    print(f"Device operation timeout: {Timeouts.DEVICE_OPERATION}s")

    print("\nDevice Server Configurations:")
    for device_type in get_all_device_types():
        config = get_device_server_config(device_type)
        print(
            f"  {device_type}: {len(config['instances'])} instances, script: {config['script']}"
        )
    print()


def demo_infrastructure_manager():
    """Demonstrate TangoInfrastructureManager usage."""
    print("=== Infrastructure Manager Demo ===")

    # Initialize manager
    infra_mgr = TangoInfrastructureManager()
    print(f"Initialized with bin path: {infra_mgr.bin_path}")

    # Check initial status
    status = infra_mgr.get_status()
    print("Initial status:")
    for component, state in status.items():
        print(f"  {component}: {state}")

    # Note: We don't actually start infrastructure in demo
    print("Note: Infrastructure startup requires TANGO_ROOT environment variable")
    print("      and actual Tango installation to work properly.")
    print()


def demo_device_manager():
    """Demonstrate DeviceServerManager usage."""
    print("=== Device Server Manager Demo ===")

    # Initialize manager
    device_mgr = DeviceServerManager()
    print(f"Initialized with bin path: {device_mgr.bin_path}")

    # Show available device types
    available_types = device_mgr.get_available_device_types()
    print("Available device types:")
    for device_type, config in available_types.items():
        instances = ", ".join(config["instances"])
        print(f"  {device_type}: [{instances}]")

    # Check running servers
    running = device_mgr.get_running_servers()
    if running:
        print("Currently running servers:")
        for server, info in running.items():
            print(f"  {server}: {info['status']}")
    else:
        print("No servers currently running")

    print("Note: Device server startup requires actual script files")
    print("      and proper Tango environment to work.")
    print()


def demo_integration():
    """Demonstrate how components work together."""
    print("=== Integration Demo ===")

    # Initialize both managers
    infra_mgr = TangoInfrastructureManager()
    device_mgr = DeviceServerManager()

    print("Typical startup sequence would be:")
    print("1. Start Tango infrastructure (database, starter, astor)")
    print("2. Wait for infrastructure to be ready")
    print("3. Start individual device servers")
    print("4. Monitor device states")

    print("\nTypical shutdown sequence would be:")
    print("1. Stop all device servers")
    print("2. Stop Tango infrastructure")
    print("3. Clean up resources")

    # Show status from both managers
    infra_status = infra_mgr.get_status()
    device_status = device_mgr.get_running_servers()

    print(f"\nInfrastructure components: {len(infra_status)}")
    print(f"Running device servers: {len(device_status)}")
    print()


def main():
    """Run the complete demo."""
    print("PyConlyse Modular Architecture Demo")
    print("=" * 50)
    print()

    try:
        demo_configuration()
        demo_infrastructure_manager()
        demo_device_manager()
        demo_integration()

        print("Demo completed successfully!")
        print()
        print("Next steps:")
        print("- Run the test suite: python test_simple.py")
        print("- Create monitoring_threads.py module")
        print("- Create main_window.py module")
        print("- Update main_ctrl.py to use modular components")

    except Exception as e:
        print(f"Demo failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
