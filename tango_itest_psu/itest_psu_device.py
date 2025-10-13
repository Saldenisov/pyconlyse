# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import os
import threading
from typing import Optional

from tango import DevState
from tango.server import Device, attribute, command, device_property, run

from .scpi_client import SCPISocket, SCPIError


class ITestPSU(Device):
    """
    Tango Device Server for controlling an iTest/ITECH-like PSU via SCPI over TCP.

    Device properties:
      - Host (str): PSU IP address
      - Port (int, default 5025): SCPI TCP port
      - StartCurrent (float, default 0.0): starting current setpoint if no ConfigPath is provided
      - ConfigPath (str, optional): path to JSON file containing {"start_current": <float>}
      - EnableOutputOnInit (bool, default False): whether to turn output ON at init
      - EOL (str, default \n): line terminator for SCPI ("\n", "\r\n", or "\r")

    Attributes:
      - CurrentSetpoint (RW, double): current setpoint in A (SOUR:CURR?)
      - MeasuredCurrent (RO, double): measured current in A (MEAS:CURR?)
      - MeasuredVoltage (RO, double): measured voltage in V (MEAS:VOLT?)
      - OutputEnabled (RW, bool): PS output ON/OFF
      - InstrumentId (RO, string): *IDN? response

    Commands:
      - IncCurrentFine / DecCurrentFine: ±0.01 A
      - IncCurrentCoarse / DecCurrentCoarse: ±0.1 A
      - Reconnect: reconnect to instrument
    """

    # Device properties
    Host = device_property(dtype=str)
    Port = device_property(dtype=int, default_value=5025)
    StartCurrent = device_property(dtype=float, default_value=0.0)
    ConfigPath = device_property(dtype=str)
    EnableOutputOnInit = device_property(dtype=bool, default_value=False)
    EOL = device_property(dtype=str, default_value="\n")

    # Internal
    _scpi: Optional[SCPISocket] = None
    _lock: threading.RLock
    _instrument_id: str = ""

    def init_device(self) -> None:
        Device.init_device(self)
        self.set_state(DevState.INIT)
        self._lock = threading.RLock()
        try:
            eol = self.EOL or "\n"
            self._scpi = SCPISocket(self.Host, self.Port, timeout=3.0, eol=eol)
            self._scpi.connect()
            # Identify
            try:
                self._instrument_id = self._scpi.idn()
            except SCPIError:
                self._instrument_id = ""
            # Determine start current
            start_current = self._load_start_current()
            # Apply start current if provided
            if start_current is not None:
                self._set_current_safe(start_current)
            # Optionally enable output
            if self.EnableOutputOnInit:
                try:
                    self._scpi.output_on()
                except SCPIError as exc:
                    self.error_stream(f"Failed to enable output on init: {exc}")
            self.set_status("Initialized and connected")
            self.set_state(DevState.ON)
        except Exception as exc:
            self.error_stream(f"Initialization failed: {exc}")
            self.set_status(f"Init error: {exc}")
            self.set_state(DevState.FAULT)

    def delete_device(self) -> None:
        with self._lock:
            if self._scpi is not None:
                self._scpi.close()
                self._scpi = None

    # ---- Helpers ----
    def _load_start_current(self) -> Optional[float]:
        if self.ConfigPath:
            try:
                path = os.path.expanduser(self.ConfigPath)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                val = float(data.get("start_current"))
                return val
            except Exception as exc:
                self.warn_stream(f"Failed reading ConfigPath '{self.ConfigPath}': {exc}; falling back to StartCurrent")
        # fallback
        try:
            return float(self.StartCurrent)
        except Exception:
            return None

    def _with_scpi(self) -> SCPISocket:
        if self._scpi is None:
            raise SCPIError("SCPI not connected")
        return self._scpi

    def _set_current_safe(self, amps: float) -> None:
        with self._lock:
            scpi = self._with_scpi()
            scpi.set_current(amps)

    def _get_current_setpoint_safe(self) -> float:
        with self._lock:
            scpi = self._with_scpi()
            return scpi.get_current_setpoint()

    # ---- Attributes ----
    @attribute(dtype=float, rw=True, unit="A", label="Current Setpoint")
    def CurrentSetpoint(self) -> float:  # type: ignore[override]
        try:
            val = self._get_current_setpoint_safe()
            return val
        except Exception as exc:
            self.error_stream(f"Read CurrentSetpoint failed: {exc}")
            raise

    @CurrentSetpoint.write
    def CurrentSetpoint(self, value: float) -> None:  # type: ignore[override]
        try:
            self._set_current_safe(float(value))
        except Exception as exc:
            self.error_stream(f"Write CurrentSetpoint failed: {exc}")
            raise

    @attribute(dtype=float, rw=False, unit="A", label="Measured Current")
    def MeasuredCurrent(self) -> float:  # type: ignore[override]
        with self._lock:
            scpi = self._with_scpi()
            return scpi.measure_current()

    @attribute(dtype=float, rw=False, unit="V", label="Measured Voltage")
    def MeasuredVoltage(self) -> float:  # type: ignore[override]
        with self._lock:
            scpi = self._with_scpi()
            return scpi.measure_voltage()

    @attribute(dtype=bool, rw=True, label="Output Enabled")
    def OutputEnabled(self) -> bool:  # type: ignore[override]
        # Not all PSUs provide OUTP? response consistently; we approximate by success response
        # For deterministic behavior, you can override to read a vendor-specific query.
        return False  # unknown unless extended; kept for UI completeness

    @OutputEnabled.write
    def OutputEnabled(self, value: bool) -> None:  # type: ignore[override]
        with self._lock:
            scpi = self._with_scpi()
            if value:
                scpi.output_on()
            else:
                scpi.output_off()

    @attribute(dtype=str, rw=False, label="Instrument ID")
    def InstrumentId(self) -> str:  # type: ignore[override]
        return self._instrument_id or ""

    # ---- Commands ----
    @command()
    def Reconnect(self) -> None:
        with self._lock:
            if self._scpi is not None:
                try:
                    self._scpi.close()
                except Exception:
                    pass
            self._scpi = SCPISocket(self.Host, self.Port, timeout=3.0, eol=self.EOL or "\n")
            self._scpi.connect()
            try:
                self._instrument_id = self._scpi.idn()
            except Exception:
                self._instrument_id = ""

    def _adjust_current(self, delta: float) -> float:
        cur = self._get_current_setpoint_safe()
        new_val = cur + delta
        # Optional: clamp range if you know limits; left open here
        self._set_current_safe(new_val)
        return new_val

    @command()
    def IncCurrentFine(self) -> float:
        """Increase current by +0.01 A. Returns the new setpoint."""
        return self._adjust_current(+0.01)

    @command()
    def DecCurrentFine(self) -> float:
        """Decrease current by -0.01 A. Returns the new setpoint."""
        return self._adjust_current(-0.01)

    @command()
    def IncCurrentCoarse(self) -> float:
        """Increase current by +0.1 A. Returns the new setpoint."""
        return self._adjust_current(+0.1)

    @command()
    def DecCurrentCoarse(self) -> float:
        """Decrease current by -0.1 A. Returns the new setpoint."""
        return self._adjust_current(-0.1)


def main() -> None:
    run((ITestPSU,))


if __name__ == "__main__":
    main()
