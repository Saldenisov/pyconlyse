# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import os
import threading
from typing import Optional, List, Dict, Any

from tango import DevState, AttrWriteType, DispLevel
from tango.server import Device, attribute, command, device_property, run

# Try multiple import paths for SCPI client
try:
    from .scpi_client import SCPISocket, SCPIError  # local package style
except Exception:
    try:
        from tango_itest_psu.scpi_client import SCPISocket, SCPIError  # installed/package style
    except Exception:
        # Fallback for direct script execution when path is in sys.path
        from scpi_client import SCPISocket, SCPIError


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

    # Discovery and safety
    UseDiscovery = device_property(dtype=bool, default_value=True, doc="If true, discover outputs via INST:LIST? on init")
    SafeCurrentMin = device_property(dtype=float, default_value=-5.0, doc="Software minimum current limit [A]")
    SafeCurrentMax = device_property(dtype=float, default_value=5.0, doc="Software maximum current limit [A]")

    # Multi-rack properties
    RackHosts = device_property(dtype=str, doc="Comma-separated host[:port] entries for racks. If empty, Host/Port are used.")
    ChannelsPerRack = device_property(dtype=int, default_value=1)

    # Optional: engineer-friendly aliases for outputs
    # JSON string mapping slot numbers to alias names, e.g. {"1": "Gate", "7": "Drain"}
    OutputAliases = device_property(dtype=str, doc="JSON mapping of slot->alias for output names")

    # Internal
    _scpi: Optional[SCPISocket] = None  # primary rack for backward compatibility
    _scpis: list[SCPISocket] = []
    _lock: threading.RLock
    _instrument_id: str = ""
    _outputs_info: List[Dict[str, Any]] = []  # [{"slot": int, "model": str, "name": str}]
    _last_setpoints: Dict[int, float] = {}  # slot -> last requested current [A]

    def init_device(self) -> None:
        Device.init_device(self)
        self.set_state(DevState.INIT)
        self._lock = threading.RLock()
        try:
            eol = self.EOL or "\n"
            # Build rack connections
            hosts: list[tuple[str, int]] = []
            if self.RackHosts:
                parts = [p.strip() for p in str(self.RackHosts).split(",") if p.strip()]
                for p in parts:
                    if ":" in p:
                        h, sp = p.rsplit(":", 1)
                        try:
                            hosts.append((h.strip(), int(sp)))
                        except Exception:
                            hosts.append((h.strip(), self.Port))
                    else:
                        hosts.append((p, self.Port))
            else:
                hosts.append((self.Host, self.Port))

            self._scpis = []
            for h, prt in hosts:
                sc = SCPISocket(h, prt, timeout=3.0, eol=eol)
                sc.connect()
                self._scpis.append(sc)

            # Primary scpi for backward compatibility (rack 1)
            self._scpi = self._scpis[0]

            # Load templates and output names from config (optional)
            cfg = self._load_config()
            templates = cfg.get("commands") or {}
            if templates:
                try:
                    # Not all SCPISocket variants implement templates; ignore if missing
                    getattr(self._scpi, "configure_templates", lambda _t: None)(templates)
                except Exception as exc:
                    self.warn_stream(f"Template configuration warning: {exc}")

            # Initialize outputs list
            self._output_names: List[str] = []
            self._outputs_info = []

            # 1) Try discovery via SCPI if enabled
            if bool(self.UseDiscovery):
                try:
                    self._discover_outputs_via_scpi()
                except Exception as exc:
                    self.warn_stream(f"Discovery failed, falling back to config outputs: {exc}")

            # Apply aliases if provided
            try:
                self._apply_output_aliases()
            except Exception as exc:
                self.warn_stream(f"Alias mapping failed: {exc}")

            # 2) Fallback to outputs from config
            if not self._output_names:
                outs = cfg.get("outputs")
                if isinstance(outs, list):
                    self._output_names = [str(x) for x in outs]
                    # Build basic outputs_info with unknown model
                    try:
                        # When only names exist, try to extract slot numbers (best-effort)
                        for name in self._output_names:
                            slot = self._parse_slot_from_name(name)
                            self._outputs_info.append({"slot": slot, "model": "", "name": name})
                    except Exception:
                        pass
                # Apply aliases to configured names as well
                try:
                    self._apply_output_aliases()
                except Exception:
                    pass

            # Identify (use first rack id)
            try:
                self._instrument_id = self._scpi.idn()
            except SCPIError:
                self._instrument_id = ""

            # Determine start current
            start_current = self._load_start_current()
            # Apply start current on first configured output, else channel 1
            if start_current is not None:
                try:
                    if self._outputs_info:
                        self._set_output_current_by_name(self._outputs_info[0]["name"], start_current)
                    else:
                        # No discovery/config → try default channel 1 on primary
                        self._set_current_safe(start_current)
                except Exception as exc:
                    self.warn_stream(f"Failed to set start current: {exc}")

            # Optionally enable output on first output
            if self.EnableOutputOnInit:
                try:
                    if self._outputs_info:
                        self._set_output_state_by_name(self._outputs_info[0]["name"], True)
                    else:
                        # Fallback: primary only
                        self._with_scpi().output_on()
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
    def _load_config(self) -> Dict[str, Any]:
        cfg: Dict[str, Any] = {}
        if self.ConfigPath:
            try:
                path = os.path.expanduser(self.ConfigPath)
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception as exc:
                self.warn_stream(f"Failed reading ConfigPath '{self.ConfigPath}': {exc}; continuing with defaults")
        return cfg

    def _load_start_current(self) -> Optional[float]:
        cfg = self._load_config()
        try:
            if "start_current" in cfg:
                return float(cfg.get("start_current"))
        except Exception:
            pass
        # fallback
        try:
            return float(self.StartCurrent)
        except Exception:
            return None

    def _with_scpi(self) -> SCPISocket:
        if self._scpi is None:
            raise SCPIError("SCPI not connected")
        return self._scpi

    # ---- Discovery helpers ----
    def _parse_slot_from_name(self, name: str) -> int:
        try:
            # Expect names like slot_7_model_2819 or custom names with slot numbers
            import re
            m = re.search(r"slot[_-]?([0-9]+)", name.lower())
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 1

    def _discover_outputs_via_scpi(self) -> None:
        """Populate self._outputs_info and self._output_names using INST:LIST?.
        Builds names as slot_<n>_model_<id>.
        """
        scpi = self._with_scpi()
        try:
            raw = scpi.query("INST:LIST?")
        except Exception as exc:
            raise SCPIError(f"INST:LIST? failed: {exc}")
        outs: List[Dict[str, Any]] = []
        names: List[str] = []
        for entry in str(raw).split(";"):
            if not entry.strip():
                continue
            try:
                slot_str, model_str = entry.split(",", 1)
                slot = int(slot_str.strip())
                model = model_str.strip()
                name = f"slot_{slot}_model_{model}"
                outs.append({"slot": slot, "model": model, "name": name})
                names.append(name)
            except Exception:
                continue
        self._outputs_info = outs
        self._output_names = names

    def _apply_output_aliases(self) -> None:
        """If OutputAliases property is provided, rename outputs accordingly.
        Accepts JSON mapping of slot numbers to alias strings.
        """
        mapping: Dict[int, str] = {}
        try:
            raw = (self.OutputAliases or "").strip()
            if not raw:
                return
            import json as _json
            mobj = _json.loads(raw)
            if isinstance(mobj, dict):
                for k, v in mobj.items():
                    try:
                        sk = int(k)
                        sv = str(v).strip()
                        if sv:
                            mapping[sk] = sv
                    except Exception:
                        continue
        except Exception:
            return
        if not mapping or not self._outputs_info:
            return
        used = set()
        for info in self._outputs_info:
            slot = int(info.get("slot") or 0)
            if slot in mapping:
                alias = mapping[slot]
                # ensure uniqueness
                cand = alias
                idx = 1
                while cand in used:
                    cand = f"{alias}_{idx}"
                    idx += 1
                info["name"] = cand
                used.add(cand)
        # Rebuild names list in same order
        self._output_names = [i.get("name") for i in self._outputs_info if i.get("name")]

    def _select_slot(self, slot: int) -> None:
        """Select instrument slot before issuing per-slot commands.
        On this hardware the selection is "I <slot>" (alias of INST <slot>)."""
        scpi = self._with_scpi()
        scpi.write(f"I {int(slot)}")

    def _find_slot_by_name(self, name: str) -> int:
        for info in self._outputs_info:
            if info.get("name") == name:
                return int(info.get("slot") or 1)
        # fallback best-effort from name
        return self._parse_slot_from_name(name)

    def _set_output_state_by_name(self, name: str, on: bool) -> bool:
        slot = self._find_slot_by_name(name)
        self._select_slot(slot)
        sc = self._with_scpi()
        if on:
            sc.output_on()
        else:
            sc.output_off()
        try:
            return bool(int(sc.query("OUTP?")))
        except Exception:
            return on

    # ---- Safety helpers ----
    def _in_safe_current_range(self, amps: float) -> bool:
        try:
            lo = float(self.SafeCurrentMin)
            hi = float(self.SafeCurrentMax)
        except Exception:
            lo, hi = -5.0, 5.0
        return (lo <= float(amps) <= hi)

    def _enforce_safe_current(self, amps: float) -> None:
        if not self._in_safe_current_range(amps):
            lo = self.SafeCurrentMin
            hi = self.SafeCurrentMax
            raise Exception(f"Requested current {amps:.4f} A outside safe range [{lo}, {hi}] A")

    def _get_scpi_for(self, rack: int) -> SCPISocket:
        if not self._scpis:
            raise SCPIError("No SCPI connections available")
        idx = rack - 1
        if idx < 0 or idx >= len(self._scpis):
            raise SCPIError(f"Rack index out of range: {rack}")
        return self._scpis[idx]

    def _set_current_safe(self, amps: float) -> None:
        # Primary (legacy) path, without selecting slot
        self._enforce_safe_current(amps)
        with self._lock:
            scpi = self._with_scpi()
            scpi.set_current(amps)

    def _get_current_setpoint_safe(self) -> float:
        with self._lock:
            scpi = self._with_scpi()
            try:
                return scpi.get_current_setpoint()
            except Exception:
                # Some modules do not support readback; return measured current as best-effort
                try:
                    return scpi.measure_current()
                except Exception:
                    raise

    # ---- Attributes ----
    @attribute(dtype=float, access=AttrWriteType.READ_WRITE, unit="A", label="Current Setpoint")
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

    @attribute(dtype=float, access=AttrWriteType.READ, unit="A", label="Measured Current")
    def MeasuredCurrent(self) -> float:  # type: ignore[override]
        with self._lock:
            scpi = self._with_scpi()
            return scpi.measure_current()

    @attribute(dtype=float, access=AttrWriteType.READ, unit="V", label="Measured Voltage")
    def MeasuredVoltage(self) -> float:  # type: ignore[override]
        with self._lock:
            scpi = self._with_scpi()
            return scpi.measure_voltage()

    @attribute(dtype=bool, access=AttrWriteType.READ_WRITE, label="Output Enabled")
    def OutputEnabled(self) -> bool:  # type: ignore[override]
        # Primary-only output state (for legacy single-output usage)
        with self._lock:
            try:
                return bool(int(self._with_scpi().query("OUTP?")))
            except Exception:
                return False

    @OutputEnabled.write
    def OutputEnabled(self, value: bool) -> None:  # type: ignore[override]
        with self._lock:
            scpi = self._with_scpi()
            if value:
                scpi.output_on()
            else:
                scpi.output_off()

    @attribute(dtype=str, access=AttrWriteType.READ, label="Instrument ID")
    def InstrumentId(self) -> str:  # type: ignore[override]
        return self._instrument_id or ""

    # ---- DS_PDU-like multi-output attributes for interoperability ----
    @attribute(
        label="Outputs names",
        dtype=[str],
        max_dim_x=32,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="List of output names (aliases applied if configured)",
        polling_period=1000,
    )
    def names(self) -> List[str]:
        if getattr(self, "_output_names", None):
            return list(self._output_names)
        # Fallback to generic names if discovery/config missing
        try:
            ch = int(self.ChannelsPerRack) if self.ChannelsPerRack else 1
        except Exception:
            ch = 1
        return [f"slot_{i}" for i in range(1, ch + 1)]

    @attribute(
        label="Outputs ids",
        dtype=[int],
        max_dim_x=32,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="List of output slot indices (1-based)",
        polling_period=1000,
    )
    def ids(self) -> List[int]:
        if getattr(self, "_outputs_info", None):
            try:
                return [int(x.get("slot") or 1) for x in self._outputs_info]
            except Exception:
                pass
        try:
            ch = int(self.ChannelsPerRack) if self.ChannelsPerRack else 1
        except Exception:
            ch = 1
        return list(range(1, ch + 1))

    @attribute(
        label="Outputs states",
        dtype=[int],
        max_dim_x=32,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Output enable states as integers (0=OFF, 1=ON)",
        polling_period=500,
    )
    def states(self) -> List[int]:
        res: List[int] = []
        with self._lock:
            sc = self._with_scpi()
            if getattr(self, "UseDiscovery", True) and getattr(self, "_outputs_info", None):
                for info in self._outputs_info:
                    slot = int(info.get("slot") or 1)
                    try:
                        try:
                            self._select_slot(slot)
                        except Exception:
                            pass
                        on = sc.get_output_state()
                        res.append(1 if on else 0)
                    except Exception:
                        res.append(0)
            else:
                # Fallback: use configured channel count
                try:
                    ch = int(self.ChannelsPerRack) if self.ChannelsPerRack else 1
                except Exception:
                    ch = 1
                for slot in range(1, ch + 1):
                    try:
                        try:
                            sc.write(f"I {slot}")
                        except Exception:
                            pass
                        on = sc.get_output_state()
                        res.append(1 if on else 0)
                    except Exception:
                        res.append(0)
        return res

    @attribute(dtype=int, access=AttrWriteType.READ, label="Rack Count")
    def RackCount(self) -> int:  # type: ignore[override]
        return len(self._scpis) if hasattr(self, "_scpis") and self._scpis else (1 if self._scpi else 0)

    @attribute(dtype=int, access=AttrWriteType.READ, label="Channels Per Rack")
    def Channels(self) -> int:  # type: ignore[override]
        return int(self.ChannelsPerRack)

    @attribute(dtype=int, access=AttrWriteType.READ, label="Slot Count")
    def SlotCount(self) -> int:  # type: ignore[override]
        try:
            return len(self._outputs_info) if getattr(self, "_outputs_info", None) else int(self.ChannelsPerRack)
        except Exception:
            return int(self.ChannelsPerRack) if self.ChannelsPerRack else 1

    @attribute(
        label="Models",
        dtype=[str],
        max_dim_x=64,
        display_level=DispLevel.EXPERT,
        access=AttrWriteType.READ,
        doc="Discovered module models per slot (empty if unknown)",
        polling_period=2000,
    )
    def Models(self) -> List[str]:
        if getattr(self, "_outputs_info", None):
            try:
                return [str(x.get("model") or "") for x in self._outputs_info]
            except Exception:
                return []
        return []

    @attribute(
        label="Current setpoints per slot",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        unit="A",
        polling_period=500,
    )
    def CurrentSetpoints(self) -> List[float]:  # type: ignore[override]
        vals: List[float] = []
        with self._lock:
            sc = self._with_scpi()
            slots: List[int]
            if getattr(self, "_outputs_info", None):
                slots = [int(i.get("slot") or 1) for i in self._outputs_info]
            else:
                try:
                    ch = int(self.ChannelsPerRack) if self.ChannelsPerRack else 1
                except Exception:
                    ch = 1
                slots = list(range(1, ch + 1))
            for slot in slots:
                try:
                    try:
                        self._select_slot(slot)
                    except Exception:
                        pass
                    try:
                        vals.append(float(sc.get_current_setpoint()))
                    except Exception:
                        # Fallback: cached setpoint or measured current
                        cached = self._last_setpoints.get(slot)
                        if cached is not None:
                            vals.append(float(cached))
                        else:
                            vals.append(float(sc.measure_current()))
                except Exception:
                    vals.append(float("nan"))
        return vals

    @attribute(
        label="Measured currents per slot",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        unit="A",
        polling_period=500,
    )
    def MeasuredCurrents(self) -> List[float]:  # type: ignore[override]
        vals: List[float] = []
        with self._lock:
            sc = self._with_scpi()
            if getattr(self, "_outputs_info", None):
                slots = [int(i.get("slot") or 1) for i in self._outputs_info]
            else:
                try:
                    ch = int(self.ChannelsPerRack) if self.ChannelsPerRack else 1
                except Exception:
                    ch = 1
                slots = list(range(1, ch + 1))
            for slot in slots:
                try:
                    try:
                        self._select_slot(slot)
                    except Exception:
                        pass
                    vals.append(float(sc.measure_current()))
                except Exception:
                    vals.append(float("nan"))
        return vals

    @attribute(
        label="Measured voltages per slot",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        unit="V",
        polling_period=500,
    )
    def MeasuredVoltages(self) -> List[float]:  # type: ignore[override]
        vals: List[float] = []
        with self._lock:
            sc = self._with_scpi()
            if getattr(self, "_outputs_info", None):
                slots = [int(i.get("slot") or 1) for i in self._outputs_info]
            else:
                try:
                    ch = int(self.ChannelsPerRack) if self.ChannelsPerRack else 1
                except Exception:
                    ch = 1
                slots = list(range(1, ch + 1))
            for slot in slots:
                try:
                    try:
                        self._select_slot(slot)
                    except Exception:
                        pass
                    vals.append(float(sc.measure_voltage()))
                except Exception:
                    vals.append(float("nan"))
        return vals

    # ---- Commands ----
    @command()
    def Reconnect(self) -> None:
        with self._lock:
            # Rebuild connections based on properties
            if hasattr(self, "_scpis") and self._scpis:
                for sc in self._scpis:
                    try:
                        sc.close()
                    except Exception:
                        pass
            self._scpis = []
            eol = self.EOL or "\n"
            hosts: list[tuple[str, int]] = []
            if self.RackHosts:
                parts = [p.strip() for p in str(self.RackHosts).split(",") if p.strip()]
                for p in parts:
                    if ":" in p:
                        h, sp = p.rsplit(":", 1)
                        try:
                            hosts.append((h.strip(), int(sp)))
                        except Exception:
                            hosts.append((h.strip(), self.Port))
                    else:
                        hosts.append((p, self.Port))
            else:
                hosts.append((self.Host, self.Port))
            for h, prt in hosts:
                sc = SCPISocket(h, prt, timeout=3.0, eol=eol)
                sc.connect()
                self._scpis.append(sc)
            self._scpi = self._scpis[0]
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

    # ----- Multi-rack/channel commands -----
    @command(dtype_in=str, dtype_out=bool)
    def OutputOn(self, name: str) -> bool:
        with self._lock:
            try:
                slot = self._find_slot_by_name(name)
                self._select_slot(slot)
                self._with_scpi().output_on()
                try:
                    return bool(int(self._with_scpi().query("OUTP?")))
                except Exception:
                    return True
            except Exception:
                return False

    @command(dtype_in=str, dtype_out=bool)
    def OutputOff(self, name: str) -> bool:
        with self._lock:
            try:
                slot = self._find_slot_by_name(name)
                self._select_slot(slot)
                self._with_scpi().output_off()
                try:
                    return not bool(int(self._with_scpi().query("OUTP?")))
                except Exception:
                    return True
            except Exception:
                return False

    def _set_output_current_by_name(self, name: str, amps: float) -> float:
        self._enforce_safe_current(amps)
        slot = self._find_slot_by_name(name)
        self._select_slot(slot)
        sc = self._with_scpi()
        sc.set_current(float(amps))
        # Cache value per slot
        try:
            self._last_setpoints[slot] = float(amps)
        except Exception:
            pass
        # Try readback; if not supported, return requested
        try:
            return sc.get_current_setpoint()
        except Exception:
            return float(amps)

    @command(dtype_in=(str, float), dtype_out=float)
    def SetOutputCurrent(self, name_value: tuple) -> float:
        name, amps = name_value
        with self._lock:
            return self._set_output_current_by_name(name, float(amps))

    @command(dtype_in=(str, float), dtype_out=float)
    def BumpOutputCurrent(self, name_delta: tuple) -> float:
        name, delta = name_delta
        with self._lock:
            slot = self._find_slot_by_name(name)
            return self._bump_slot_current(slot, float(delta))

    # ---- Slot-index convenience commands ----
    @command(dtype_in=int, dtype_out=bool)
    def OutputOnSlot(self, slot: int) -> bool:
        with self._lock:
            try:
                self._select_slot(int(slot))
                self._with_scpi().output_on()
                try:
                    return bool(int(self._with_scpi().query("OUTP?")))
                except Exception:
                    return True
            except Exception:
                return False

    @command(dtype_in=int, dtype_out=bool)
    def OutputOffSlot(self, slot: int) -> bool:
        with self._lock:
            try:
                self._select_slot(int(slot))
                self._with_scpi().output_off()
                try:
                    return not bool(int(self._with_scpi().query("OUTP?")))
                except Exception:
                    return True
            except Exception:
                return False

    def _set_slot_current(self, slot: int, amps: float) -> float:
        self._enforce_safe_current(amps)
        self._select_slot(int(slot))
        sc = self._with_scpi()
        sc.set_current(float(amps))
        # Cache and attempt readback
        try:
            self._last_setpoints[int(slot)] = float(amps)
        except Exception:
            pass
        try:
            return sc.get_current_setpoint()
        except Exception:
            return float(amps)

    def _bump_slot_current(self, slot: int, delta: float) -> float:
        sc = self._with_scpi()
        self._select_slot(int(slot))
        try:
            cur = sc.get_current_setpoint()
        except Exception:
            cur = self._last_setpoints.get(int(slot), None)
            if cur is None:
                cur = sc.measure_current()
        newv = float(cur) + float(delta)
        self._enforce_safe_current(newv)
        sc.set_current(newv)
        try:
            self._last_setpoints[int(slot)] = float(newv)
        except Exception:
            pass
        try:
            return sc.get_current_setpoint()
        except Exception:
            return newv

    @command(dtype_in=(int, float), dtype_out=float)
    def SetSlotCurrent(self, slot_value: tuple) -> float:
        slot, amps = slot_value
        with self._lock:
            return self._set_slot_current(int(slot), float(amps))

    @command(dtype_in=(int, float), dtype_out=float)
    def BumpSlotCurrent(self, slot_delta: tuple) -> float:
        slot, delta = slot_delta
        with self._lock:
            return self._bump_slot_current(int(slot), float(delta))

    @command(dtype_out=str)
    def GetAllOutputs(self) -> str:
        """Return JSON array of outputs with status and measurements.
        Uses discovered output names/slots when available.
        """
        res: List[Dict[str, Any]] = []
        with self._lock:
            sc = self._with_scpi()
            # Ensure we have discovery results if enabled
            if self.UseDiscovery and not self._outputs_info:
                try:
                    self._discover_outputs_via_scpi()
                except Exception:
                    pass
            if self._outputs_info:
                for info in self._outputs_info:
                    slot = int(info.get("slot") or 1)
                    name = info.get("name") or f"slot_{slot}"
                    entry: Dict[str, Any] = {"slot": slot, "name": name, "model": info.get("model", "")}
                    try:
                        try:
                            self._select_slot(slot)
                        except Exception:
                            pass
                        try:
                            entry["output_enabled"] = bool(int(sc.query("OUTP?")))
                        except Exception:
                            entry["output_enabled"] = None
                        try:
                            entry["current_setpoint"] = sc.get_current_setpoint()
                        except Exception:
                            # use cached if available
                            entry["current_setpoint"] = self._last_setpoints.get(slot)
                        try:
                            entry["measured_current"] = sc.measure_current()
                        except Exception:
                            entry["measured_current"] = None
                        try:
                            entry["measured_voltage"] = sc.measure_voltage()
                        except Exception:
                            entry["measured_voltage"] = None
                    except Exception as exc:
                        entry["error"] = str(exc)
                    res.append(entry)
            else:
                # Fallback legacy: single/unknown channel count
                ch_count = int(self.ChannelsPerRack) if self.ChannelsPerRack else 1
                for ch in range(1, ch_count + 1):
                    entry = {"channel": ch}
                    try:
                        try:
                            sc.write(f"I {ch}")
                        except Exception:
                            pass
                        try:
                            entry["output_enabled"] = bool(int(sc.query("OUTP?")))
                        except Exception:
                            entry["output_enabled"] = None
                        try:
                            entry["current_setpoint"] = sc.get_current_setpoint()
                        except Exception:
                            entry["current_setpoint"] = None
                        try:
                            entry["measured_current"] = sc.measure_current()
                        except Exception:
                            entry["measured_current"] = None
                        try:
                            entry["measured_voltage"] = sc.measure_voltage()
                        except Exception:
                            entry["measured_voltage"] = None
                    except Exception as exc:
                        entry["error"] = str(exc)
                    res.append(entry)
        return json.dumps(res)

    # ---- DS_PDU-like batch output control ----
    @command(
        dtype_in=[int],
        doc_in="Set output states in batch order. For discovered outputs, order follows 'names'/ids. Otherwise, slots 1..ChannelsPerRack.",
    )
    def set_channels_states(self, outputs: List[int]) -> None:
        with self._lock:
            sc = self._with_scpi()
            try:
                if getattr(self, "_outputs_info", None):
                    pairs = list(zip(self._outputs_info, outputs))
                    for info, val in pairs:
                        slot = int(info.get("slot") or 1)
                        try:
                            self._select_slot(slot)
                            if int(val):
                                sc.output_on()
                            else:
                                sc.output_off()
                        except Exception as exc:
                            self.warn_stream(f"set_channels_states: slot {slot} -> {val} failed: {exc}")
                else:
                    # Fallback: use configured channel count
                    try:
                        ch = int(self.ChannelsPerRack) if self.ChannelsPerRack else len(outputs)
                    except Exception:
                        ch = len(outputs)
                    for idx, val in enumerate(outputs[: max(0, ch) ]):
                        slot = idx + 1
                        try:
                            try:
                                sc.write(f"I {slot}")
                            except Exception:
                                pass
                            if int(val):
                                sc.output_on()
                            else:
                                sc.output_off()
                        except Exception as exc:
                            self.warn_stream(f"set_channels_states: slot {slot} -> {val} failed: {exc}")
            finally:
                # no return value; Tango command completion indicates success unless exception escapes
                pass

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


class DS_iTest_PSU(ITestPSU):
    """Alias class to match DS_* naming convention used by Astor/DB."""
    pass

def main() -> None:
    run((DS_iTest_PSU,))


if __name__ == "__main__":
    main()
