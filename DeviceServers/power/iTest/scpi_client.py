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

    def __init__(self, host: str, port: int = 5025, timeout: float = 3.0, eol: str = "\n") -> None:
        if eol not in ("\n", "\r\n", "\r"):
            raise ValueError("Unsupported EOL; use \\n, \\r\\n, or \\r")
        self._host = str(host)
        self._port = int(port)
        self._timeout_s = float(timeout)
        self._eol = eol
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

    # ---- lifecycle ----
    def connect(self) -> None:
        print(f"[ITestSCPI] connect() called for {self._host}:{self._port}")
        if self._inst is not None and getattr(self._inst, "connected", False):
            print(f"[ITestSCPI] Already connected to {self._host}:{self._port}")
            return
            
        try:
            resource = f"TCPIP::{self._host}::{self._port}::SOCKET"
            params = {
                "timeout": int(max(0.0, self._timeout_s) * 1000.0),
                "read_termination": self._eol,
                "write_termination": self._eol,
            }
            print(f"[ITestSCPI] Creating EasyInstrument with resource='{resource}', params={params}")
            
            self._inst = EasyInstrument(port=resource, port_match=False, **params)
            print(f"[ITestSCPI] EasyInstrument created successfully")
            
            print(f"[ITestSCPI] Calling _inst.connect()...")
            self._inst.connect()
            print(f"[ITestSCPI] Successfully connected to {self._host}:{self._port}")
            
        except Exception as exc:
            print(f"[ITestSCPI] Connection failed: {exc}")
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
            print(f"[ITestSCPI] Writing command: '{cmd}'")
            self._ensure().write(cmd)
            print(f"[ITestSCPI] Command written successfully")
        except Exception as exc:
            print(f"[ITestSCPI] Write failed: {exc}")
            raise SCPIError(f"Write failed: {exc}") from exc

    def _query(self, cmd: str) -> str:
        try:
            print(f"[ITestSCPI] Querying: '{cmd}'")
            result = self._ensure().query(cmd)
            print(f"[ITestSCPI] Query result: '{result}'")
            return result
        except Exception as exc:
            print(f"[ITestSCPI] Query failed: {exc}")
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
    def measure_all_currents(self, slot_count: int) -> list[float]:
        out: list[float] = []
        for i in range(1, slot_count + 1):
            try:
                out.append(self.measure_current(i))
            except Exception:
                out.append(float('nan'))
        return out

    def read_all_states(self, slot_count: int) -> list[int]:
        out: list[int] = []
        for i in range(1, slot_count + 1):
            try:
                out.append(self.get_output_state(i))
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
