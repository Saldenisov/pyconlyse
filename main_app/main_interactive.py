#!/usr/bin/env python3
"""PyConlyse Interactive Application

This version provides an interactive menu system for managing
the Tango infrastructure and device servers.
"""

import logging
import sys
from pathlib import Path

# Add main_app parent directory to path for package imports
main_app_path = Path(__file__).parent
sys.path.insert(0, str(main_app_path.parent))

# Import as a package
from main_app.core.config import *
from main_app.managers.device_manager import DeviceServerManager
from main_app.managers.infrastructure_manager import TangoInfrastructureManager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PyConlyseInteractiveApp:
    """Interactive PyConlyse Application with menu system."""

    def __init__(self):
        """Initialize the interactive application."""
        self.bin_path = main_app_path.parent / "bin"
        self.infrastructure_mgr = TangoInfrastructureManager(self.bin_path)
        self.device_mgr = DeviceServerManager(self.bin_path)
        self.running = True

        logger.info(
            f"PyConlyse Interactive App initialized with bin path: {self.bin_path}"
        )

    def show_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 60)
        print("🔬 PyConlyse Interactive Application v2.0")
        print("=" * 60)
        print("1. 🏗️  Infrastructure Management")
        print("2. 🖥️  Device Server Management")
        print("3. 📊 Status & Monitoring")
        print("4. ⚙️  Configuration")
        print("5. 🧪 Run Tests")
        print("0. ❌ Exit")
        print("=" * 60)

    def show_infrastructure_menu(self):
        """Display infrastructure management menu."""
        while True:
            print("\n" + "=" * 50)
            print("🏗️ Infrastructure Management")
            print("=" * 50)
            print("1. Start Tango Infrastructure")
            print("2. Stop Tango Infrastructure")
            print("3. Restart Infrastructure")
            print("4. Infrastructure Status")
            print("0. ← Back to Main Menu")
            print("=" * 50)

            choice = input("\nEnter your choice (0-4): ").strip()

            if choice == "1":
                self.start_infrastructure()
            elif choice == "2":
                self.stop_infrastructure()
            elif choice == "3":
                self.restart_infrastructure()
            elif choice == "4":
                self.show_infrastructure_status()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice. Please try again.")

    def show_device_menu(self):
        """Display device server management menu."""
        while True:
            print("\n" + "=" * 50)
            print("🖥️ Device Server Management")
            print("=" * 50)
            print("1. Start Device Server")
            print("2. Stop Device Server")
            print("3. Start All Device Servers")
            print("4. Stop All Device Servers")
            print("5. List Available Device Types")
            print("6. Show Running Servers")
            print("0. ← Back to Main Menu")
            print("=" * 50)

            choice = input("\nEnter your choice (0-6): ").strip()

            if choice == "1":
                self.start_device_server()
            elif choice == "2":
                self.stop_device_server()
            elif choice == "3":
                self.start_all_device_servers()
            elif choice == "4":
                self.stop_all_device_servers()
            elif choice == "5":
                self.list_device_types()
            elif choice == "6":
                self.show_running_servers()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice. Please try again.")

    def start_infrastructure(self):
        """Start Tango infrastructure with progress feedback."""
        print("\n🚀 Starting Tango Infrastructure...")

        def progress_callback(message):
            print(f"   {message}")

        success = self.infrastructure_mgr.start_infrastructure(progress_callback)
        if success:
            print("✅ Infrastructure started successfully!")
        else:
            print("❌ Failed to start infrastructure. Check logs for details.")

    def stop_infrastructure(self):
        """Stop Tango infrastructure."""
        print("\n🛑 Stopping Tango Infrastructure...")
        success = self.infrastructure_mgr.stop_infrastructure()
        if success:
            print("✅ Infrastructure stopped successfully!")
        else:
            print("❌ Failed to stop infrastructure. Check logs for details.")

    def restart_infrastructure(self):
        """Restart Tango infrastructure."""
        print("\n🔄 Restarting Tango Infrastructure...")
        self.stop_infrastructure()
        print("   Waiting 3 seconds...")
        import time

        time.sleep(3)
        self.start_infrastructure()

    def show_infrastructure_status(self):
        """Show infrastructure status."""
        print("\n📊 Infrastructure Status:")
        status = self.infrastructure_mgr.get_status()
        for component, state in status.items():
            status_icon = (
                "✅"
                if state in ["Connected", "Running"]
                else "❌" if state == "Not started" else "⚠️"
            )
            print(f"   {status_icon} {component.title()}: {state}")

    def start_device_server(self):
        """Start a specific device server."""
        self.list_device_types()

        device_type = input("\nEnter device type: ").strip().upper()
        if not device_type or device_type not in get_all_device_types():
            print("❌ Invalid device type!")
            return

        config = get_device_server_config(device_type)
        print(f"Available instances: {', '.join(config['instances'])}")

        instance = input("Enter instance name: ").strip()
        if not instance or instance not in config["instances"]:
            print("❌ Invalid instance name!")
            return

        vis_type = (
            input("Enter visualization type (FULL/MINIMAL) [FULL]: ").strip() or "FULL"
        )

        print(f"\n🚀 Starting {device_type}/{instance}...")
        success = self.device_mgr.start_deviceserver(device_type, instance, vis_type)
        if success:
            print("✅ Device server started successfully!")
        else:
            print("❌ Failed to start device server. Check logs for details.")

    def stop_device_server(self):
        """Stop a specific device server."""
        running = self.device_mgr.get_running_servers()
        if not running:
            print("\n❌ No device servers are currently running.")
            return

        print("\n🖥️ Running Device Servers:")
        for i, (server_key, info) in enumerate(running.items(), 1):
            print(
                f"   {i}. {info['device_type']}/{info['instance']} ({info['status']})"
            )

        try:
            choice = int(input(f"\nEnter server number to stop (1-{len(running)}): "))
            if 1 <= choice <= len(running):
                server_key = list(running.keys())[choice - 1]
                info = running[server_key]

                print(f"\n🛑 Stopping {info['device_type']}/{info['instance']}...")
                success = self.device_mgr.stop_deviceserver(
                    info["device_type"], info["instance"]
                )
                if success:
                    print("✅ Device server stopped successfully!")
                else:
                    print("❌ Failed to stop device server.")
            else:
                print("❌ Invalid choice!")
        except ValueError:
            print("❌ Please enter a valid number!")

    def start_all_device_servers(self):
        """Start all configured device servers."""
        print("\n🚀 Starting all configured device servers...")
        count = self.device_mgr.start_all_configured_servers()
        print(f"✅ Started {count} device servers!")

    def stop_all_device_servers(self):
        """Stop all running device servers."""
        print("\n🛑 Stopping all device servers...")
        count = self.device_mgr.stop_all_servers()
        print(f"✅ Stopped {count} device servers!")

    def list_device_types(self):
        """List all available device types."""
        print("\n📋 Available Device Types:")
        for device_type in get_all_device_types():
            config = get_device_server_config(device_type)
            instances = ", ".join(config["instances"])
            print(f"   🔧 {device_type}: [{instances}]")

    def show_running_servers(self):
        """Show all running device servers."""
        running = self.device_mgr.get_running_servers()
        if not running:
            print("\n❌ No device servers are currently running.")
        else:
            print(f"\n🖥️ Running Device Servers ({len(running)}):")
            for server_key, info in running.items():
                status_icon = "✅" if info["status"] == "Running" else "❌"
                print(
                    f"   {status_icon} {info['device_type']}/{info['instance']} - {info['vis_type']} ({info['status']})"
                )

    def show_status_menu(self):
        """Show status and monitoring menu."""
        while True:
            print("\n" + "=" * 50)
            print("📊 Status & Monitoring")
            print("=" * 50)
            print("1. Complete System Status")
            print("2. Infrastructure Status Only")
            print("3. Device Servers Status Only")
            print("4. Refresh Status")
            print("0. ← Back to Main Menu")
            print("=" * 50)

            choice = input("\nEnter your choice (0-4): ").strip()

            if choice == "1":
                self.show_complete_status()
            elif choice == "2":
                self.show_infrastructure_status()
            elif choice == "3":
                self.show_running_servers()
            elif choice == "4":
                print("🔄 Refreshing status...")
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice. Please try again.")

    def show_complete_status(self):
        """Show complete system status."""
        print("\n" + "=" * 60)
        print("📊 Complete PyConlyse System Status")
        print("=" * 60)

        # Infrastructure status
        self.show_infrastructure_status()

        # Device servers status
        print()
        self.show_running_servers()

        # Configuration summary
        print("\n⚙️ Configuration Summary:")
        print(f"   📁 Bin Path: {self.bin_path}")
        print(f"   🔧 Available Device Types: {len(get_all_device_types())}")
        print(f"   ⏱️ Database Timeout: {Timeouts.DATABASE_CONNECTION}s")

    def show_configuration(self):
        """Show configuration details."""
        print("\n" + "=" * 50)
        print("⚙️ Configuration Details")
        print("=" * 50)

        print("📁 Application Paths:")
        print(f"   Bin Directory: {self.bin_path}")
        print(f"   Main App: {main_app_path}")

        print("\n⏱️ Timeouts:")
        print(f"   Database Connection: {Timeouts.DATABASE_CONNECTION}s")
        print(f"   Device Operation: {Timeouts.DEVICE_OPERATION}s")
        print(f"   Subprocess Start: {Timeouts.SUBPROCESS_START}s")

        print("\n🔧 Device Server Configurations:")
        for device_type, config in DEVICE_SERVER_CONFIGS.items():
            print(f"   {device_type}:")
            print(f"     Script: {config['script']}")
            print(f"     Instances: {', '.join(config['instances'])}")

    def run_tests(self):
        """Run the test suite."""
        print("\n🧪 Running PyConlyse Test Suite...")
        print("=" * 50)

        try:
            import subprocess

            result = subprocess.run(
                [sys.executable, "-m", "main_app.tests.test_simple"],
                check=False,
                cwd=str(main_app_path.parent),
                capture_output=True,
                text=True,
            )

            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)

            if result.returncode == 0:
                print("✅ All tests completed!")
            else:
                print(f"❌ Tests failed with return code {result.returncode}")

        except Exception as e:
            print(f"❌ Failed to run tests: {e}")

    def run(self):
        """Run the interactive application."""
        print("🔬 Welcome to PyConlyse Interactive Application!")

        while self.running:
            try:
                self.show_main_menu()
                choice = input("\nEnter your choice (0-5): ").strip()

                if choice == "1":
                    self.show_infrastructure_menu()
                elif choice == "2":
                    self.show_device_menu()
                elif choice == "3":
                    self.show_status_menu()
                elif choice == "4":
                    self.show_configuration()
                elif choice == "5":
                    self.run_tests()
                elif choice == "0":
                    print("\n👋 Goodbye! Thanks for using PyConlyse!")
                    self.running = False
                else:
                    print("❌ Invalid choice. Please try again.")

            except KeyboardInterrupt:
                print("\n\n⚠️ Interrupted by user. Exiting...")
                self.running = False
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.exception("Application error")


def main():
    """Main entry point for the interactive application."""
    try:
        app = PyConlyseInteractiveApp()
        app.run()
        return 0
    except Exception as e:
        logger.error(f"Failed to start interactive application: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
