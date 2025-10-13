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

    This client also includes basic helpers for multi-output PSUs:
    - select_channel(n) uses INST:NSEL n
    - select_output_by_name(name) using configurable template
    - get_output_state() queries OUTP? (fallback: OUTP:STAT?)

    You can configure per-instrument command templates via configure_templates().
    Supported template keys (all optional):
      - select_output:   e.g. "INST:SEL {name}" or "ROUT:CHAN:SEL '{name}'"
      - set_current:     e.g. "SOUR:CURR {value:.4f}" or "SOUR:CURR:{name} {value:.4f}"
      - get_current:     e.g. "SOUR:CURR?" or "SOUR:CURR:{name}?"
      - measure_current: e.g. "MEAS:CURR?" or "MEAS:CURR? {name}"
      - measure_voltage: e.g. "MEAS:VOLT?" or "MEAS:VOLT? {name}"
      - output_on:       e.g. "OUTP ON" or "OUTP {name},ON"
      - output_off:      e.g. "OUTP OFF" or "OUTP {name},OFF"
      - get_output:      e.g. "OUTP?" or "OUTP? {name}"
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
        # Optional instrument-specific templates
        self._tmpl: dict[str, str] = {}

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

    def query_first(self, cmds: list[str]) -> str:
        """Try a list of queries; return the first successful response."""
        last_exc: Optional[Exception] = None
        for c in cmds:
            try:
                return self.query(c)
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc:
            raise SCPIError(f"All queries failed: {cmds}: {last_exc}")
        raise SCPIError("Empty query list")

    # Convenience helpers for common PSU operations (SCPI-ish defaults)
    def idn(self) -> str:
        return self.query("*IDN?")

    # Template configuration
    def configure_templates(self, templates: dict[str, str]) -> None:
        # Only keep known keys
        allowed = {
            "select_output",
            "set_current",
            "get_current",
            "measure_current",
            "measure_voltage",
            "output_on",
            "output_off",
            "get_output",
        }
        self._tmpl = {k: v for k, v in (templates or {}).items() if k in allowed}

    def output_on(self) -> None:
        # If template specifies name, user should call output_on_for(name)
        tpl = self._tmpl.get("output_on")
        if tpl and "{name}" in tpl:
            raise SCPIError("output_on() requires name in template; call output_on_for(name)")
        if tpl:
            self.write(tpl)
        else:
            self.write("OUTP ON")

    def output_off(self) -> None:
        tpl = self._tmpl.get("output_off")
        if tpl and "{name}" in tpl:
            raise SCPIError("output_off() requires name in template; call output_off_for(name)")
        if tpl:
            self.write(tpl)
        else:
            self.write("OUTP OFF")

    def set_current(self, amps: float) -> None:
        tpl = self._tmpl.get("set_current")
        if tpl and "{name}" in tpl:
            raise SCPIError("set_current() requires name in template; call set_current_for(name, amps)")
        if tpl:
            self.write(tpl.format(value=amps))
        else:
            self.write(f"SOUR:CURR {amps:.4f}")

    def get_current_setpoint(self) -> float:
        tpl = self._tmpl.get("get_current")
        if tpl and "{name}" in tpl:
            raise SCPIError("get_current_setpoint() requires name in template; call get_current_setpoint_for(name)")
        resp = self.query(tpl or "SOUR:CURR?")
        return _to_float(resp)

    def measure_current(self) -> float:
        tpl = self._tmpl.get("measure_current")
        if tpl and "{name}" in tpl:
            raise SCPIError("measure_current() requires name in template; call measure_current_for(name)")
        resp = self.query(tpl or "MEAS:CURR?")
        return _to_float(resp)

    def measure_voltage(self) -> float:
        tpl = self._tmpl.get("measure_voltage")
        if tpl and "{name}" in tpl:
            raise SCPIError("measure_voltage() requires name in template; call measure_voltage_for(name)")
        resp = self.query(tpl or "MEAS:VOLT?")
        return _to_float(resp)

    # Name-based helpers
    def select_output_by_name(self, name: str) -> None:
        tpl = self._tmpl.get("select_output")
        if not tpl:
            # Fall back to INST:SEL with name directly; user may need quotes in template
            self.write(f"INST:SEL {name}")
        else:
            self.write(tpl.format(name=name))

    def output_on_for(self, name: str) -> None:
        tpl = self._tmpl.get("output_on")
        if tpl and "{name}" in tpl:
            self.write(tpl.format(name=name))
        else:
            # Select then generic
            self.select_output_by_name(name)
            self.output_on()

    def output_off_for(self, name: str) -> None:
        tpl = self._tmpl.get("output_off")
        if tpl and "{name}" in tpl:
            self.write(tpl.format(name=name))
        else:
            self.select_output_by_name(name)
            self.output_off()

    def set_current_for(self, name: str, amps: float) -> None:
        tpl = self._tmpl.get("set_current")
        if tpl and "{name}" in tpl:
            self.write(tpl.format(name=name, value=amps))
        else:
            self.select_output_by_name(name)
            self.set_current(amps)

    def get_current_setpoint_for(self, name: str) -> float:
        tpl = self._tmpl.get("get_current")
        if tpl and "{name}" in tpl:
            resp = self.query(tpl.format(name=name))
        else:
            self.select_output_by_name(name)
            resp = self.query(self._tmpl.get("get_current") or "SOUR:CURR?")
        return _to_float(resp)

    def measure_current_for(self, name: str) -> float:
        tpl = self._tmpl.get("measure_current")
        if tpl and "{name}" in tpl:
            resp = self.query(tpl.format(name=name))
        else:
            self.select_output_by_name(name)
            resp = self.query(self._tmpl.get("measure_current") or "MEAS:CURR?")
        return _to_float(resp)

    def measure_voltage_for(self, name: str) -> float:
        tpl = self._tmpl.get("measure_voltage")
        if tpl and "{name}" in tpl:
            resp = self.query(tpl.format(name=name))
        else:
            self.select_output_by_name(name)
            resp = self.query(self._tmpl.get("measure_voltage") or "MEAS:VOLT?")
        return _to_float(resp)

    # Multi-channel helpers (common SCPI dialects)
    def select_channel(self, n: int) -> None:
        """Select output channel n (1-based) for subsequent SOUR/MEAS/OUTP commands."""
        self.write(f"INST:NSEL {int(n)}")

    def get_output_state(self) -> bool:
        """Query output enable state on the currently selected channel."""
        # Try common forms
        resp = None
        try:
            resp = self.query(self._tmpl.get("get_output") or "OUTP?")
        except Exception:
            resp = self.query_first(["OUTP:STAT?"])
        s = resp.strip().upper()
        if s in ("1", "ON", "TRUE"):
            return True
        if s in ("0", "OFF", "FALSE"):
            return False
        # Sometimes returns like 'ON\n' or 'OFF\n'
        return s.startswith("ON") or s.startswith("1")

    def get_output_state_for(self, name: str) -> bool:
        tpl = self._tmpl.get("get_output")
        if tpl and "{name}" in tpl:
            resp = self.query(tpl.format(name=name))
        else:
            self.select_output_by_name(name)
            resp = self.query(self._tmpl.get("get_output") or "OUTP?")
        s = resp.strip().upper()
        if s in ("1", "ON", "TRUE"):
            return True
        if s in ("0", "OFF", "FALSE"):
            return False
        return s.startswith("ON") or s.startswith("1")


def _to_float(s: str) -> float:
    try:
        return float(s.strip())
    except ValueError as exc:
        raise SCPIError(f"Could not parse float from '{s}'") from exc