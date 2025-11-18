#!/usr/bin/env python3
"""Script to restart NETIO PDU device servers"""

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.append(r"C:\dev\pyconlyse")

# NETIO server configurations based on add_ds_NETIO.py
NETIO_SERVERS = {
    "1_V0": {
        "device_name": "manip/V0/PDU_VO",
        "ip": "10.20.30.40",
        "friendly_name": "PDU_VO",
    },
    "2_VD2": {
        "device_name": "manip/VD2/PDU_VD2",
        "ip": "10.20.30.41",
        "friendly_name": "PDU_VD2",
    },
    "3_SD1": {
        "device_name": "manip/SD1/PDU_SD1",
        "ip": "10.20.30.42",
        "friendly_name": "PDU_SD1",
    },
    "4_SD2": {
        "device_name": "manip/SD2/PDU_SD2",
        "ip": "10.20.30.43",
        "friendly_name": "PDU_SD2",
    },
    "5_ELYSE": {
        "device_name": "manip/ELYSE/PDU_ELYSE",
        "ip": "10.20.30.44",
        "friendly_name": "PDU_ELYSE",
    },
}


def start_netio_server(server_id, server_info):
    """Start a single NETIO device server."""
    print(f"Starting NETIO server: {server_id} ({server_info['friendly_name']})")

    # Path to device server
    netio_path = Path(r"C:\dev\pyconlyse\DeviceServers\power\netio")
    script_path = netio_path / "DS_Netio_pdu.py"

    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        return False

    try:
        # Start the device server process
        cmd = [
            "cmd",
            "/c",
            f'cd "{netio_path}" && conda activate pyconlyse39 && python DS_Netio_pdu.py {server_id}',
        ]

        # Start in background
        process = subprocess.Popen(
            cmd,
            shell=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE
            | subprocess.CREATE_NEW_PROCESS_GROUP,
            cwd=str(netio_path),
        )

        print(f"  Started with PID: {process.pid}")
        return True

    except Exception as e:
        print(f"  ERROR starting server: {e}")
        return False


def test_server_connection(server_info):
    """Test if a server is responding to TANGO commands."""
    try:
        import tango

        dp = tango.DeviceProxy(server_info["device_name"])
        state = dp.state()
        print(f"  Server {server_info['friendly_name']}: {state}")
        return True
    except Exception as e:
        print(f"  Server {server_info['friendly_name']}: NOT RESPONDING ({e})")
        return False


def main():
    print("NETIO PDU Device Server Restart Utility")
    print("=" * 50)

    # Check environment variables
    required_vars = ["PYCONLYSE", "PYCONLYSE_ENV", "ANACONDA"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        print(f"ERROR: Missing environment variables: {', '.join(missing_vars)}")
        print("Please ensure your environment is properly configured.")
        return False

    print("Environment check: OK")
    print(f"Using conda environment: {os.environ.get('PYCONLYSE_ENV', 'pyconlyse39')}")
    print()

    # Start all servers
    print("Starting NETIO device servers...")
    started_servers = 0

    for server_id, server_info in NETIO_SERVERS.items():
        if start_netio_server(server_id, server_info):
            started_servers += 1
            time.sleep(2)  # Give each server time to initialize
        else:
            print(f"  Failed to start {server_id}")

    print(f"\nStarted {started_servers}/{len(NETIO_SERVERS)} NETIO servers")

    # Wait for servers to initialize
    print("Waiting 10 seconds for servers to initialize...")
    time.sleep(10)

    # Test connections
    print("\\nTesting server connections...")
    try:
        import tango

        responsive_servers = 0

        for server_id, server_info in NETIO_SERVERS.items():
            if test_server_connection(server_info):
                responsive_servers += 1

        print(
            f"\\nSummary: {responsive_servers}/{len(NETIO_SERVERS)} servers are responding"
        )

        if responsive_servers == len(NETIO_SERVERS):
            print("✓ All NETIO servers are now working properly!")
            return True
        print("⚠ Some servers are still not responding. Check the logs.")
        return False

    except ImportError:
        print("Cannot test connections: TANGO not available")
        print("Please test manually using your TANGO tools")
        return True


if __name__ == "__main__":
    success = main()
    if not success:
        print("\\nThere were issues starting the servers.")
        print("Check the console outputs and try again if needed.")

    input("\\nPress Enter to exit...")
