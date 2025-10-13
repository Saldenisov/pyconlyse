# SPDX-License-Identifier: MIT
# Simple SCPI-over-TCP client
from __future__ import annotations

import socket
import threading
from typing import Optional


class SCPIError(Exception):
    pass


class SCPISocket:
    """
    Minimal SCPI client over raw TCP sockets.

    Defaults assume many lab PSUs speak SCPI on port 5025 with LF as terminator.
    Adjust eol / port if your instrument differs.
    """

    def __init__(self, host: str, port: int = 5025, timeout: float = 3.0, eol: str = "\n") -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        if eol not in ("\n", "\r\n", "\r"):
            raise ValueError("Unsupported EOL; use \n, \r\n, or \r")
        self.eol = eol.encode()
        self._sock: Optional[socket.socket] = None
        self._lock = threading.RLock()

    def connect(self) -> None:
        with self._lock:
            if self._sock is not None:
                return
            try:
                s = socket.create_connection((self.host, self.port), timeout=self.timeout)
                s.settimeout(self.timeout)
            except OSError as exc:
                raise SCPIError(f"Failed to connect to {self.host}:{self.port}: {exc}") from exc
            self._sock = s

    def close(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                finally:
                    self._sock = None

    def _ensure_conn(self) -> socket.socket:
        if self._sock is None:
            raise SCPIError("Not connected")
        return self._sock

    def write(self, cmd: str) -> None:
        """Send a SCPI command (no response expected)."""
        data = cmd.encode() + self.eol
        with self._lock:
            s = self._ensure_conn()
            try:
                s.sendall(data)
            except OSError as exc:
                raise SCPIError(f"Send failed: {exc}") from exc

    def readline(self) -> str:
        """Read one line until EOL; return decoded string without terminator."""
        with self._lock:
            s = self._ensure_conn()
            chunks: list[bytes] = []
            try:
                while True:
                    b = s.recv(1)
                    if not b:
                        # connection closed
                        break
                    chunks.append(b)
                    if len(chunks) >= len(self.eol) and b"".join(chunks[-len(self.eol):]) == self.eol:
                        break
            except OSError as exc:
                raise SCPIError(f"Receive failed: {exc}") from exc
            if not chunks:
                raise SCPIError("No data received")
            data = b"".join(chunks)
            if data.endswith(self.eol):
                data = data[: -len(self.eol)]
            return data.decode(errors="replace")

    def query(self, cmd: str) -> str:
        """Send a query and read the response line."""
        with self._lock:
            self.write(cmd)
            return self.readline()

    # Convenience helpers for common PSU operations (SCPI-ish defaults)
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
        return float(s.strip())
    except ValueError as exc:
        raise SCPIError(f"Could not parse float from '{s}'") from exc
