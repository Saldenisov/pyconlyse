#!/usr/bin/env python3
"""
Test script to verify that iTest slot limits are working correctly with the web client.

This script tests the new slot-specific API endpoint to ensure:
1. Current limits are correctly retrieved for each slot
2. Limits are enforced when setting current values
3. Multi-slot devices work properly
"""

import requests
import json
import sys
from pathlib import Path

# Add backend to path for device testing
sys.path.append(str(Path(__file__).parent / "backend"))

# Configuration - update these for your setup
BASE_URL = "http://localhost:5000"  # Update with your web server URL
DEVICE_NAME = "elyse/pdu/itest"     # Update with your actual device name
TEST_SLOT_ID = 1                    # Slot to test (will be detected automatically)

def test_get_available_slots():
    """Test getting available slots from multi-slot device"""
    print("1. Testing slot discovery...")
    
    url = f"{BASE_URL}/api/device/ds_itest_psu/{DEVICE_NAME}/slots"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            slots = data.get('available_slot_ids', [])
            print(f"✓ Available slots: {slots}")
            return slots
        else:
            print(f"✗ Slot discovery failed: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"✗ Slot discovery error: {e}")
        return []

def test_get_slot_current_with_limits(slot_id):
    """Test GET /api/device/itest/<device>/slot/<slot_id>/current returns correct limits"""
    print(f"\n2. Testing GET current with limits for slot {slot_id}...")
    
    url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/slot/{slot_id}/current"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET successful for slot {slot_id}")
            print(f"  Current setpoint: {data.get('current_setpoint', 'N/A')}A")
            print(f"  Measured current: {data.get('measured_current', 'N/A')}A")
            print(f"  Current limits: {data.get('current_limits', 'N/A')}")
            return data.get('current_limits')
        else:
            print(f"✗ GET failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ GET error: {e}")
        return None

def test_set_current_within_limits(slot_id, limits):
    """Test setting current within limits"""
    if not limits:
        print(f"Skipping within-limits test for slot {slot_id} (no limits available)")
        return
    
    print(f"\n3. Testing SET current within limits for slot {slot_id}...")
    test_value = (limits['min'] + limits['max']) / 2  # Middle value
    
    url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/slot/{slot_id}/current"
    data = {"action": "set", "value": test_value}
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ SET within limits successful: {test_value:.3f}A")
            print(f"  Actual setpoint: {result.get('current_setpoint', 'N/A')}A")
        else:
            print(f"✗ SET within limits failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ SET within limits error: {e}")

def test_set_current_outside_limits(slot_id, limits):
    """Test setting current outside limits (should fail)"""
    if not limits:
        print(f"Skipping outside-limits test for slot {slot_id} (no limits available)")
        return
    
    print(f"\n4. Testing SET current outside limits for slot {slot_id}...")
    test_value = limits['max'] + 5.0  # Above max limit
    
    url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/slot/{slot_id}/current"
    data = {"action": "set", "value": test_value}
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 400:
            result = response.json()
            print(f"✓ SET outside limits correctly rejected: {result.get('error', 'No error message')}")
        else:
            print(f"✗ SET outside limits should have been rejected but got: {response.status_code}")
            if response.status_code == 200:
                print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"✗ SET outside limits error: {e}")

def test_increment_actions(slot_id):
    """Test increment/decrement actions"""
    print(f"\n5. Testing increment/decrement actions for slot {slot_id}...")
    
    url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/slot/{slot_id}/current"
    
    # Test fine increment
    try:
        response = requests.post(url, json={"action": "inc_fine"})
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Fine increment successful: {result.get('current_setpoint', 'N/A')}A")
        else:
            print(f"✗ Fine increment failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Fine increment error: {e}")
    
    # Test fine decrement
    try:
        response = requests.post(url, json={"action": "dec_fine"})
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Fine decrement successful: {result.get('current_setpoint', 'N/A')}A")
        else:
            print(f"✗ Fine decrement failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Fine decrement error: {e}")

def test_multiple_slots(slots):
    """Test that different slots have different limits (if configured)"""
    if len(slots) < 2:
        print("\n6. Skipping multi-slot limits test (only one slot available)")
        return
    
    print(f"\n6. Testing different limits for multiple slots...")
    
    slot_limits = {}
    for slot_id in slots[:3]:  # Test first 3 slots
        url = f"{BASE_URL}/api/device/itest/{DEVICE_NAME}/slot/{slot_id}/current"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                limits = data.get('current_limits')
                slot_limits[slot_id] = limits
                print(f"  Slot {slot_id}: limits = {limits}")
            else:
                print(f"  Slot {slot_id}: failed to get limits")
        except Exception as e:
            print(f"  Slot {slot_id}: error = {e}")
    
    # Check if slots have different limits
    unique_limits = set(str(limits) for limits in slot_limits.values() if limits)
    if len(unique_limits) > 1:
        print("✓ Multiple slots have different limits (good - slot-specific limits working)")
    elif len(unique_limits) == 1:
        print("⚠ All slots have same limits (may be expected if config sets same limits)")
    else:
        print("✗ Could not determine slot limits")

def main():
    print(f"Testing iTest slot limits functionality")
    print(f"Base URL: {BASE_URL}")
    print(f"Device: {DEVICE_NAME}")
    print("=" * 60)
    
    # Test 1: Get available slots
    slots = test_get_available_slots()
    if not slots:
        print("Could not discover slots. Check device connection and configuration.")
        return
    
    # Use first available slot for detailed testing
    test_slot = slots[0]
    
    # Test 2: Get current with limits
    limits = test_get_slot_current_with_limits(test_slot)
    
    # Test 3: Set within limits
    test_set_current_within_limits(test_slot, limits)
    
    # Test 4: Set outside limits
    test_set_current_outside_limits(test_slot, limits)
    
    # Test 5: Increment/decrement actions
    test_increment_actions(test_slot)
    
    # Test 6: Multiple slot limits
    test_multiple_slots(slots)
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("\nTo test with the web UI:")
    print(f"1. Open browser to {BASE_URL}")
    print(f"2. Navigate to iTest PSU client for device: {DEVICE_NAME}")
    print("3. Verify slot selection dropdown appears")
    print("4. Test setting current values outside limits - should show error")
    print("5. Verify limits shown in UI match the configured values")

if __name__ == "__main__":
    main()