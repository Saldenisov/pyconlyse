"""
Arduino TTL Trigger Controller for Avantes Spectrometers
=========================================================

This module provides an interface to control the Arduino-based TTL pulse
generator for synchronized Avantes spectrometer measurements.

The Arduino HTTP server provides three modes:
1. LAMP AND AVANTES - Triggers both flash lamp and spectrometers
2. ONLY AVANTES - Triggers only spectrometers (for background/dark)
3. OFF - Stops all TTL generation

Hardware Setup:
- Arduino with Ethernet shield
- IP: 10.20.30.47 (default, configurable)
- Port 80 (HTTP)
- TTL outputs on pins 7 (lamp) and 8 (Avantes)

Usage:
    from arduino_trigger_controller import ArduinoTriggerController
    
    # Create controller
    arduino = ArduinoTriggerController(ip="10.20.30.47")
    
    # Start TTL pulses for spectrometers only
    arduino.set_mode("ONLY AVANTES")
    
    # Check current state
    lamp_on, avantes_on = arduino.get_state()
    
    # Stop TTL generation
    arduino.set_mode("OFF")
"""

import requests
from bs4 import BeautifulSoup
from typing import Tuple, Optional
from enum import Enum


class ArduinoMode(Enum):
    """Arduino trigger modes."""
    LAMP_AND_AVANTES = "LAMP+AND+AVANTES"  # Matches arduino_sync_code.ino line 216
    ONLY_AVANTES = "ONLY+AVANTES"          # Matches arduino_sync_code.ino line 222
    OFF = "OFF"                             # Matches arduino_sync_code.ino line 228


class ArduinoTriggerController:
    """Controller for Arduino-based TTL pulse generator."""
    
    def __init__(self, ip: str = "10.20.30.47", port: int = 80, timeout: float = 2.0):
        """
        Initialize Arduino trigger controller.
        
        Parameters
        ----------
        ip : str, optional
            Arduino IP address (default: "10.20.30.47")
        port : int, optional
            Arduino HTTP port (default: 80)
        timeout : float, optional
            HTTP request timeout in seconds (default: 2.0)
        """
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{ip}:{port}"
        
        # Cached state
        self._lamp_enabled = False
        self._avantes_enabled = False
        self._last_mode = None
        
    def set_mode(self, mode: str) -> bool:
        """
        Set Arduino trigger mode.
        
        Parameters
        ----------
        mode : str
            One of:
            - "LAMP AND AVANTES" - Both lamp and spectrometers
            - "ONLY AVANTES" - Spectrometers only (background)
            - "OFF" - Stop all TTL generation
        
        Returns
        -------
        bool
            True if successful, False otherwise
        """
        # Convert mode string to URL-encoded format
        mode_map = {
            "LAMP AND AVANTES": ArduinoMode.LAMP_AND_AVANTES.value,
            "ONLY AVANTES": ArduinoMode.ONLY_AVANTES.value,
            "OFF": ArduinoMode.OFF.value,
        }
        
        if mode not in mode_map:
            print(f"Invalid mode: {mode}. Valid modes: {list(mode_map.keys())}")
            return False
        
        url_mode = mode_map[mode]
        url = f"{self.base_url}/?status={url_mode}"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                self._last_mode = mode
                # Update cached state
                self.get_state()
                return True
            else:
                print(f"Arduino returned status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Failed to communicate with Arduino: {e}")
            return False
    
    def get_state(self) -> Tuple[bool, bool]:
        """
        Get current Arduino TTL state by parsing HTML from arduino_sync_code.ino.
        
        Returns
        -------
        Tuple[bool, bool]
            (lamp_enabled, avantes_enabled)
            Returns (False, False) if communication fails
        """
        try:
            response = requests.get(self.base_url, timeout=self.timeout)
            
            if response.status_code != 200:
                return False, False
            
            # Parse HTML response
            html = response.text
            
            # The Arduino HTML contains status rows like:
            # <span class='on'>ON</span> or <span class='off'>OFF</span>
            # Look for the text content to determine state
            
            # Find lamp status (appears after "Flash Lamp (Pin 7)")
            lamp_on = "Flash Lamp (Pin 7)" in html and "class='on'>ON" in html
            if "Flash Lamp" in html:
                # Check if the next status span says ON or OFF
                lamp_idx = html.find("Flash Lamp (Pin 7)")
                if lamp_idx >= 0:
                    next_span = html[lamp_idx:lamp_idx+200]
                    lamp_on = "class='on'>ON" in next_span
            
            # Find Avantes status (appears after "Avantes (Pin 8)")
            avantes_on = "Avantes (Pin 8)" in html and "class='on'>ON" in html
            if "Avantes (Pin 8)" in html:
                # Check if the next status span says ON or OFF
                avantes_idx = html.find("Avantes (Pin 8)")
                if avantes_idx >= 0:
                    next_span = html[avantes_idx:avantes_idx+200]
                    avantes_on = "class='on'>ON" in next_span
            
            self._lamp_enabled = lamp_on
            self._avantes_enabled = avantes_on
            return self._lamp_enabled, self._avantes_enabled
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to get Arduino state: {e}")
            return False, False
    
    def start_lamp_and_spectrometers(self) -> bool:
        """
        Start TTL pulses for both lamp and spectrometers.
        
        Typical use: Sample measurement with flash lamp excitation
        
        Returns
        -------
        bool
            True if successful
        """
        return self.set_mode("LAMP AND AVANTES")
    
    def start_spectrometers_only(self) -> bool:
        """
        Start TTL pulses for spectrometers only (no lamp).
        
        Typical use: Background/dark measurement
        
        Returns
        -------
        bool
            True if successful
        """
        return self.set_mode("ONLY AVANTES")
    
    def stop_all(self) -> bool:
        """
        Stop all TTL generation.
        
        Returns
        -------
        bool
            True if successful
        """
        return self.set_mode("OFF")
    
    def is_connected(self) -> bool:
        """
        Check if Arduino is reachable.
        
        Returns
        -------
        bool
            True if Arduino responds to HTTP requests
        """
        try:
            response = requests.get(self.base_url, timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_status_string(self) -> str:
        """
        Get human-readable status string.
        
        Returns
        -------
        str
            Status description
        """
        lamp, avantes = self.get_state()
        
        if lamp and avantes:
            return "LAMP AND AVANTES (Sample mode)"
        elif avantes and not lamp:
            return "ONLY AVANTES (Background mode)"
        elif not lamp and not avantes:
            return "OFF (Idle)"
        else:
            return "UNKNOWN"
    
    @property
    def lamp_enabled(self) -> bool:
        """Check if lamp TTL is enabled (cached)."""
        return self._lamp_enabled
    
    @property
    def avantes_enabled(self) -> bool:
        """Check if Avantes TTL is enabled (cached)."""
        return self._avantes_enabled


# Convenience functions for quick access

def create_arduino_controller(ip: str = "10.20.30.47") -> ArduinoTriggerController:
    """
    Create an Arduino trigger controller with default settings.
    
    Parameters
    ----------
    ip : str, optional
        Arduino IP address
    
    Returns
    -------
    ArduinoTriggerController
        Controller instance
    """
    return ArduinoTriggerController(ip=ip)


def test_arduino_connection(ip: str = "10.20.30.47") -> bool:
    """
    Test Arduino connection.
    
    Parameters
    ----------
    ip : str
        Arduino IP address
    
    Returns
    -------
    bool
        True if Arduino is reachable
    """
    controller = ArduinoTriggerController(ip=ip)
    return controller.is_connected()


# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("Arduino Trigger Controller - Test")
    print("=" * 60)
    
    # Create controller
    arduino = ArduinoTriggerController(ip="10.20.30.47")
    
    # Test connection
    print("\n1. Testing connection...")
    if arduino.is_connected():
        print("   ✓ Arduino is reachable")
    else:
        print("   ✗ Cannot reach Arduino")
        exit(1)
    
    # Get initial state
    print("\n2. Getting current state...")
    lamp, avantes = arduino.get_state()
    print(f"   Lamp: {'ON' if lamp else 'OFF'}")
    print(f"   Avantes: {'ON' if avantes else 'OFF'}")
    print(f"   Status: {arduino.get_status_string()}")
    
    # Test mode changes
    print("\n3. Testing mode changes...")
    
    print("   Setting: ONLY AVANTES")
    if arduino.start_spectrometers_only():
        print("   ✓ Mode set successfully")
        lamp, avantes = arduino.get_state()
        print(f"   Current: Lamp={lamp}, Avantes={avantes}")
    
    input("\n   Press Enter to test LAMP AND AVANTES mode...")
    print("   Setting: LAMP AND AVANTES")
    if arduino.start_lamp_and_spectrometers():
        print("   ✓ Mode set successfully")
        lamp, avantes = arduino.get_state()
        print(f"   Current: Lamp={lamp}, Avantes={avantes}")
    
    input("\n   Press Enter to stop TTL generation...")
    print("   Setting: OFF")
    if arduino.stop_all():
        print("   ✓ TTL stopped")
        lamp, avantes = arduino.get_state()
        print(f"   Current: Lamp={lamp}, Avantes={avantes}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
