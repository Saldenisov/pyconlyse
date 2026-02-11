#!/usr/bin/env python
"""
Direct DLL stress test for OWIS PS90 - bypasses Tango Device Server
Tests if concurrent position reads during movement cause issues (mutex necessity test)
"""

import ctypes
from ctypes import windll, c_long, c_double
import random
import time
import threading
import os
import sys

# Configuration
COM_PORT = 4  # Same as DS_OWIS_PS90 default
AXIS = 2
MIN_POSITION = -800.0  # From Tango config: limit_min=-900, using safe margin
MAX_POSITION = 0.0     # From Tango config: limit_max=100, using safe margin
NUM_MOVES = 200  # Full stress test
CONTROL_UNIT = 1
POSITION_READ_INTERVAL = 0.1  # 100ms between position reads

# Stage parameters from Tango DB for axis 2 (Delay line for SC)
# These convert between motor increments and mm
PITCH = 5.0        # Spindle pitch in mm per revolution
REVOLUTION = 200   # Steps/increments per motor revolution  
GEAR_RATIO = 1.0   # Gear reduction ratio


class OWISDirect:
    """Direct wrapper for OWIS PS90 DLL functions"""
    
    def __init__(self, dll_path=None):
        if dll_path is None:
            # Try to find DLL in drivers folder
            script_dir = os.path.dirname(os.path.abspath(__file__))
            dll_path = os.path.join(script_dir, "drivers", "ps90_64.dll")
        
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL not found: {dll_path}")
        
        # Add DLL directory to search path (Python 3.8+)
        dll_dir = os.path.dirname(dll_path)
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_dir)
        
        self.lib = windll.LoadLibrary(dll_path)
        
        # Set return types for functions that return double
        self.lib.PS90_GetPositionEx.restype = c_double
        
        self.connected = False
        self.control_unit = CONTROL_UNIT
    
    def connect(self, com_port, baudrate=115200):
        """Connect to controller"""
        result = self.lib.PS90_Connect(
            c_long(self.control_unit),
            c_long(0),  # Interface: serial/USB
            c_long(com_port),
            c_long(baudrate),
            c_long(0), c_long(0), c_long(0), c_long(0)
        )
        self.connected = (result == 0)
        return result
    
    def simple_connect(self):
        """Auto-detect and connect to first available controller"""
        result = self.lib.PS90_SimpleConnect(c_long(self.control_unit), b"")
        self.connected = (result == 0)
        return result
    
    def disconnect(self):
        """Disconnect from controller"""
        result = self.lib.PS90_Disconnect(c_long(self.control_unit))
        self.connected = False
        return result
    
    def motor_init(self, axis):
        """Initialize axis"""
        return self.lib.PS90_MotorInit(c_long(self.control_unit), c_long(axis))
    
    def motor_on(self, axis):
        """Turn motor on"""
        return self.lib.PS90_MotorOn(c_long(self.control_unit), c_long(axis))
    
    def motor_off(self, axis):
        """Turn motor off"""
        return self.lib.PS90_MotorOff(c_long(self.control_unit), c_long(axis))
    
    def get_position(self, axis):
        """Get current position (returns double)"""
        return self.lib.PS90_GetPositionEx(c_long(self.control_unit), c_long(axis))
    
    def get_move_state(self, axis):
        """Get move state: >0 = moving, 0 = stopped"""
        return self.lib.PS90_GetMoveState(c_long(self.control_unit), c_long(axis))
    
    def get_axis_state(self, axis):
        """Get axis state: 0=not active, 1=not init, 2=off, 3=on"""
        return self.lib.PS90_GetAxisState(c_long(self.control_unit), c_long(axis))
    
    def set_target_mode(self, axis, mode):
        """Set target mode: 0=relative, 1=absolute"""
        return self.lib.PS90_SetTargetMode(c_long(self.control_unit), c_long(axis), c_long(mode))
    
    def set_target(self, axis, position):
        """Set target position"""
        return self.lib.PS90_SetTargetEx(c_long(self.control_unit), c_long(axis), c_double(position))
    
    def go_target(self, axis):
        """Start movement to target"""
        return self.lib.PS90_GoTarget(c_long(self.control_unit), c_long(axis))
    
    def stop(self, axis):
        """Stop axis movement"""
        return self.lib.PS90_Stop(c_long(self.control_unit), c_long(axis))
    
    def set_stage_attributes(self, axis, pitch, inc_rev, gear_ratio):
        """Set stage attributes for unit conversion (inc <-> mm)"""
        return self.lib.PS90_SetStageAttributes(
            c_long(self.control_unit),
            c_long(axis),
            c_double(pitch),
            c_long(int(inc_rev)),
            c_double(gear_ratio)
        )


def log(msg, indent=0):
    """Print message with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[{timestamp}] {prefix}{msg}")


class PositionReader(threading.Thread):
    """Background thread that continuously reads position during movement"""
    
    def __init__(self, owis, axis):
        super().__init__(daemon=True)
        self.owis = owis
        self.axis = axis
        self.running = False
        self.positions = []
        self.errors = []
        self.read_count = 0
    
    def start_reading(self):
        self.running = True
        self.positions = []
        self.errors = []
        self.read_count = 0
        if not self.is_alive():
            self.start()
    
    def stop_reading(self):
        self.running = False
    
    def run(self):
        while True:
            if self.running:
                try:
                    pos = self.owis.get_position(self.axis)
                    self.positions.append((time.time(), pos))
                    self.read_count += 1
                except Exception as e:
                    self.errors.append((time.time(), str(e)))
            time.sleep(POSITION_READ_INTERVAL)


def main():
    log("=" * 70)
    log("=== OWIS PS90 Direct DLL Stress Test (Mutex Test) ===")
    log("=" * 70)
    log(f"COM Port: {COM_PORT}")
    log(f"Axis: {AXIS}")
    log(f"Movements: {NUM_MOVES}")
    log(f"Range: {MIN_POSITION} to {MAX_POSITION}")
    log(f"Position read interval: {POSITION_READ_INTERVAL}s")
    log("")
    
    # Initialize DLL wrapper
    log("Loading OWIS DLL...")
    try:
        owis = OWISDirect()
        log("✓ DLL loaded successfully", 1)
    except Exception as e:
        log(f"✗ Failed to load DLL: {e}", 1)
        return
    
    # Connect - try SimpleConnect first (auto-detect), fall back to specific port
    log("Connecting (auto-detect)...")
    result = owis.simple_connect()
    if result != 0:
        log(f"Auto-detect failed ({result}), trying COM{COM_PORT}...", 1)
        result = owis.connect(COM_PORT)
        if result != 0:
            log(f"✗ Connection failed with code: {result}", 1)
            log("  5 = no response from control unit", 1)
            log("  Check: Is controller powered on? Is COM port correct?", 1)
            return
    log("✓ Connected", 1)
    
    try:
        # Initialize axis
        log(f"Initializing axis {AXIS}...")
        result = owis.motor_init(AXIS)
        if result != 0:
            log(f"✗ Motor init failed: {result}", 1)
            return
        log("✓ Motor initialized", 1)
        
        # Set stage attributes for proper unit conversion (increments <-> mm)
        log(f"Setting stage attributes (pitch={PITCH}, rev={REVOLUTION}, ratio={GEAR_RATIO})...")
        result = owis.set_stage_attributes(AXIS, PITCH, REVOLUTION, GEAR_RATIO)
        if result != 0:
            log(f"✗ Set stage attributes failed: {result}", 1)
            return
        log("✓ Stage attributes configured", 1)
        
        # Set absolute positioning mode
        result = owis.set_target_mode(AXIS, 1)  # 1 = absolute
        if result != 0:
            log(f"✗ Set target mode failed: {result}", 1)
            return
        log("✓ Target mode set to absolute", 1)
        
        # Get initial position
        initial_pos = owis.get_position(AXIS)
        log(f"Initial position: {initial_pos:.3f}", 1)
        
        # Check axis state
        axis_state = owis.get_axis_state(AXIS)
        log(f"Axis state: {axis_state} (3=ON)", 1)
        
        # Turn motor on if needed
        if axis_state != 3:
            log("Turning motor on...")
            owis.motor_on(AXIS)
            time.sleep(0.2)
        
        log("")
        
        # Create position reader thread
        reader = PositionReader(owis, AXIS)
        
        # Generate random positions
        positions = [random.uniform(MIN_POSITION, MAX_POSITION) for _ in range(NUM_MOVES)]
        
        log("=" * 70)
        log(f"Starting stress test with {NUM_MOVES} movements...")
        log("Background thread will read position every 100ms during movement")
        log("=" * 70)
        log("")
        
        success_count = 0
        error_count = 0
        total_reads = 0
        total_read_errors = 0
        start_time = time.time()
        
        for i, target_pos in enumerate(positions, 1):
            log("-" * 70)
            log(f"MOVE {i}/{NUM_MOVES}: Target = {target_pos:.3f} mm")
            log("-" * 70)
            
            try:
                current_pos = owis.get_position(AXIS)
                log(f"Current position: {current_pos:.3f} mm", 1)
                
                distance = abs(target_pos - current_pos)
                if distance < 0.1:
                    log("Already at target, skipping", 1)
                    success_count += 1
                    continue
                
                # Start position reader
                reader.start_reading()
                
                # Set target and start movement
                log(f"Setting target to {target_pos:.3f}...", 1)
                result = owis.set_target(AXIS, target_pos)
                if result != 0:
                    log(f"✗ Set target failed: {result}", 1)
                    error_count += 1
                    reader.stop_reading()
                    continue
                
                log("Starting movement...", 1)
                move_start = time.time()
                result = owis.go_target(AXIS)
                if result != 0:
                    log(f"✗ Go target failed: {result}", 1)
                    error_count += 1
                    reader.stop_reading()
                    continue
                
                # Wait for movement to complete (poll GetMoveState)
                timeout = 60.0
                while owis.get_move_state(AXIS) > 0:
                    if time.time() - move_start > timeout:
                        log("✗ Movement timeout!", 1)
                        owis.stop(AXIS)
                        break
                    time.sleep(0.1)
                
                # Stop position reader
                reader.stop_reading()
                time.sleep(0.1)  # Let last reads complete
                
                move_time = time.time() - move_start
                final_pos = owis.get_position(AXIS)
                position_error = abs(final_pos - target_pos)
                
                log(f"Movement completed in {move_time:.2f}s", 1)
                log(f"Final position: {final_pos:.3f} mm", 1)
                log(f"Position error: {position_error:.3f} mm", 1)
                log(f"Position reads during move: {reader.read_count}", 1)
                log(f"Read errors during move: {len(reader.errors)}", 1)
                
                if reader.errors:
                    for err_time, err_msg in reader.errors:
                        log(f"  READ ERROR: {err_msg}", 2)
                
                total_reads += reader.read_count
                total_read_errors += len(reader.errors)
                
                if position_error < 1.0:
                    log("✓ Move successful", 1)
                    success_count += 1
                else:
                    log("✗ Large position error!", 1)
                    error_count += 1
                
            except Exception as e:
                log(f"✗ Exception: {e}", 1)
                error_count += 1
                reader.stop_reading()
            
            log("")
        
        # Summary
        total_time = time.time() - start_time
        
        log("=" * 70)
        log("=== TEST SUMMARY ===")
        log("=" * 70)
        log(f"Total moves: {NUM_MOVES}")
        log(f"Successful: {success_count}")
        log(f"Failed: {error_count}")
        log(f"Success rate: {100 * success_count / NUM_MOVES:.1f}%")
        log(f"Total time: {total_time:.1f}s")
        log("")
        log("=== CONCURRENT READ STATISTICS ===")
        log(f"Total position reads during movements: {total_reads}")
        log(f"Total read errors: {total_read_errors}")
        if total_reads > 0:
            log(f"Error rate: {100 * total_read_errors / total_reads:.2f}%")
        log("")
        
        if total_read_errors == 0:
            log("✓ NO CONCURRENT READ ERRORS - Mutex may not be necessary for position reads")
        else:
            log(f"✗ {total_read_errors} CONCURRENT READ ERRORS - Mutex IS necessary")
        
        log("=" * 70)
        
        # Turn motor off
        owis.motor_off(AXIS)
        
    finally:
        # Always disconnect
        log("Disconnecting...")
        owis.disconnect()
        log("✓ Disconnected")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("")
        log("✗ Test interrupted by user")
    except Exception as e:
        log(f"✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
