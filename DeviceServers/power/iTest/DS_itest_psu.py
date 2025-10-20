#!/usr/bin/env python3
"""
iTest PSU Tango Device Server (from scratch)

- Device name: elyse/pdu/itest (example)
- Device property 'Host' defines IP address
- Attribute 'config' (RW, JSON string) maps slot names to aliases
- names (RO, str[]) aliases for 8 slots (ordered by slot index 1..8)
- ids (RO, int[]) 1..8
- states (RO, int[]) per-slot output states (0/1)
- currents_setpoint (RO, double[]) last known setpoints
- currents_meas (RO, double[]) measured currents

Commands:
- find_device() → connect SCPI
- get_controller_status() → refresh arrays
- set_output_state([slotIndex, state]) (state: 0/1)
- set_current([slotIndex, amps])
- turn_on() / turn_off() affect all outputs

Notes:
- Uses easy-scpi via ITestSCPI wrapper
- Defaults to 8 slots
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple, Union

from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, command, device_property

from DeviceServers.base.general import DS_General
from DeviceServers.power.iTest.scpi_client import ITestSCPI, SCPIError


class DS_iTest_PSU(DS_General):
    _version_ = "0.1"
    _model_ = "iTest PSU (BiLT)"

    # Device properties (defaults)
    NumberOfSlots = device_property(dtype=int, default_value=8)
    Host = device_property(dtype=str, default_value="")
    Port = device_property(dtype=int, default_value=5025)
    EOL = device_property(dtype=str, default_value="\n")
    # Slot alias mapping provided via Tango device property 'config' (JSON string)
    config = device_property(dtype=str, default_value="")

    # Runtime state
    def init_device(self):
        # Pre-initialize arrays and config map so super().init_device() (which calls find_device()) can use them
        self.info("=== iTest PSU Device Server Starting Initialization ===", True)
        
        try:
            sc = int(getattr(self, "NumberOfSlots", 8) or 8)
            self.info(f"NumberOfSlots property: {sc}", True)
        except Exception as e:
            sc = 8
            self.info(f"NumberOfSlots property failed, using default: {sc}. Error: {e}", True)
            
        self._slot_count = max(1, int(sc))
        self._ids: List[int] = list(range(1, self._slot_count + 1))
        self._config_map: Dict[str, str] = {f"S{i}": f"Slot {i}" for i in self._ids}
        self._names: List[str] = [self._config_map[f"S{i}"] for i in self._ids]
        self._states: List[int] = [0] * self._slot_count
        self._currents_sp: List[float] = [0.0] * self._slot_count
        self._currents_meas: List[float] = [0.0] * self._slot_count
        self._scpi: ITestSCPI | None = None
        
        self.info(f"Initialized with {self._slot_count} slots, IDs: {self._ids}", True)

        # Read properties for info (lazy-loaded in find_device too)
        self._host = (getattr(self, "Host", "") or "").strip()
        self._port = int(getattr(self, "Port", 5025) or 5025)
        self._eol = str(getattr(self, "EOL", "\n") or "\n")
        
        self.info(f"Device properties loaded: Host='{self._host}', Port={self._port}, EOL={repr(self._eol)}", True)

        # Let base class init run (sets archive, calls find_device(), etc.)
        self.info("Calling super().init_device() - this will call find_device()", True)
        super().init_device()
        self.info("super().init_device() completed", True)

        # Initial state/info
        self.set_state(DevState.INIT)
        self.info(
            f"iTest PSU initialization completed. Current state: {self.get_state()}. Host: '{self._host or '(empty)'}", True)

    # ---- Attributes ----
    @attribute(
        label="Host (property)",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Effective Host loaded from Tango device property",
    )
    def host_property(self) -> str:
        return self._host or ""

    @attribute(
        label="Port (property)",
        dtype=int,
        display_level=DispLevel.EXPERT,
        access=AttrWriteType.READ,
    )
    def port_property(self) -> int:
        return int(self._port)

    @attribute(
        label="EOL (property)",
        dtype=str,
        display_level=DispLevel.EXPERT,
        access=AttrWriteType.READ,
    )
    def eol_property(self) -> str:
        return str(self._eol)

    # Helper: apply alias mapping from Tango device property 'config' (JSON string)
    def _apply_config_property(self):
        try:
            js = str(getattr(self, "config", "") or "")
            if not js:
                return
            data = json.loads(js)
            if isinstance(data, dict):
                updated = dict(self._config_map)
                for k, v in data.items():
                    ks = str(k)
                    if ks.upper().startswith("S"):
                        try:
                            idx = int(ks[1:])
                            if idx in self._ids:
                                updated[f"S{idx}"] = str(v)
                        except Exception:
                            continue
                self._config_map = updated
                # Update names for existing ids
                self._names = [self._config_map.get(f"S{i}", f"Slot {i}") for i in self._ids]
        except Exception as exc:
            self.error(f"Failed to apply 'config' property: {exc}")

    @attribute(
        label="Outputs names",
        dtype=[str],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=1000,
    )
    def names(self) -> List[str]:
        return list(self._names)

    @attribute(
        label="Outputs ids",
        dtype=[int],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=1000,
    )
    def ids(self) -> List[int]:
        return list(self._ids)

    @attribute(
        label="Outputs states",
        dtype=[int],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=500,
    )
    def states(self) -> List[int]:
        return list(self._states)

    @attribute(
        label="Currents Setpoint (A)",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=500,
    )
    def currents_setpoint(self) -> List[float]:
        return list(self._currents_sp)

    @attribute(
        label="Currents Measured (A)",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=500,
    )
    def currents_meas(self) -> List[float]:
        return list(self._currents_meas)

    # ---- Commands ----
    @command
    def find_device(self):
        self.info("=== find_device() called ===", True)
        
        # Lazy-load properties in case superclass init calls this before our fields are set
        self.info("Loading device properties...", True)
        try:
            if not hasattr(self, "_host") or self._host is None or str(self._host).strip() == "":
                self._host = (getattr(self, "Host", "") or "").strip()
                self.info(f"Loaded Host property: '{self._host}'", True)
            if not hasattr(self, "_port") or self._port is None:
                self._port = int(getattr(self, "Port", 5025) or 5025)
                self.info(f"Loaded Port property: {self._port}", True)
            if not hasattr(self, "_eol") or self._eol is None:
                self._eol = str(getattr(self, "EOL", "\n") or "\n")
                self.info(f"Loaded EOL property: {repr(self._eol)}", True)
        except Exception as e:
            # Fallback defaults if properties not yet available
            self.info(f"Property loading failed, using fallbacks. Error: {e}", True)
            self._host = str(getattr(self, "Host", "") or "").strip()
            self._port = int(getattr(self, "Port", 5025) or 5025)
            self._eol = str(getattr(self, "EOL", "\n") or "\n")
            self.info(f"Fallback values: Host='{self._host}', Port={self._port}, EOL={repr(self._eol)}", True)

        if not self._host:
            self.error("Host device property is empty; set it in Tango DB and retry.")
            self.set_state(DevState.FAULT)
            self.info("find_device() failed: Host property empty", True)
            return
            
        self.info(f"Attempting SCPI connection to {self._host}:{self._port} with timeout=3.0s", True)
        
        try:
            self.info("Creating ITestSCPI instance...", True)
            self._scpi = ITestSCPI(self._host, port=self._port, timeout=3.0, eol=self._eol)
            self.info("ITestSCPI instance created successfully", True)
            
            self.info("Calling _scpi.connect()...", True)
            self._scpi.connect()
            self.info(f"SCPI connection established to {self._host}:{self._port}", True)
            
            # Auto-discover slots and apply aliases from config
            self.info("Starting slot discovery...", True)
            try:
                self.discover_slots()
                self.info("Slot discovery completed successfully", True)
            except Exception as exc:
                self.error(f"Slot discovery failed (continuing): {exc}")
                
            self.info("Setting device state to ON", True)
            self.set_state(DevState.ON)
            
            # Initial refresh
            self.info("Getting initial controller status...", True)
            self.get_controller_status()
            self.info("find_device() completed successfully", True)
            
        except Exception as exc:
            self._scpi = None
            self.error(f"Connection failed: {exc}")
            self.info(f"find_device() failed: {exc}", True)
            self.set_state(DevState.FAULT)

    @command
    def discover_slots(self):
        """Discover installed slots via SCPI INST:LIST? and update ids/names.
        Aliases are taken from config (S{slot} -> alias) when available.
        """
        self.info("=== discover_slots() called ===", True)
        
        if not self._scpi:
            self.error("Not connected")
            self.info("discover_slots() failed: No SCPI connection", True)
            return
            
        try:
            self.info("Calling _scpi.list_slots() to discover installed slots...", True)
            pairs = self._scpi.list_slots()  # [(slot, model)]
            self.info(f"Raw slot discovery result: {pairs}", True)
            
            if not pairs:
                self.info("No slots discovered via INST:LIST?", True)
                return
                
            slots = [int(s) for s, _ in pairs]
            models = {int(s): str(m) for s, m in pairs}
            self.info(f"Parsed slots: {slots}, models: {models}", True)
            
            self._ids = list(slots)
            self._slot_count = len(self._ids)
            self.info(f"Updated slot count: {self._slot_count}, IDs: {self._ids}", True)
            
            # Apply aliases from property first
            self.info("Applying config property aliases...", True)
            self._apply_config_property()
            
            # names from config alias or fallback to Slot N (model)
            new_names: List[str] = []
            for s in self._ids:
                alias = self._config_map.get(f"S{s}")
                if alias:
                    new_names.append(str(alias))
                    self.info(f"Slot {s}: using alias '{alias}'", True)
                else:
                    mdl = models.get(s, "?")
                    name = f"Slot {s} ({mdl})"
                    new_names.append(name)
                    self.info(f"Slot {s}: using default name '{name}'", True)
                    
            self._names = new_names
            self.info(f"Final slot names: {self._names}", True)
            
            # resize arrays
            self.info("Resizing state and current arrays...", True)
            self._states = [0] * self._slot_count
            self._currents_sp = [0.0] * self._slot_count
            self._currents_meas = [0.0] * self._slot_count
            
            self.info(f"Slot discovery completed successfully. Discovered {self._slot_count} slots: {self._ids}", True)
            
        except Exception as exc:
            self.error(f"discover_slots failed: {exc}")
            self.info(f"discover_slots() failed with exception: {exc}", True)

    @command
    def get_controller_status(self):
        self.info("=== get_controller_status() called ===", True)
        
        if not self._scpi:
            self.info("No SCPI connection (_scpi is None) - setting state to STANDBY", True)
            self.set_state(DevState.STANDBY)
            return
            
        self.info(f"SCPI connection available - reading status for {self._slot_count} slots", True)
        
        try:
            self.info("Reading all slot states...", True)
            self._states = self._scpi.read_all_states(self._slot_count)
            self.info(f"Slot states: {self._states}", True)
            
            self.info("Measuring all slot currents...", True)
            self._currents_meas = self._scpi.measure_all_currents(self._slot_count)
            self.info(f"Measured currents: {self._currents_meas}", True)
            
            self.info("Status refresh completed - setting state to ON", True)
            self.set_state(DevState.ON)
            
        except Exception as exc:
            self.error(f"Status refresh failed: {exc}")
            self.info(f"get_controller_status() failed: {exc}", True)

    @command(dtype_in=[int])
    def set_output_state(self, args: List[int]):
        """
        args = [slotIndex, state]
        state: 1 = ON, 0 = OFF
        """
        if not self._scpi:
            self.error("Not connected")
            return
        if not args or len(args) < 2:
            self.error("set_output_state expects [slotIndex, state]")
            return
        idx = int(args[0])
        st = 1 if int(args[1]) != 0 else 0
        
        # Add debug logging
        self.info(f"Setting slot {idx} output to {'ON' if st else 'OFF'}", True)
        
        try:
            if st:
                self._scpi.output_on(idx)
                self.info(f"Successfully turned ON slot {idx}", True)
            else:
                self._scpi.output_off(idx)
                self.info(f"Successfully turned OFF slot {idx}", True)
            self._states[idx - 1] = st
            self.set_state(DevState.ON)
        except Exception as exc:
            self.error(f"set_output_state failed: {exc}")

    @command(dtype_in=[float])
    def set_current(self, args: List[float]):
        """
        args = [slotIndex, amps]
        """
        if not self._scpi:
            self.error("Not connected")
            return
        if not args or len(args) < 2:
            self.error("set_current expects [slotIndex, amps]")
            return
        idx = int(args[0])
        amps = float(args[1])
        
        # Add debug logging
        self.info(f"Setting slot {idx} current to {amps:.3f} A", True)
        
        try:
            self._scpi.set_current(idx, amps)
            self._currents_sp[idx - 1] = amps
            self.info(f"Successfully set slot {idx} current to {amps:.3f} A", True)
        except Exception as exc:
            self.error(f"set_current failed: {exc}")

    @command
    def turn_on(self):
        if not self._scpi:
            self.error("Not connected")
            return
        for i in range(1, self._slot_count + 1):
            try:
                self._scpi.output_on(i)
                self._states[i - 1] = 1
            except Exception:
                pass
        self.set_state(DevState.ON)

    @command
    def turn_off(self):
        if not self._scpi:
            self.error("Not connected")
            return
        for i in range(1, self._slot_count + 1):
            try:
                self._scpi.output_off(i)
                self._states[i - 1] = 0
            except Exception:
                pass
        self.set_state(DevState.STANDBY)

    @command
    def reload_connection(self):
        """Reload Host/Port/EOL from device properties and reconnect."""
        # Close existing connection
        try:
            if self._scpi:
                self._scpi.close()
        except Exception:
            pass
        self._scpi = None
        # Refresh properties
        try:
            self._host = (getattr(self, "Host", "") or "").strip()
            self._port = int(getattr(self, "Port", 5025) or 5025)
            self._eol = str(getattr(self, "EOL", "\n") or "\n")
            self.info(f"Reloaded properties: host={self._host}, port={self._port}, eol={repr(self._eol)}")
        except Exception as exc:
            self.error(f"Failed to reload properties: {exc}")
            return
        # Reconnect
        self.find_device()


if __name__ == "__main__":
    DS_iTest_PSU.run_server()
