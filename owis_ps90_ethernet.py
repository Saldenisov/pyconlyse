"""
OWIS PS90 Controller - Ethernet Communication via ps90.dll

This module provides a Python interface to connect to OWIS PS90 controllers
over Ethernet using the official ps90.dll SDK.

Key finding: Use PS90_SimpleConnect with the controller's serial number
to connect to a specific controller on the network.

Example:
    controller = OwisPS90Ethernet(serial_number="25010013")
    controller.connect()
    print(controller.get_position(axis=1))
    controller.disconnect()
"""
import ctypes
from ctypes import windll, c_double, c_long, create_string_buffer
import os
import sys
from pathlib import Path


class OwisPS90Ethernet:
    """Interface for OWIS PS90 controller via Ethernet using ps90.dll"""
    
    # Default DLL paths to search
    DEFAULT_DLL_PATHS = [
        r"C:\Program Files (x86)\OWISoft\exe\x64\Release\ps90.dll",
        r"C:\Program Files (x86)\OWISoft\Application\ps90.dll",
        Path(__file__).parent / "DeviceServers" / "motion" / "owis" / "drivers" / "ps90_64.dll",
    ]
    
    def __init__(self, serial_number: str, control_unit_id: int = 1, dll_path: str = None):
        """
        Initialize OWIS PS90 Ethernet connection.
        
        Args:
            serial_number: The serial number of the controller (e.g., "25010013")
            control_unit_id: Controller slot index 1-10 (default: 1)
            dll_path: Optional path to ps90.dll
        """
        self.serial_number = serial_number
        self.control_unit_id = control_unit_id
        self.dll_path = dll_path
        self.dll = None
        self.connected = False
        
    def _find_dll(self) -> str:
        """Find ps90.dll in common locations"""
        if self.dll_path and os.path.exists(self.dll_path):
            return self.dll_path
            
        for path in self.DEFAULT_DLL_PATHS:
            if os.path.exists(path):
                return str(path)
                
        raise FileNotFoundError("ps90.dll not found. Please specify dll_path.")
    
    def _load_dll(self):
        """Load ps90.dll and configure function signatures"""
        dll_path = self._find_dll()
        
        # Add DLL directory to PATH for dependencies
        dll_dir = os.path.dirname(dll_path)
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
        
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_dir)
        
        self.dll = windll.LoadLibrary(dll_path)
        
        # Set return types for functions returning double
        self.dll.PS90_GetPositionEx.restype = c_double
        self.dll.PS90_GetTargetEx.restype = c_double
        self.dll.PS90_GetPosF.restype = c_double
        self.dll.PS90_GetActF.restype = c_double
        
        return dll_path
    
    def connect(self) -> bool:
        """
        Connect to the controller using its serial number.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self.connected:
            return True
            
        dll_path = self._load_dll()
        print(f"Loaded DLL: {dll_path}")
        
        # Connect using serial number - this works for Ethernet discovery
        result = self.dll.PS90_SimpleConnect(
            self.control_unit_id, 
            self.serial_number.encode('ascii')
        )
        
        if result == 0:
            self.connected = True
            print(f"Connected to PS90 (Serial: {self.serial_number})")
            return True
        else:
            error_msg = self._get_connect_error(result)
            print(f"Connection failed: {error_msg}")
            return False
    
    def disconnect(self):
        """Disconnect from the controller"""
        if self.connected and self.dll:
            self.dll.PS90_Disconnect(self.control_unit_id)
            self.connected = False
            print("Disconnected.")
    
    def get_serial_number(self) -> str:
        """Read serial number from controller"""
        self._check_connected()
        buf = create_string_buffer(64)
        self.dll.PS90_GetSerNumber(self.control_unit_id, buf, 64)
        return buf.value.decode('utf-8')
    
    def get_firmware_version(self) -> str:
        """Read firmware version from controller"""
        self._check_connected()
        buf = create_string_buffer(64)
        self.dll.PS90_GetBoardVersion(self.control_unit_id, buf, 64)
        return buf.value.decode('utf-8')
    
    def get_axis_state(self, axis: int) -> int:
        """
        Get axis state.
        
        Returns:
            0: axis not active
            1: axis not initialized  
            2: axis switched off
            3: axis active, initialized and switched on
        """
        self._check_connected()
        return self.dll.PS90_GetAxisState(self.control_unit_id, axis)
    
    def get_position(self, axis: int) -> float:
        """Get current position of axis in configured units"""
        self._check_connected()
        return self.dll.PS90_GetPositionEx(self.control_unit_id, axis)
    
    def motor_init(self, axis: int) -> bool:
        """Initialize axis motor"""
        self._check_connected()
        result = self.dll.PS90_MotorInit(self.control_unit_id, axis)
        return result == 0
    
    def motor_on(self, axis: int) -> bool:
        """Switch axis motor on"""
        self._check_connected()
        result = self.dll.PS90_MotorOn(self.control_unit_id, axis)
        return result == 0
    
    def motor_off(self, axis: int) -> bool:
        """Switch axis motor off"""
        self._check_connected()
        result = self.dll.PS90_MotorOff(self.control_unit_id, axis)
        return result == 0
    
    def set_target_mode(self, axis: int, absolute: bool = True) -> bool:
        """
        Set target mode.
        
        Args:
            axis: Axis number (1-9)
            absolute: True for absolute positioning, False for relative
        """
        self._check_connected()
        mode = 1 if absolute else 0
        result = self.dll.PS90_SetTargetMode(self.control_unit_id, axis, mode)
        return result == 0
    
    def set_velocity(self, axis: int, velocity: float) -> bool:
        """Set positioning velocity in configured units/s"""
        self._check_connected()
        result = self.dll.PS90_SetPosFEx(self.control_unit_id, axis, c_double(velocity))
        return result == 0
    
    def move_to(self, axis: int, position: float, wait: bool = False) -> bool:
        """
        Move axis to position.
        
        Args:
            axis: Axis number (1-9)
            position: Target position in configured units
            wait: If True, block until movement completes
        """
        self._check_connected()
        
        # Set target
        result = self.dll.PS90_SetTargetEx(self.control_unit_id, axis, c_double(position))
        if result != 0:
            return False
            
        # Start movement
        result = self.dll.PS90_GoTarget(self.control_unit_id, axis)
        if result != 0:
            return False
            
        if wait:
            import time
            while self.is_moving(axis):
                time.sleep(0.1)
                
        return True
    
    def is_moving(self, axis: int) -> bool:
        """Check if axis is currently moving"""
        self._check_connected()
        state = self.dll.PS90_GetMoveState(self.control_unit_id, axis)
        return state > 0
    
    def stop(self, axis: int) -> bool:
        """Stop axis movement"""
        self._check_connected()
        result = self.dll.PS90_Stop(self.control_unit_id, axis)
        return result == 0
    
    def go_reference(self, axis: int, mode: int = 4) -> bool:
        """
        Start reference run (homing).
        
        Args:
            axis: Axis number (1-9)
            mode: Reference mode (default 4)
        """
        self._check_connected()
        result = self.dll.PS90_GoRef(self.control_unit_id, axis, mode)
        return result == 0
    
    def set_stage_attributes(self, axis: int, pitch: float, steps_per_rev: int, 
                            gear_ratio: float = 1.0) -> bool:
        """
        Set stage attributes for unit conversion.
        
        Args:
            axis: Axis number (1-9)
            pitch: Distance per revolution (e.g., 1.0 mm)
            steps_per_rev: Steps/pulses per motor revolution
            gear_ratio: Gear reduction ratio
        """
        self._check_connected()
        result = self.dll.PS90_SetStageAttributes(
            self.control_unit_id, axis,
            c_double(pitch), steps_per_rev, c_double(gear_ratio)
        )
        return result == 0
    
    def _check_connected(self):
        """Raise exception if not connected"""
        if not self.connected:
            raise RuntimeError("Not connected to controller. Call connect() first.")
    
    def _get_connect_error(self, code: int) -> str:
        """Get human-readable connection error message"""
        errors = {
            0: "Success",
            -1: "Function error (invalid parameters)",
            -3: "Invalid serial port",
            -4: "Access denied (port busy)",
            -5: "No response from controller",
            -7: "Controller with specified serial not found",
            -8: "No connection to Modbus/TCP",
            -9: "No connection to TCP/IP socket",
        }
        return errors.get(code, f"Unknown error ({code})")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# Example usage
if __name__ == "__main__":
    # Connect to the new controller at 10.20.30.134
    with OwisPS90Ethernet(serial_number="25010013") as controller:
        print(f"\nSerial: {controller.get_serial_number()}")
        print(f"Firmware: {controller.get_firmware_version()}")
        
        for axis in range(1, 5):
            state = controller.get_axis_state(axis)
            pos = controller.get_position(axis)
            state_names = {0: "not active", 1: "not initialized", 2: "off", 3: "on"}
            print(f"Axis {axis}: state={state_names.get(state, state)}, position={pos}")
