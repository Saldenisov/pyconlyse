#!/usr/bin/env python3
"""Test network connection timing to isolate firewall delays vs Tango protocol delays"""

import socket
import time


def test_raw_socket_connection():
    """Test raw TCP socket connection to everest:10000"""
    print("🔍 Testing raw TCP socket connection to everest:10000")
    print("=" * 60)

    for attempt in range(3):
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout

            print(f"⏱️  Attempt {attempt + 1}: Connecting...")
            sock.connect(("everest", 10000))

            elapsed = time.time() - start_time
            print(f"✓ Raw socket connection: {elapsed:.2f}s")

            sock.close()
            time.sleep(1)  # Brief pause between attempts

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"✗ Raw socket connection failed: {elapsed:.2f}s - {e}")


def test_multiple_connections():
    """Test multiple rapid connections to see if firewall caching helps"""
    print("\n" + "=" * 60)
    print("🔍 Testing multiple rapid connections (firewall caching)")
    print("=" * 60)

    for i in range(5):
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(("everest", 10000))
            elapsed = time.time() - start_time
            print(f"✓ Connection {i + 1}: {elapsed:.2f}s")
            sock.close()
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"✗ Connection {i + 1}: {elapsed:.2f}s - {e}")

        time.sleep(0.5)  # Small delay between connections


def test_localhost_comparison():
    """Test localhost connection for comparison"""
    print("\n" + "=" * 60)
    print("🔍 Testing localhost connection for comparison")
    print("=" * 60)

    # Test a common local service (like HTTP)
    ports_to_test = [80, 443, 22, 3306, 5432]  # Common services

    for port in ports_to_test:
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("localhost", port))
            elapsed = time.time() - start_time
            print(f"✓ localhost:{port}: {elapsed:.2f}s")
            sock.close()
        except Exception:
            elapsed = time.time() - start_time
            if elapsed < 1:  # Quick failures are normal (port closed)
                print(f"- localhost:{port}: {elapsed:.2f}s (port closed)")
            else:
                print(f"✗ localhost:{port}: {elapsed:.2f}s - slow failure")


def main():
    print("🔍 Network Timing Test - Firewall Investigation")
    print("Testing connection patterns to identify firewall delays...")
    print("=" * 60)

    test_raw_socket_connection()
    test_multiple_connections()
    test_localhost_comparison()

    print("\n" + "=" * 60)
    print("📊 ANALYSIS:")
    print(
        "- If raw socket connections are fast (~0.1s), the issue is in Tango protocol"
    )
    print("- If raw socket connections are slow (~20s), it's likely firewall/network")
    print("- If subsequent connections are faster, firewall caching is helping")
    print("- Compare with localhost times to identify network vs firewall issues")


if __name__ == "__main__":
    main()
