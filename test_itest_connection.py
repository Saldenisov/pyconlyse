#!/usr/bin/env python3
"""
Simple test script to debug iTest PSU SCPI connection issues.
This will help isolate if the problem is with the SCPI communication.
"""

import sys
import traceback

def test_basic_connection():
    """Test basic TCP connection without SCPI"""
    import socket
    
    host = "10.20.30.24"
    port = 5025
    timeout = 3.0
    
    print(f"Testing basic TCP connection to {host}:{port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        
        if result == 0:
            print("✓ TCP connection successful")
            
            # Try sending a simple SCPI identification command
            print("Sending *IDN? command...")
            sock.send(b"*IDN?\n")
            
            # Try to receive response
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            print(f"Response: {repr(response)}")
            
            sock.close()
            return True
        else:
            print(f"✗ TCP connection failed with code: {result}")
            return False
            
    except Exception as e:
        print(f"✗ TCP connection failed: {e}")
        traceback.print_exc()
        return False

def test_easy_scpi():
    """Test easy-scpi library connection"""
    print("\nTesting easy-scpi connection...")
    
    try:
        from easy_scpi import Instrument
        
        host = "10.20.30.24"
        port = 5025
        resource = f"TCPIP::{host}::{port}::SOCKET"
        
        print(f"Creating easy-scpi instrument with resource: {resource}")
        
        params = {
            "timeout": 3000,  # 3 seconds in milliseconds
            "read_termination": "\n",
            "write_termination": "\n",
        }
        
        inst = Instrument(port=resource, port_match=False, **params)
        print("✓ Instrument created")
        
        print("Connecting...")
        inst.connect()
        print("✓ Connected successfully")
        
        print("Sending *IDN? command...")
        response = inst.query("*IDN?")
        print(f"Response: {repr(response)}")
        
        print("Disconnecting...")
        inst.disconnect()
        print("✓ Disconnected")
        
        return True
        
    except ImportError as e:
        print(f"✗ easy-scpi not available: {e}")
        return False
    except Exception as e:
        print(f"✗ easy-scpi connection failed: {e}")
        traceback.print_exc()
        return False

def test_itest_scpi_wrapper():
    """Test the ITestSCPI wrapper directly"""
    print("\nTesting ITestSCPI wrapper...")
    
    try:
        sys.path.append("DeviceServers/power/iTest")
        from scpi_client import ITestSCPI
        
        host = "10.20.30.24"
        port = 5025
        
        print(f"Creating ITestSCPI instance for {host}:{port}")
        scpi = ITestSCPI(host, port=port, timeout=5.0)  # Longer timeout for testing
        
        print("Connecting...")
        scpi.connect()
        print("✓ Connected successfully")
        
        print("Testing slot discovery...")
        slots = scpi.list_slots()
        print(f"Discovered slots: {slots}")
        
        scpi.close()
        print("✓ Closed connection")
        
        return True
        
    except Exception as e:
        print(f"✗ ITestSCPI wrapper failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== iTest PSU Connection Debug Test ===\n")
    
    # Test 1: Basic TCP connection
    tcp_ok = test_basic_connection()
    
    # Test 2: easy-scpi library
    easy_scpi_ok = test_easy_scpi()
    
    # Test 3: ITestSCPI wrapper
    wrapper_ok = test_itest_scpi_wrapper()
    
    print("\n=== Summary ===")
    print(f"TCP Connection: {'✓' if tcp_ok else '✗'}")
    print(f"easy-scpi:      {'✓' if easy_scpi_ok else '✗'}")
    print(f"ITestSCPI:      {'✓' if wrapper_ok else '✗'}")
    
    if not any([tcp_ok, easy_scpi_ok, wrapper_ok]):
        print("\n⚠️ All tests failed - there may be a fundamental connectivity issue")
    elif tcp_ok and not easy_scpi_ok:
        print("\n⚠️ Basic TCP works but SCPI library has issues")
    elif tcp_ok and easy_scpi_ok and not wrapper_ok:
        print("\n⚠️ SCPI library works but ITestSCPI wrapper has issues")
    else:
        print("\n✓ Connection should work - issue may be elsewhere")