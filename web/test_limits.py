#!/usr/bin/env python3
"""
Test script for iTest PSU limits functionality
"""
import sys
import os
sys.path.append('backend')

import requests
import json

# Configuration
BASE_URL = "http://10.20.30.202:5000"  # Update with your web server URL
DEVICE_NAME = "your/itest/device/name"  # Update with your actual device name

def test_get_current_with_limits():
    """Test GET /api/device/itest/<device>/current returns limits"""
    print("Testing GET current with limits...")
    
    url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/current"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET successful")
            print(f"  Current setpoint: {data.get('current_setpoint', 'N/A')}")
            print(f"  Current limits: {data.get('current_limits', 'N/A')}")
            return data.get('current_limits')
        else:
            print(f"✗ GET failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ GET error: {e}")
        return None

def test_set_current_within_limits(limits):
    """Test setting current within limits"""
    if not limits:
        print("Skipping within-limits test (no limits available)")
        return
    
    print("\nTesting SET current within limits...")
    test_value = (limits['min'] + limits['max']) / 2  # Middle value
    
    url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/current"
    data = {"action": "set", "value": test_value}
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print(f"✓ SET within limits successful: {test_value}A")
        else:
            print(f"✗ SET within limits failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ SET within limits error: {e}")

def test_set_current_outside_limits(limits):
    """Test setting current outside limits (should fail)"""
    if not limits:
        print("Skipping outside-limits test (no limits available)")
        return
    
    print("\nTesting SET current outside limits...")
    test_value = limits['max'] + 5.0  # Above max limit
    
    url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/current"
    data = {"action": "set", "value": test_value}
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 400:
            result = response.json()
            print(f"✓ SET outside limits correctly rejected: {result.get('error', 'No error message')}")
        else:
            print(f"✗ SET outside limits should have been rejected but got: {response.status_code}")
    except Exception as e:
        print(f"✗ SET outside limits error: {e}")

def main():
    print(f"Testing iTest PSU limits functionality")
    print(f"Base URL: {BASE_URL}")
    print(f"Device: {DEVICE_NAME}")
    print("=" * 50)
    
    # Test 1: Get current with limits
    limits = test_get_current_with_limits()
    
    # Test 2: Set within limits
    test_set_current_within_limits(limits)
    
    # Test 3: Set outside limits
    test_set_current_outside_limits(limits)
    
    print("\n" + "=" * 50)
    print("Test completed. Update DEVICE_NAME and BASE_URL in this script for actual testing.")

if __name__ == "__main__":
    main()