#!/usr/bin/env python3
"""Script to diagnose NETIO PDU device server connectivity issues"""

import socket
import sys

import requests

sys.path.append(r"C:\dev\pyconlyse")

try:
    import tango
    from tango import Database, DeviceProxy

    def check_netio_devices():
        """Check NETIO PDU devices and their network connectivity."""
        try:
            db = Database()
            print("Connected to TANGO database successfully")

            # Get NETIO devices
            device_list = db.get_device_exported_for_class("DS_Netio_pdu")
            print(f"Found {len(device_list)} DS_Netio_pdu devices:")

            netio_info = {}

            for device_name in device_list:
                print(f"\n=== Analyzing device: {device_name} ===")

                try:
                    # Get device properties
                    props = db.get_device_property(
                        device_name,
                        [
                            "ip_address",
                            "device_id",
                            "friendly_name",
                            "authentication_name",
                            "authentication_password",
                        ],
                    )

                    ip_address = (
                        props.get("ip_address", ["N/A"])[0]
                        if props.get("ip_address")
                        else "N/A"
                    )
                    device_id = (
                        props.get("device_id", ["N/A"])[0]
                        if props.get("device_id")
                        else "N/A"
                    )
                    friendly_name = (
                        props.get("friendly_name", ["N/A"])[0]
                        if props.get("friendly_name")
                        else "N/A"
                    )
                    auth_name = (
                        props.get("authentication_name", ["N/A"])[0]
                        if props.get("authentication_name")
                        else "N/A"
                    )
                    auth_pass = (
                        props.get("authentication_password", ["***"])[0]
                        if props.get("authentication_password")
                        else "***"
                    )

                    print(f"  IP Address: {ip_address}")
                    print(f"  Device ID: {device_id}")
                    print(f"  Friendly Name: {friendly_name}")
                    print(f"  Auth User: {auth_name}")
                    print(f"  Auth Pass: {'***' if auth_pass != 'N/A' else 'N/A'}")

                    netio_info[device_name] = {
                        "ip": ip_address,
                        "device_id": device_id,
                        "friendly_name": friendly_name,
                        "auth": (auth_name, auth_pass) if auth_pass != "***" else None,
                    }

                    # Test network connectivity
                    if ip_address != "N/A":
                        print(f"  Testing network connectivity to {ip_address}...")

                        # Test ping
                        try:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(2)
                            result = sock.connect_ex((ip_address, 80))  # Try HTTP port
                            sock.close()

                            if result == 0:
                                print(f"    ✓ Network connection to {ip_address}:80 OK")
                            else:
                                print(
                                    f"    ✗ Network connection to {ip_address}:80 FAILED"
                                )
                        except Exception as e:
                            print(f"    ✗ Network test failed: {e}")

                        # Test HTTP/API connectivity
                        try:
                            url = f"http://{ip_address}/netio.json"
                            if auth_name != "N/A" and auth_pass != "***":
                                response = requests.get(
                                    url, auth=(auth_name, auth_pass), timeout=5
                                )
                            else:
                                response = requests.get(url, timeout=5)

                            if response.status_code == 200:
                                print(
                                    f"    ✓ NETIO API response OK (status: {response.status_code})"
                                )
                                try:
                                    data = response.json()
                                    agent = data.get("Agent", {})
                                    print(
                                        f"    Device Model: {agent.get('Model', 'Unknown')}"
                                    )
                                    print(
                                        f"    Serial Number: {agent.get('SerialNumber', 'Unknown')}"
                                    )
                                    print(
                                        f"    Version: {agent.get('Version', 'Unknown')}"
                                    )
                                    outputs = data.get("Outputs", [])
                                    print(f"    Number of outputs: {len(outputs)}")
                                except Exception as e:
                                    print(f"    ⚠ API response not JSON: {e}")
                            else:
                                print(
                                    f"    ✗ NETIO API response FAILED (status: {response.status_code})"
                                )

                        except requests.exceptions.RequestException as e:
                            print(f"    ✗ NETIO API request failed: {e}")

                    # Try to connect to TANGO device
                    try:
                        print("  Testing TANGO device connection...")
                        dp = DeviceProxy(device_name)
                        state = dp.state()
                        status = dp.status()
                        print(f"    ✓ TANGO device state: {state}")
                        print(f"    Status: {status}")

                        # Test a simple command
                        try:
                            info = dp.info()
                            print(f"    Device Server: {info.dev_class}")
                        except Exception as e:
                            print(f"    ⚠ Device info failed: {e}")

                    except Exception as e:
                        print(f"    ✗ TANGO device connection FAILED: {e}")

                except Exception as e:
                    print(f"  ERROR getting device properties: {e}")

            return netio_info

        except Exception as e:
            print(f"Error: {e}")
            return {}

    def suggest_fixes(netio_info):
        """Suggest fixes based on the diagnostics."""
        print("\n" + "=" * 60)
        print("DIAGNOSTIC SUMMARY & SUGGESTED FIXES")
        print("=" * 60)

        if not netio_info:
            print("No NETIO devices found or database connection failed.")
            return

        for device_name, info in netio_info.items():
            print(f"\nDevice: {device_name}")
            print(f"  Friendly Name: {info['friendly_name']}")
            print(f"  IP: {info['ip']}")

            if info["ip"] == "N/A":
                print("  🔧 FIX: Set ip_address property in TANGO database")
            elif info["auth"] is None:
                print("  🔧 FIX: Set authentication credentials in TANGO database")
            else:
                print("  🔧 SUGGESTED ACTIONS:")
                print(
                    f"    1. Verify NETIO PDU at {info['ip']} is powered on and accessible"
                )
                print(f"    2. Check network connectivity: ping {info['ip']}")
                print(
                    f"    3. Test API manually: curl -u {info['auth'][0]}:*** http://{info['ip']}/netio.json"
                )
                print("    4. Restart the device server: DS_Netio_pdu")

        print("\n🔧 GENERAL FIXES:")
        print("  1. Restart all NETIO device servers:")
        print("     Get-Process DS_Netio_pdu | Stop-Process -Force")
        print("     Then restart them through your startup script")
        print("  2. Check network configuration and firewall settings")
        print("  3. Verify NETIO PDU devices are powered and accessible")
        print("  4. Check authentication credentials are correct")

    if __name__ == "__main__":
        print("NETIO PDU Device Server Diagnostics")
        print("=" * 40)

        netio_info = check_netio_devices()
        suggest_fixes(netio_info)

except ImportError as e:
    print(f"TANGO import failed: {e}")
    print("Make sure TANGO Python bindings are installed and accessible.")
    sys.exit(1)
