#!/usr/bin/env python3
"""
Test script to verify Tango change events are working for the iTest PSU
"""

import time
import taurus
import tango

def test_change_events():
    """Test that change events are working correctly"""
    print("=== Testing Tango Change Events ===")
    
    event_count = 0
    received_events = []
    
    def event_callback(evt_src, evt_type, evt_data):
        nonlocal event_count, received_events
        try:
            event_count += 1
            attr_name = evt_data.attr_name.split('/')[-1]
            value = evt_data.attr_value.value if evt_data.attr_value else None
            timestamp = time.time()
            
            event_info = {
                'count': event_count,
                'attr': attr_name,
                'value': value,
                'timestamp': timestamp,
                'error': evt_data.err if hasattr(evt_data, 'err') else None
            }
            received_events.append(event_info)
            
            print(f"Event #{event_count}: {attr_name} = {value}")
            
        except Exception as e:
            print(f"Error processing event: {e}")
    
    try:
        dev = taurus.Device('elyse/pdu/itest')
        print(f"Device: {dev}")
        print(f"Device state: {dev.state}")
        
        # Subscribe to change events
        print("\n1. Subscribing to change events...")
        attributes = ['states', 'currents_meas', 'currents_setpoint']
        
        for attr in attributes:
            try:
                print(f"   Subscribing to {attr}...")
                dev.subscribe_event(attr, tango.EventType.CHANGE_EVENT, event_callback)
                print(f"   ✓ Subscribed to {attr}")
            except Exception as e:
                print(f"   ✗ Failed to subscribe to {attr}: {e}")
        
        print(f"\n2. Waiting 2 seconds for initial events...")
        time.sleep(2)
        print(f"   Events received so far: {event_count}")
        
        # Test 1: Change a current setpoint
        print(f"\n3. Testing setpoint change event...")
        print("   Setting slot 1 current to 0.015A...")
        try:
            dev.command_inout('set_current', [1.0, 0.015])
            print("   ✓ Command sent")
        except Exception as e:
            print(f"   ✗ Command failed: {e}")
        
        time.sleep(1)
        print(f"   Events received after setpoint change: {event_count}")
        
        # Test 2: Change an output state
        print(f"\n4. Testing state change event...")
        print("   Turning OFF slot 1...")
        try:
            dev.command_inout('set_output_state', [1, 0])
            print("   ✓ Command sent")
        except Exception as e:
            print(f"   ✗ Command failed: {e}")
        
        time.sleep(1)
        print(f"   Events received after state change: {event_count}")
        
        # Test 3: Turn back on
        print(f"\n5. Testing another state change...")
        print("   Turning ON slot 1...")
        try:
            dev.command_inout('set_output_state', [1, 1])
            print("   ✓ Command sent")
        except Exception as e:
            print(f"   ✗ Command failed: {e}")
        
        time.sleep(2)
        print(f"   Final event count: {event_count}")
        
        # Summary
        print(f"\n=== Event Summary ===")
        print(f"Total events received: {event_count}")
        
        if received_events:
            print("\nRecent events:")
            for evt in received_events[-5:]:  # Show last 5 events
                print(f"  {evt['count']:2d}. {evt['attr']:20s} = {evt['value']}")
        
        if event_count >= 3:
            print("✓ Change events are working correctly!")
        elif event_count >= 1:
            print("⚠️ Some change events working, but may need improvement")
        else:
            print("✗ No change events received - check configuration")
    
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n=== Test Complete ===")

if __name__ == "__main__":
    test_change_events()