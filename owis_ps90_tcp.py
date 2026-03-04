"""
OWIS PS90 Controller - Direct TCP/IP Communication (No DLL required)

This module provides direct Ethernet communication with OWIS PS90 controllers
via raw TCP socket on port 8777. No USB connection or ps90.dll required.

The PS90 accepts ASCII commands terminated with CR (\\r).
Commands are automatically converted to uppercase by the controller.

Example:
    controller = OwisPS90TCP(ip="10.20.30.134")
    controller.connect()
    print(controller.get_version())
    controller.motor_init(axis=1)
    controller.move_to(axis=1, position=10.0)
    controller.disconnect()
"""
import socket
import time
from typing import Optional, Tuple, Union


class OwisPS90TCP:
    """Direct TCP/IP interface to OWIS PS90 controller on port 8777."""
    
    DEFAULT_PORT = 8777
    DEFAULT_TIMEOUT = 5.0
    COMMAND_DELAY = 0.02  # Delay between commands (SDK uses 0.01-0.05s)
    
    def __init__(self, ip: str, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize connection parameters.
        
        Args:
            ip: IP address of the controller (e.g., "10.20.30.134")
            port: TCP port (default: 8777)
            timeout: Socket timeout in seconds
        """
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None
        
    @property
    def connected(self) -> bool:
        return self._socket is not None
    
    def connect(self) -> bool:
        """
        Connect to the controller.
        
        Returns:
            True if connection successful
        """
        if self.connected:
            return True
            
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.ip, self.port))
            print(f"Connected to OWIS PS90 at {self.ip}:{self.port}")
            return True
        except Exception as e:
            self._socket = None
            print(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the controller."""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None
            print("Disconnected.")
    
    def send_command(self, command: str, expect_response: bool = True) -> str:
        """
        Send ASCII command and receive response.
        
        Args:
            command: Command string (CR will be appended)
            expect_response: Whether to wait for response
            
        Returns:
            Response string (stripped of whitespace)
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
            
        # Send command with CR terminator
        cmd_bytes = (command + "\r").encode("ascii")
        self._socket.sendall(cmd_bytes)
        
        time.sleep(self.COMMAND_DELAY)
        
        if not expect_response:
            return ""
            
        # Read response
        try:
            response = self._socket.recv(1024).decode("ascii", errors="replace")
            return response.strip()
        except socket.timeout:
            return ""
    
    def query(self, command: str) -> str:
        """Send query command and return response."""
        return self.send_command(command, expect_response=True)
    
    # ==================== System Commands ====================
    
    def get_serial_number(self) -> str:
        """Get controller serial number."""
        return self.query("?SERNUM")
    
    def get_version(self) -> str:
        """Get firmware version."""
        return self.query("?VERSION")
    
    def get_error(self) -> int:
        """Get error code (0 = no error)."""
        resp = self.query("?ERR")
        try:
            return int(resp)
        except:
            return -1
    
    def clear_error(self):
        """Clear error state."""
        self.send_command("CLERR", expect_response=False)
    
    # ==================== Axis Commands ====================
    
    def motor_init(self, axis: int) -> bool:
        """
        Initialize axis motor.
        
        Args:
            axis: Axis number (1-9)
        """
        resp = self.query(f"INIT{axis}")
        return "OK" in resp.upper() or resp == ""
    
    def motor_on(self, axis: int) -> bool:
        """Switch axis motor on."""
        resp = self.query(f"MON{axis}")
        return "OK" in resp.upper() or resp == ""
    
    def motor_off(self, axis: int) -> bool:
        """Switch axis motor off."""
        resp = self.query(f"MOFF{axis}")
        return "OK" in resp.upper() or resp == ""
    
    def get_axis_state(self, axis: int) -> int:
        """
        Get axis state.
        
        Returns:
            0: not active, 1: not initialized, 2: off, 3: on
        """
        resp = self.query(f"?AXIS{axis}")
        try:
            return int(resp)
        except:
            return -1
    
    def get_position(self, axis: int) -> float:
        """Get current position in increments."""
        resp = self.query(f"?CNT{axis}")
        try:
            return float(resp)
        except:
            return 0.0
    
    def set_position(self, axis: int, position: int):
        """Set position counter value."""
        self.send_command(f"CNT{axis}={position}", expect_response=False)
    
    def get_target(self, axis: int) -> float:
        """Get target position."""
        resp = self.query(f"?PSET{axis}")
        try:
            return float(resp)
        except:
            return 0.0
    
    def set_target(self, axis: int, position: float):
        """Set target position."""
        self.send_command(f"PSET{axis}={int(position)}", expect_response=False)
    
    def set_target_mode(self, axis: int, absolute: bool = True):
        """
        Set target mode.
        
        Args:
            axis: Axis number (1-9)
            absolute: True for absolute, False for relative
        """
        mode = 1 if absolute else 0
        self.send_command(f"ABSOL{axis}={mode}", expect_response=False)
    
    def go_target(self, axis: int) -> bool:
        """Start movement to target."""
        resp = self.query(f"PGO{axis}")
        return "OK" in resp.upper() or resp == ""
    
    def stop(self, axis: int):
        """Stop axis movement."""
        self.send_command(f"STOP{axis}", expect_response=False)
    
    def is_moving(self, axis: int) -> bool:
        """Check if axis is moving."""
        resp = self.query(f"?MPTS{axis}")
        try:
            return int(resp) > 0
        except:
            return False
    
    def go_reference(self, axis: int, mode: int = 4):
        """Start reference run (homing)."""
        self.send_command(f"REF{axis}={mode}", expect_response=False)
    
    # ==================== Velocity/Acceleration ====================
    
    def set_velocity(self, axis: int, velocity: int):
        """Set positioning velocity in Hz."""
        self.send_command(f"PVEL{axis}={velocity}", expect_response=False)
    
    def get_velocity(self, axis: int) -> int:
        """Get positioning velocity in Hz."""
        resp = self.query(f"?PVEL{axis}")
        try:
            return int(resp)
        except:
            return 0
    
    def set_acceleration(self, axis: int, accel: int):
        """Set acceleration."""
        self.send_command(f"ACC{axis}={accel}", expect_response=False)
    
    # ==================== High-Level Methods ====================
    
    def move_to(self, axis: int, position: float, wait: bool = False) -> bool:
        """
        Move axis to position.
        
        Args:
            axis: Axis number (1-9)
            position: Target position
            wait: If True, block until movement completes
        """
        self.set_target_mode(axis, absolute=True)
        self.set_target(axis, position)
        success = self.go_target(axis)
        
        if wait and success:
            while self.is_moving(axis):
                time.sleep(0.1)
                
        return success
    
    def move_relative(self, axis: int, distance: float, wait: bool = False) -> bool:
        """
        Move axis by relative distance.
        
        Args:
            axis: Axis number (1-9)
            distance: Distance to move (+ or -)
            wait: If True, block until movement completes
        """
        self.set_target_mode(axis, absolute=False)
        self.set_target(axis, distance)
        success = self.go_target(axis)
        
        if wait and success:
            while self.is_moving(axis):
                time.sleep(0.1)
                
        return success
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# Example usage
if __name__ == "__main__":
    # Connect to controller at 10.20.30.134:8777 (direct Ethernet, no USB)
    with OwisPS90TCP(ip="10.20.30.134") as ctrl:
        print(f"\nSerial: {ctrl.get_serial_number()}")
        print(f"Firmware: {ctrl.get_version()}")
        print(f"Error: {ctrl.get_error()}")
        
        for axis in range(1, 5):
            state = ctrl.get_axis_state(axis)
            pos = ctrl.get_position(axis)
            state_names = {0: "not active", 1: "not initialized", 2: "off", 3: "on", -1: "error"}
            print(f"Axis {axis}: state={state_names.get(state, state)}, position={pos}")
