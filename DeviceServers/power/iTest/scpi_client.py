# easy-SCPI wrapper for iTest PSU (BiLT chassis)
from __future__ import annotations

from typing import Optional, Sequence

try:
    from easy_scpi import Instrument as EasyInstrument
except Exception as exc:
    raise ImportError("easy_scpi is required. Install with: pip install easy-scpi") from exc


class SCPIError(Exception):
    pass


class ITestSCPI:
    """
    Thin SCPI wrapper for iTest/BiLT chassis using easy-scpi.

    Assumptions (can be adapted via templates):
    - Channel selection by index via INST:SEL S{index}
    - Current set with SOUR:CURR {amps}
    - Measure current with MEAS:CURR?
    - Output ON/OFF via OUTP ON / OUTP OFF and state via OUTP?
    """

    def __init__(self, host: str, port: int = 5025, timeout: float = 3.0, eol: str = "\n", log_level: int = 0) -> None:
        if eol not in ("\n", "\r\n", "\r"):
            raise ValueError("Unsupported EOL; use \\n, \\r\\n, or \\r")
        self._host = str(host)
        self._port = int(port)
        self._timeout_s = float(timeout)
        self._eol = eol
        self._log_level = int(log_level)
        self._inst: Optional[EasyInstrument] = None
        self._tmpl: dict[str, str] = {
            # BiLT selection: short form 'I <slot>' preferred; also accepts 'INST <slot>'
            "select_output": "I {index}",
            # BiLT setpoint: CURR <A> recommended; SOUR:CURR may work but readback often unsupported
            "set_current": "CURR {value:.4f}",
            # Setpoint readback varies: try SOUR:CURR? then CURR?; fallback to DS cache
            "get_current_primary": "SOUR:CURR?",
            "get_current_alt": "CURR?",
            # Measurements
            "measure_current": "MEAS:CURR?",
            # Output control
            "output_on": "OUTP ON",
            "output_off": "OUTP OFF",
            "get_output": "OUTP?",
        }
    
    def _log_debug(self, message: str):
        """Log debug messages only if log level is high enough"""
        if self._log_level >= 2:  # LOG_MAX equivalent
            print(f"[ITestSCPI] {message}")
    
    def _log_normal(self, message: str):
        """Log normal messages if log level allows"""
        if self._log_level >= 1:  # LOG_NORMAL equivalent
            print(f"[ITestSCPI] {message}")
    
    def _log_error(self, message: str):
        """Always log errors"""
        print(f"[ITestSCPI] ERROR: {message}")

    # ---- lifecycle ----
    def connect(self) -> None:
        self._log_normal(f"connect() called for {self._host}:{self._port}")
        if self._inst is not None and getattr(self._inst, "connected", False):
            self._log_debug(f"Already connected to {self._host}:{self._port}")
            return
            
        try:
            resource = f"TCPIP::{self._host}::{self._port}::SOCKET"
            params = {
                "timeout": int(max(0.0, self._timeout_s) * 1000.0),
                "read_termination": self._eol,
                "write_termination": self._eol,
            }
            self._log_debug(f"Creating EasyInstrument with resource='{resource}', params={params}")
            
            self._inst = EasyInstrument(port=resource, port_match=False, **params)
            self._log_debug(f"EasyInstrument created successfully")
            
            self._log_debug(f"Calling _inst.connect()...")
            self._inst.connect()
            self._log_normal(f"Successfully connected to {self._host}:{self._port}")
            
        except Exception as exc:
            self._log_error(f"Connection failed: {exc}")
            raise SCPIError(f"Failed to connect to {self._host}:{self._port}: {exc}") from exc

    def close(self) -> None:
        try:
            if self._inst is not None:
                self._inst.disconnect()
        finally:
            self._inst = None

    # ---- helpers ----
    def _ensure(self) -> EasyInstrument:
        if self._inst is None or not getattr(self._inst, "connected", False):
            raise SCPIError("SCPI not connected")
        return self._inst

    def _write(self, cmd: str) -> None:
        try:
            self._log_debug(f"Writing command: '{cmd}'")
            self._ensure().write(cmd)
            self._log_debug(f"Command written successfully")
        except Exception as exc:
            self._log_error(f"Write failed: {exc}")
            raise SCPIError(f"Write failed: {exc}") from exc

    def _query(self, cmd: str) -> str:
        try:
            self._log_debug(f"Querying: '{cmd}'")
            result = self._ensure().query(cmd)
            self._log_debug(f"Query result: '{result}'")
            return result
        except Exception as exc:
            self._log_error(f"Query failed: {exc}")
            raise SCPIError(f"Query failed: {exc}") from exc

    # ---- templates ----
    def configure_templates(self, templates: dict[str, str]) -> None:
        allowed = set(self._tmpl.keys())
        for k, v in (templates or {}).items():
            if k in allowed:
                self._tmpl[k] = str(v)

    # ---- per-slot ops ----
    def select_slot(self, index: int) -> None:
        if index < 1:
            raise ValueError("Slot index is 1-based")
        cmd = self._tmpl["select_output"].format(index=int(index))
        self._write(cmd)

    def set_current(self, index: int, amps: float) -> None:
        self.select_slot(index)
        cmd = self._tmpl["set_current"].format(value=float(amps))
        self._write(cmd)

    def get_current_setpoint(self, index: int) -> float:
        self.select_slot(index)
        # Try primary then alt template
        last_exc: Exception | None = None
        for key in ("get_current_primary", "get_current_alt"):
            try:
                resp = self._query(self._tmpl[key]).strip()
                return float(resp.split(",")[0]) if "," in resp else float(resp)
            except Exception as exc:
                last_exc = exc
                continue
        # If both readbacks fail, propagate for DS to decide (cache fallback there)
        if last_exc:
            raise SCPIError(f"Setpoint readback unsupported: {last_exc}")
        raise SCPIError("Setpoint readback unsupported")

    def measure_current(self, index: int) -> float:
        self.select_slot(index)
        resp = self._query(self._tmpl["measure_current"]).strip()
        return float(resp.split(",")[0]) if "," in resp else float(resp)

    def output_on(self, index: int) -> None:
        self.select_slot(index)
        self._write(self._tmpl["output_on"])

    def output_off(self, index: int) -> None:
        self.select_slot(index)
        self._write(self._tmpl["output_off"])

    def get_output_state(self, index: int) -> int:
        self.select_slot(index)
        resp = self._query(self._tmpl["get_output"]).strip()
        # Expect "1" or "0"
        try:
            return 1 if int(resp) != 0 else 0
        except Exception:
            return 1 if resp.upper() in ("ON", "1", "TRUE") else 0

    # ---- batch helpers ----
    def measure_all_currents(self, slot_ids: list[int]) -> list[float]:
        """Measure currents for the provided slot IDs (not sequential range)"""
        out: list[float] = []
        for slot_id in slot_ids:
            try:
                out.append(self.measure_current(slot_id))
            except Exception:
                out.append(float('nan'))
        return out

    def read_all_states(self, slot_ids: list[int]) -> list[int]:
        """Read states for the provided slot IDs (not sequential range)"""
        out: list[int] = []
        for slot_id in slot_ids:
            try:
                out.append(self.get_output_state(slot_id))
            except Exception:
                out.append(0)
        return out

    # ---- discovery ----
    def list_slots(self) -> list[tuple[int, str]]:
        """Return list of (slot, model) from INST:LIST? response.
        Example: "1,2819;3,2819;5,2811" → [(1,'2819'), (3,'2819'), (5,'2811')]
        """
        resp = self._query("INST:LIST?").strip()
        items = [s for s in resp.split(";") if s.strip()]
        result: list[tuple[int, str]] = []
        for it in items:
            try:
                parts = [p.strip() for p in it.split(",")]
                if len(parts) >= 2:
                    slot = int(parts[0])
                    model = parts[1]
                    result.append((slot, model))
            except Exception:
                continue
        return sorted(result, key=lambda x: x[0])
