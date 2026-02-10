#!/usr/bin/env python
"""
Stress test for OWIS PS90 Axis 2
Performs 200 random movements between 0 and -600 with 4 second wait at each position
"""

import random
import time
from tango import DeviceProxy

# Configuration
DEVICE_NAME = "tango://localhost:10000/manip/general/DS_OWIS_PS90"  # Adjust to your Tango device name
AXIS = 2
MIN_POSITION = -600.0
MAX_POSITION = 0.0
NUM_MOVES = 200
WAIT_TIME = 4.0  # seconds to wait at each position

def log(msg, indent=0):
    """Print message with timestamp and optional indentation"""
    timestamp = time.strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[{timestamp}] {prefix}{msg}")

def main():
    log("=" * 70)
    log(f"=== OWIS PS90 Axis {AXIS} Stress Test ===")
    log("=" * 70)
    log(f"Device: {DEVICE_NAME}")
    log(f"Movements: {NUM_MOVES}")
    log(f"Range: {MIN_POSITION} to {MAX_POSITION}")
    log(f"Wait time: {WAIT_TIME}s per position")
    log("")
    
    # Connect to device
    log("Connecting to Tango device...")
    try:
        device = DeviceProxy(DEVICE_NAME)
        log(f"✓ Connected to device: {device.name()}", 1)
        
        state = device.state()
        log(f"Device state: {state}", 1)
        log(f"Device status: {device.status()}", 1)
    except Exception as e:
        log(f"✗ ERROR: Could not connect to device: {e}", 1)
        return
    
    log("")
    
    # Ensure device is ON
    log("Ensuring device is ON...")
    try:
        device.ensure_on()
        state = device.state()
        log(f"✓ Device state after ensure_on: {state}", 1)
    except Exception as e:
        log(f"✗ ERROR: Could not turn on device: {e}", 1)
        return
    
    log("")
    
    # Get initial position
    log(f"Reading initial position of axis {AXIS}...")
    try:
        initial_pos = device.read_position_axis(AXIS)
        log(f"✓ Initial position: {initial_pos:.3f} mm", 1)
    except Exception as e:
        log(f"✗ ERROR: Could not read initial position: {e}", 1)
        return
    
    log("")
    
    # Generate random positions
    positions = [random.uniform(MIN_POSITION, MAX_POSITION) for _ in range(NUM_MOVES)]
    
    log("=" * 70)
    log(f"Starting stress test with {NUM_MOVES} movements...")
    log("=" * 70)
    log("")
    
    success_count = 0
    error_count = 0
    start_time = time.time()
    
    for i, target_pos in enumerate(positions, 1):
        log("-" * 70)
        log(f"MOVE {i}/{NUM_MOVES}: Target position = {target_pos:.3f} mm")
        log("-" * 70)
        
        try:
            # Get current position
            log("Reading current position...", 1)
            current_pos = device.read_position_axis(AXIS)
            log(f"Current position: {current_pos:.3f} mm", 2)
            
            # Calculate move parameters
            distance = target_pos - current_pos
            move_direction = "forward" if distance > 0 else "backward"
            abs_distance = abs(distance)
            
            log(f"Move direction: {move_direction}", 2)
            log(f"Distance to travel: {abs_distance:.3f} mm", 2)
            
            # Check if already at target
            if abs_distance < 0.1:
                log("Already at target position (within 0.1mm), skipping move", 2)
                success_count += 1
                log("")
                continue
            
            log("")
            
            # Execute move command
            log(f"Executing move_axis command: move_axis([{AXIS}, {target_pos:.3f}])", 1)
            move_start = time.time()
            
            result = device.move_axis([AXIS, target_pos])
            
            log(f"move_axis returned: '{result}'", 2)
            
            if result != "0":
                log(f"✗ WARNING: move_axis did not return '0', got: {result}", 2)
            else:
                log("✓ Move command accepted", 2)
            
            log("")
            
            # Wait for movement to complete
            log("Waiting for movement to complete...", 1)
            move_timeout = 30.0
            position_tolerance = 0.5  # mm
            check_interval = 0.5  # seconds
            checks = 0
            
            while time.time() - move_start < move_timeout:
                time.sleep(check_interval)
                checks += 1
                
                new_pos = device.read_position_axis(AXIS)
                position_error = abs(new_pos - target_pos)
                
                # Only log every 5th check to reduce spam
                if checks % 5 == 0 or position_error < position_tolerance:
                    log(f"Check {checks}: Position = {new_pos:.3f} mm, Error = {position_error:.3f} mm", 2)
                
                # Check if we reached the target
                if position_error < position_tolerance:
                    elapsed = time.time() - move_start
                    log(f"✓ Target reached in {elapsed:.2f}s after {checks} checks", 2)
                    break
            else:
                # Timeout occurred
                elapsed = time.time() - move_start
                log(f"✗ WARNING: Move timeout after {elapsed:.2f}s", 2)
            
            log("")
            
            # Verify final position
            log("Verifying final position...", 1)
            final_pos = device.read_position_axis(AXIS)
            position_error = abs(final_pos - target_pos)
            
            log(f"Target position: {target_pos:.3f} mm", 2)
            log(f"Final position:  {final_pos:.3f} mm", 2)
            log(f"Position error:  {position_error:.3f} mm", 2)
            
            if position_error > 1.0:
                log(f"✗ WARNING: Large position error detected!", 2)
            else:
                log(f"✓ Position error acceptable", 2)
            
            log("")
            
            # Wait at position
            log(f"Waiting {WAIT_TIME}s at position {final_pos:.3f} mm...", 1)
            time.sleep(WAIT_TIME)
            log("✓ Wait complete", 2)
            
            success_count += 1
            
        except Exception as e:
            error_count += 1
            log(f"✗ ERROR on move {i}: {e}", 1)
            log(f"Exception type: {type(e).__name__}", 2)
            import traceback
            log("Stack trace:", 2)
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    log(line, 3)
            
            log("", 1)
            log("Attempting to recover...", 1)
            time.sleep(2)
            
            # Try to recover
            try:
                log("Calling ensure_on()...", 2)
                device.ensure_on()
                log("✓ ensure_on() succeeded", 2)
            except Exception as e2:
                log(f"✗ ensure_on() failed: {e2}", 2)
        
        log("")
    
    # Test summary
    end_time = time.time()
    total_time = end_time - start_time
    
    log("=" * 70)
    log("=== TEST COMPLETE ===")
    log("=" * 70)
    log(f"Total positions tested: {NUM_MOVES}")
    log(f"Successful moves: {success_count}")
    log(f"Failed moves: {error_count}")
    log(f"Success rate: {100 * success_count / NUM_MOVES:.1f}%")
    log(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    log(f"Average time per move: {total_time/NUM_MOVES:.1f}s")
    log("")
    
    # Get final position
    try:
        final_pos = device.read_position_axis(AXIS)
        log(f"Final position: {final_pos:.3f} mm")
    except Exception as e:
        log(f"Could not read final position: {e}")
    
    log("")
    
    # Get final device state
    try:
        final_state = device.state()
        log(f"Final device state: {final_state}")
    except:
        pass
    
    log("=" * 70)
    
    if error_count == 0:
        log("✓ ALL TESTS PASSED!")
    else:
        log(f"✗ {error_count} TEST(S) FAILED")
    
    log("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("")
        log("")
        log("✗ Test interrupted by user (Ctrl+C)")
    except Exception as e:
        log("")
        log("")
        log(f"✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
