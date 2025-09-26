#!/usr/bin/env python3
"""Test script to demonstrate global settings functionality"""

import sys
from pathlib import Path

# Add pyconlyse to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

# Import the global settings directly
from DeviceServers.base.general import CONFIG_DEFAULTS, GLOBAL_SETTINGS


def show_global_settings():
    """Show how global settings work"""
    print("🔧 Global Settings Demo")
    print("=" * 50)

    print("✅ 1. Current default settings:")
    for key, value in CONFIG_DEFAULTS.items():
        print(f"   {key} = {value}")

    print("\n✅ 2. Current active settings:")
    for key, value in GLOBAL_SETTINGS.items():
        print(f"   {key} = {value}")

    print("\n✅ 3. Simulating enabling debug timing:")
    # Simulate what happens when you call set_global_variable
    GLOBAL_SETTINGS["DEBUG_INIT_TIMING"] = True
    GLOBAL_SETTINGS["DEBUG_TIMING_THRESHOLD_MS"] = 5

    print("   After enabling:")
    for key, value in GLOBAL_SETTINGS.items():
        print(f"   {key} = {value}")

    print("\n✅ 4. This is what you'd see in DS logs with debug enabled:")
    print("   === INIT TIMING (ms) ===")
    print("   internal_time_started: 12.3 ms (t=12.3)")
    print("   tango_Device.init_device: 156.7 ms (t=169.0)")
    print("   parameters_parsed: 8.4 ms (t=177.4)")
    print("   archive_init: 2.1 ms (t=179.5)")
    print("   find_device: 2847.3 ms (t=3026.8)")
    print("   post_find_device: 1.2 ms (t=3028.0)")
    print("   Total init: 3028.0 ms")
    print("   ^^^ This would show find_device is taking 2.8 seconds!")

    print("\n📋 What the Control Window looks like:")
    print("   Control for DS_Netio_pdu [1_V0].")
    print(
        "   Type STOP to terminate this device server, or EXIT to close this control."
    )
    print("   Command (STOP/EXIT): STOP")
    print("   Sent stop to DS_Netio_pdu [1_V0].")
    print("   Command (STOP/EXIT):")

    print("\n🎯 How to use:")
    print("   1. Launch any DS: .\\DS_Netio_pdu.bat 1_V0")
    print("   2. Two windows open:")
    print("      - DS window: shows logs and timing info")
    print("      - Control window: type STOP to terminate")
    print("   3. To enable debug timing on next startup:")
    print("      - From any running DS, use Tango commands:")
    print("        * set_global_variable(['DEBUG_INIT_TIMING','true'])")
    print("        * save_global_variables()")
    print("   4. Stop DS using Control window, restart to see timing")


if __name__ == "__main__":
    show_global_settings()
