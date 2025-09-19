#!/usr/bin/env python3
"""Script to find processes that might be using Basler cameras"""

import subprocess
import sys


def find_camera_processes():
    """Find processes that might be using cameras"""
    print("🔍 Searching for processes that might be using cameras...")
    print("=" * 60)

    # Common camera-related process names
    camera_processes = [
        "pylon",
        "basler",
        "camera",
        "DS_Basler_camera",
        "python",
        "viewer",
        "capture",
        "stream",
    ]

    found_processes = []

    try:
        # Get all running processes
        result = subprocess.run(
            ["tasklist"], check=False, capture_output=True, text=True, shell=True
        )

        if result.returncode == 0:
            lines = result.stdout.split("\n")

            for line in lines:
                if line.strip():
                    # Parse process info (name is first column)
                    parts = line.split()
                    if len(parts) >= 2:
                        process_name = parts[0].lower()
                        pid = parts[1] if parts[1].isdigit() else "Unknown"

                        # Check if process name matches camera-related terms
                        for term in camera_processes:
                            if term in process_name:
                                found_processes.append(
                                    {
                                        "name": parts[0],
                                        "pid": pid,
                                        "full_line": line.strip(),
                                    }
                                )
                                break

            if found_processes:
                print("📋 Found potentially camera-related processes:")
                print()
                for proc in found_processes:
                    print(f"🔸 {proc['name']} (PID: {proc['pid']})")
                    print(f"   {proc['full_line']}")
                    print()

                print("💡 Suggestions:")
                print("1. Check if any of these processes are using your Basler camera")
                print("2. Stop unnecessary camera applications")
                print("3. If DS_Basler_camera processes are running, stop them first")
                print("4. Use Task Manager to end processes if needed")

            else:
                print("✅ No obvious camera-related processes found")
                print("   The camera might be used by a system service or driver")

        else:
            print(f"❌ Error running tasklist: {result.stderr}")

    except Exception as e:
        print(f"❌ Error finding processes: {e}")

    return found_processes


def find_network_connections():
    """Find network connections that might be camera-related"""
    print("\n🌐 Searching for camera-related network connections...")
    print("=" * 60)

    try:
        # Get network connections
        result = subprocess.run(
            ["netstat", "-an"], check=False, capture_output=True, text=True, shell=True
        )

        if result.returncode == 0:
            lines = result.stdout.split("\n")
            camera_ports = []

            # Look for connections to camera IP addresses (based on your setup)
            camera_ips = [
                "10.20.30.31",
                "10.20.30.32",
                "10.20.30.34",
            ]  # From your camera config

            for line in lines:
                if line.strip():
                    for ip in camera_ips:
                        if ip in line:
                            camera_ports.append(line.strip())

            if camera_ports:
                print("📡 Found camera-related network connections:")
                for conn in camera_ports:
                    print(f"   {conn}")

                print("\n💡 This indicates active camera connections")
            else:
                print("✅ No camera-related network connections found")

        else:
            print(f"❌ Error running netstat: {result.stderr}")

    except Exception as e:
        print(f"❌ Error checking network connections: {e}")


def suggest_solutions():
    """Provide solutions based on findings"""
    print("\n🔧 SOLUTION STEPS:")
    print("=" * 60)
    print("1. 🛑 Stop any running DS_Basler_camera processes:")
    print("   - Check Task Manager for python.exe processes")
    print("   - Look for DS_Basler_camera in process names")
    print("   - End these processes")
    print()
    print("2. 🔌 Check camera connections:")
    print("   - Ensure cameras are powered on")
    print("   - Check network cable connections")
    print("   - Verify camera IP addresses are reachable")
    print()
    print("3. 🔄 Restart device server:")
    print("   - Use Astor to restart the device server")
    print("   - Or manually restart with proper instance name")
    print()
    print("4. 🖥️ Check camera software:")
    print("   - Close Basler Pylon Viewer if open")
    print("   - Close any other camera applications")
    print("   - Restart camera driver if needed")


def main():
    """Main function"""
    print("Basler Camera Process Finder")
    print("=" * 60)

    # Find processes
    processes = find_camera_processes()

    # Find network connections
    find_network_connections()

    # Suggest solutions
    suggest_solutions()

    return len(processes)


if __name__ == "__main__":
    process_count = main()
    sys.exit(process_count)
