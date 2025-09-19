#!/usr/bin/env python3
"""Time the actual DS_Netio_pdu startup to measure the archive timeout improvement"""

import subprocess
import sys
import time
from pathlib import Path


def time_netio_startup():
    """Time the DS_Netio_pdu Python startup"""
    print("⏱️  Timing DS_Netio_pdu Python Device Server Startup")
    print("=" * 60)

    netio_script = Path("C:/dev/pyconlyse/DeviceServers/power/netio/DS_Netio_pdu.py")

    if not netio_script.exists():
        print(f"❌ Script not found: {netio_script}")
        return

    # Test startup time by running the script with --help or similar
    print("🚀 Starting DS_Netio_pdu with test instance...")

    start_time = time.time()

    try:
        # Try to run the device server and capture early output
        process = subprocess.Popen(
            [
                sys.executable,
                str(netio_script),
                "test_V0",
                "-v4",  # High verbosity to see initialization messages
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(netio_script.parent),
        )

        # Wait for a few seconds to see if it starts quickly
        try:
            stdout, stderr = process.communicate(timeout=10)
            elapsed = time.time() - start_time

            print(f"✓ Process completed in {elapsed:.2f}s")

            if "Archive connection" in stdout or "Archive connection" in stderr:
                print("📝 Archive connection messages found:")
                for line in (stdout + stderr).split("\n"):
                    if "archive" in line.lower() or "timeout" in line.lower():
                        print(f"  {line}")

            if elapsed < 8:
                print("🎉 GOOD: Startup time is reasonable!")
            else:
                print("⚠️  SLOW: Still taking longer than expected")

        except subprocess.TimeoutExpired:
            process.kill()
            elapsed = time.time() - start_time
            print(f"⏰ Process timed out after {elapsed:.2f}s")
            print(
                "This suggests the device server is running but may be slow to initialize"
            )

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Error after {elapsed:.2f}s: {e}")


def main():
    time_netio_startup()


if __name__ == "__main__":
    main()
