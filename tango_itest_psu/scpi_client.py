# SPDX-License-Identifier: MIT
# SCPI client wrapper using easy-scpi (PyVISA backend)
from __future__ import annotations

from typing import Optional

try:
    from easy_scpi import Instrument as EasyInstrument
except Exception as exc:  # pragma: no cover - environment specific
    raise ImportError(
        "easy_scpi is required. Install with: pip install easy-scpi"
    ) from exc


class SCPIError(Exception):
    pass


class SCPISocket:
    """
    SCPI client implemented on top of easy-scpi's Instrument (PyVISA).
    
    Simplified version for tango_itest_psu package - basic PSU operations only.
    """

    def __init__(self, host: str, port: int = 5025, timeout: float = 3.0, eol: str = "\n") -> None:
        if eol not in ("\n", "\r\n", "\r"):
            raise ValueError("Unsupported EOL; use \n, \r\n, or \r")
        self._host = str(host)
        self._port = int(port)
        self._timeout_s = float(timeout)
        self._eol = eol
        self._inst: Optional[EasyInstrument] = None

    def connect(self) -> None:
        if self._inst is not None and getattr(self._inst, "connected", False):
            return
        try:
            resource = f"TCPIP::{self._host}::{self._port}::SOCKET"
            params = {
                "timeout": int(max(0.0, self._timeout_s) * 1000.0),
                "read_termination": self._eol,
                "write_termination": self._eol,
            }
            self._inst = EasyInstrument(port=resource, port_match=False, **params)
            self._inst.connect()
        except Exception as exc:
            raise SCPIError(f"Failed to connect to {self._host}:{self._port}: {exc}") from exc

    def close(self) -> None:
        try:
            if self._inst is not None:
                self._inst.disconnect()
        finally:
            self._inst = None

    def _ensure(self) -> EasyInstrument:
        if self._inst is None or not getattr(self._inst, "connected", False):
            raise SCPIError("SCPI not connected")
        return self._inst

    def write(self, cmd: str) -> None:
        try:
            self._ensure().write(cmd)
        except Exception as exc:
            raise SCPIError(f"Write failed: {exc}") from exc

    def query(self, cmd: str) -> str:
        try:
            return self._ensure().query(cmd)
        except Exception as exc:
            raise SCPIError(f"Query failed: {exc}") from exc

    def idn(self) -> str:
        return self.query("*IDN?")

    def output_on(self) -> None:
        self.write("OUTP ON")

    def output_off(self) -> None:
        self.write("OUTP OFF")

    def set_current(self, amps: float) -> None:
        self.write(f"SOUR:CURR {amps:.4f}")

    def get_current_setpoint(self) -> float:
        resp = self.query("SOUR:CURR?")
        return _to_float(resp)

    def measure_current(self) -> float:
        resp = self.query("MEAS:CURR?")
        return _to_float(resp)

    def measure_voltage(self) -> float:
        resp = self.query("MEAS:VOLT?")
        return _to_float(resp)


def _to_float(s: str) -> float:
    try:
        return float(str(s).strip())
    except Exception as exc:
        raise SCPIError(f"Could not parse float from '{s}'") from exc
