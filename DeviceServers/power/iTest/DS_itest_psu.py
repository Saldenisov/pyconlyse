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
    
    # Default polling rate - can be overridden by Tango DB property
    _default_polling_rate = 1000  # Default 1000ms instead of 100ms
    
    # Logging levels
    LOG_MIN = 0    # Only errors, commands, and init
    LOG_NORMAL = 1 # Default level 
    LOG_MAX = 2    # Full debugging including SCPI

    # Device properties (defaults)
    NumberOfSlots = device_property(dtype=int, default_value=8)
    Host = device_property(dtype=str, default_value="")
    Port = device_property(dtype=int, default_value=5025)
    EOL = device_property(dtype=str, default_value="\n")
    LogLevel = device_property(dtype=int, default_value=0)  # LOG_MIN by default
    # Polling rate for slot values (milliseconds)
    polling_rate = device_property(dtype=int, default_value=1000)  # Default 1000ms
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
        self._config_limits: Dict[int, Tuple[float, float]] = {}  # slot_id -> (min_limit, max_limit)
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
        
        # Set log level from command line if provided, otherwise use property
        if hasattr(self.__class__, '_default_log_level'):
            self.LogLevel = self.__class__._default_log_level
        
        # Get polling rate from Tango DB property, fallback to default
        self._polling_rate = int(getattr(self, "polling_rate", self._default_polling_rate) or self._default_polling_rate)
        self.polling_main = self._polling_rate  # Set the base class polling rate
        
        self._log_normal(f"Device properties loaded: Host='{self._host}', Port={self._port}, EOL={repr(self._eol)}, PollingRate={self._polling_rate}ms", True)

        # Apply config property early to set up names mapping
        self.info("Applying initial config property...", True)
        self._apply_config_property()
        
        # Let base class init run (sets archive, calls find_device(), etc.)
        self.info("Calling super().init_device() - this will call find_device()", True)
        super().init_device()
        self.info("super().init_device() completed", True)

        # Configure change events for attributes
        self._configure_change_events()
        
        # Final state - only set to INIT if connection failed
        if self._device_id_internal == -1:
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

    @attribute(
        label="Polling Rate (ms)",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Current polling rate in milliseconds for slot value updates",
    )
    def polling_rate_ms(self) -> int:
        return int(getattr(self, '_polling_rate', self._default_polling_rate))
    
    def _configure_change_events(self):
        """Configure change events for the relevant attributes"""
        attributes_to_configure = ['states', 'currents_setpoint', 'currents_meas', 'names', 'current_limits']
        
        for attr_name in attributes_to_configure:
            try:
                # Enable change events for this attribute
                self.set_change_event(attr_name, True, False)
                self.info(f"Configured change events for {attr_name}", True)
            except Exception as e:
                self.info(f"Failed to configure change events for {attr_name}: {e}", True)
    
    def _log_min(self, message: str, printing: bool = False):
        """Log only if level is LOG_MIN or higher (errors, commands, init)"""
        log_level = getattr(self, 'LogLevel', self.LOG_MIN)
        if log_level >= self.LOG_MIN:
            self.info(message, printing)
    
    def _log_normal(self, message: str, printing: bool = False):
        """Log only if level is LOG_NORMAL or higher (default operations)"""
        log_level = getattr(self, 'LogLevel', self.LOG_MIN)
        if log_level >= self.LOG_NORMAL:
            self.info(message, printing)
    
    def _log_max(self, message: str, printing: bool = False):
        """Log only if level is LOG_MAX (full debugging including SCPI)"""
        log_level = getattr(self, 'LogLevel', self.LOG_MIN)
        if log_level >= self.LOG_MAX:
            self.info(message, printing)

    # Helper: apply alias mapping from Tango device property 'config' (JSON string)
    def _apply_config_property(self):
        try:
            # Initialize config_limits if not exists
            if not hasattr(self, '_config_limits'):
                self._config_limits = {}
                
            js = str(getattr(self, "config", "") or "")
            self.info(f"Config property value: '{js[:200]}{'...' if len(js) > 200 else ''}'", True)
            
            if not js:
                self.info("No config property set, using default slot names", True)
                return
                
            data = json.loads(js)
            self.info(f"Parsed config data: {data}", True)
            
            if isinstance(data, dict):
                updated = dict(self._config_map)
                self._config_limits = {}
                for k, v in data.items():
                    ks = str(k)
                    # Handle both "Slot N" and "SN" formats
                    slot_num = None
                    if ks.upper().startswith("SLOT "):
                        try:
                            # Extract slot number from "Slot N" or "Slot N (model)"
                            slot_part = ks.split("(")[0].strip()  # Remove model part if present
                            slot_num = int(slot_part.split()[-1])
                        except Exception:
                            continue
                    elif ks.upper().startswith("S"):
                        try:
                            slot_num = int(ks[1:])
                        except Exception:
                            continue
                    
                    if slot_num and slot_num in self._ids:
                        self.info(f"Processing config for slot {slot_num}: {v}", True)
                        # Handle tuple format (name, [min_limit, max_limit]) or string format
                        if isinstance(v, (list, tuple)) and len(v) >= 2:
                            alias = str(v[0])
                            limits = v[1] if isinstance(v[1], (list, tuple)) and len(v[1]) >= 2 else [-5.0, 15.0]
                            updated[f"S{slot_num}"] = alias
                            self._config_limits[slot_num] = (float(limits[0]), float(limits[1]))
                            self.info(f"Set slot {slot_num} alias to '{alias}' with limits {limits}", True)
                        else:
                            updated[f"S{slot_num}"] = str(v)
                            self._config_limits[slot_num] = (-5.0, 15.0)  # Default limits
                            self.info(f"Set slot {slot_num} alias to '{v}' with default limits", True)
                    else:
                        self.info(f"Skipping config entry '{k}': slot_num={slot_num}, _ids={self._ids}", True)
                        
                self._config_map = updated
                # Update names for existing ids
                old_names = self._names.copy() if hasattr(self, '_names') else []
                self._names = [self._config_map.get(f"S{i}", f"Slot {i}") for i in self._ids]
                self.info(f"Updated config_map: {self._config_map}", True)
                self.info(f"Updated slot names: {self._names}", True)
                self.info(f"Updated config_limits: {self._config_limits}", True)
                
                # Push change events if names or limits changed
                if old_names != self._names:
                    try:
                        self.push_change_event("names", self._names)
                        self.info("Pushed names change event", True)
                    except Exception as e:
                        self.info(f"Failed to push names change event: {e}", True)
                        
                try:
                    limits_array = self.current_limits()
                    self.push_change_event("current_limits", limits_array)
                    self.info("Pushed current_limits change event", True)
                except Exception as e:
                    self.info(f"Failed to push current_limits change event: {e}", True)
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
    )
    def states(self) -> List[int]:
        return list(self._states)

    @attribute(
        label="Currents Setpoint (A)",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def currents_setpoint(self) -> List[float]:
        return list(self._currents_sp)

    @attribute(
        label="Currents Measured (A)",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def currents_meas(self) -> List[float]:
        return list(self._currents_meas)

    @attribute(
        label="Current Limits (Min/Max)",
        dtype=[float],
        max_dim_x=128,  # pairs of min/max for each slot
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Current limits as [min1, max1, min2, max2, ...] for each slot",
    )
    def current_limits(self) -> List[float]:
        """Return flattened list of [min_limit, max_limit] pairs for each slot"""
        result = []
        for slot_id in self._ids:
            limits = self._config_limits.get(slot_id, (-5.0, 15.0))
            result.extend([float(limits[0]), float(limits[1])])
        return result

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
            self._log_min("Creating ITestSCPI instance...", True)
            log_level = getattr(self, 'LogLevel', self.LOG_NORMAL)
            self._scpi = ITestSCPI(self._host, port=self._port, timeout=3.0, eol=self._eol, log_level=log_level)
            self._log_min("ITestSCPI instance created successfully", True)
            
            self._log_max("Calling _scpi.connect()...", True)
            self._scpi.connect()
            self._log_min(f"SCPI connection established to {self._host}:{self._port}", True)
            
            # Auto-discover slots and apply aliases from config
            self._log_normal("Starting slot discovery...", True)
            try:
                self.discover_slots()
                self._log_min("Slot discovery completed successfully", True)
            except Exception as exc:
                self.error(f"Slot discovery failed (continuing): {exc}")
                
            self._log_max("Setting device state to ON", True)
            self.set_state(DevState.ON)
            
            # Set device ID to indicate successful connection (required by base class)
            self._device_id_internal = 1
            
            # Initial refresh
            self._log_normal("Getting initial controller status...", True)
            self.get_controller_status()
            self._log_min("find_device() completed successfully", True)
            
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

    def get_controller_status_local(self) -> int:
        """Implementation of base class abstract method for automatic polling"""
        self._log_max("=== get_controller_status_local() called ===", True)
        
        if not self._scpi:
            self._log_normal("No SCPI connection (_scpi is None) - setting state to STANDBY", True)
            self.set_state(DevState.STANDBY)
            return 1  # Error code
            
        self._log_max(f"SCPI connection available - reading status for {self._slot_count} slots", True)
        
        try:
            self._log_max("Reading all slot states...", True)
            old_states = self._states.copy()
            self._states = self._scpi.read_all_states(self._ids)
            self._log_max(f"Slot states: {self._states}", True)
            
            # Push change event if states changed
            if old_states != self._states:
                try:
                    self.push_change_event("states", self._states)
                except Exception as e:
                    self._log_normal(f"Failed to push states change event: {e}", True)
            
            self._log_max("Measuring all slot currents...", True)
            old_currents_meas = self._currents_meas.copy()
            self._currents_meas = self._scpi.measure_all_currents(self._ids)
            self._log_max(f"Measured currents: {self._currents_meas}", True)
            
            # Push change event if measured currents changed
            if old_currents_meas != self._currents_meas:
                try:
                    self.push_change_event("currents_meas", self._currents_meas)
                except Exception as e:
                    self._log_normal(f"Failed to push currents_meas change event: {e}", True)
            
            self._log_max("Status refresh completed - setting state to ON", True)
            self.set_state(DevState.ON)
            return 0  # Success
            
        except Exception as exc:
            self.error(f"Status refresh failed: {exc}")
            self._log_normal(f"get_controller_status_local() failed: {exc}", True)
            return 1  # Error code
    
    @command
    def get_controller_status(self):
        """Manual command to refresh status - calls the local implementation"""
        return self.get_controller_status_local()

    @command(dtype_in=[int])
    def set_output_state(self, args: List[int]):
        """
        args = [slotIndex, state]
        state: 1 = ON, 0 = OFF
        """
        if not self._scpi:
            self.error("Not connected")
            return
        try:
            if len(args) < 2:
                self.error("set_output_state expects [slotIndex, state]")
                return
        except (TypeError, AttributeError):
            self.error("set_output_state expects [slotIndex, state] - invalid args")
            return
        idx = int(args[0])
        st = 1 if int(args[1]) != 0 else 0
        
        # Add debug logging
        self._log_min(f"=== set_output_state() called - setting slot {idx} output to {'ON' if st else 'OFF'} ===", True)
        
        # Find the array index for this slot ID
        try:
            array_idx = self._ids.index(idx)
        except ValueError:
            self.error(f"Slot {idx} not found in discovered slots {self._ids}")
            return
        
        try:
            if st:
                self._scpi.output_on(idx)
                self._log_min(f"Successfully turned ON slot {idx}", True)
            else:
                self._scpi.output_off(idx)
                self._log_min(f"Successfully turned OFF slot {idx}", True)
            
            self._states[array_idx] = st
            
            # Push change event for state update
            try:
                self.push_change_event("states", self._states)
            except Exception as e:
                self._log_normal(f"Failed to push states change event: {e}", True)
            
            self.set_state(DevState.ON)
            self._log_normal(f"set_output_state() completed successfully", True)
        except Exception as exc:
            self.error(f"set_output_state failed: {exc}")

    @command(dtype_in=[float])
    def set_current(self, args: List[float]):
        """
        args = [slotIndex, amps]
        """
        self.info(f"=== set_current() called with args: {args} (type: {type(args)}) ===", True)
        
        if not self._scpi:
            self.error("Not connected")
            return
            
        # Safe validation
        try:
            args_len = len(args)
            self.info(f"Args length: {args_len}", True)
        except Exception as e:
            self.error(f"Failed to get args length: {e}")
            return
            
        if args_len < 2:
            self.error("set_current expects [slotIndex, amps]")
            return
            
        try:
            idx = int(args[0])
            amps = float(args[1])
            self.info(f"Parsed: slot={idx}, current={amps:.3f}A", True)
        except Exception as e:
            self.error(f"Failed to parse arguments: {e}")
            return
        
        # Add debug logging
        self._log_min(f"=== set_current() called - setting slot {idx} current to {amps:.3f} A ===", True)
        
        # Find the array index for this slot ID
        try:
            array_idx = self._ids.index(idx)
        except ValueError:
            self.error(f"Slot {idx} not found in discovered slots {self._ids}")
            return
        
        # Validate current limits before setting
        limits = self._config_limits.get(idx)
        if limits:
            min_limit, max_limit = limits
            if amps < min_limit or amps > max_limit:
                self.error(f"Current value {amps:.3f}A is outside limits [{min_limit}, {max_limit}]A for slot {idx}")
                return
            self._log_min(f"Current {amps:.3f}A is within limits [{min_limit}, {max_limit}]A for slot {idx}", True)
        else:
            self._log_normal(f"No limits configured for slot {idx}, allowing {amps:.3f}A", True)
        
        try:
            self._scpi.set_current(idx, amps)
            old_setpoints = self._currents_sp.copy()
            self._currents_sp[array_idx] = amps
            
            # Push change event for setpoint update
            try:
                self.push_change_event("currents_setpoint", self._currents_sp)
            except Exception as e:
                self._log_normal(f"Failed to push currents_setpoint change event: {e}", True)
            
            self._log_min(f"Successfully set slot {idx} current to {amps:.3f} A", True)
            self._log_normal(f"set_current() completed successfully", True)
        except Exception as exc:
            self.error(f"set_current failed: {exc}")

    @command
    def turn_on(self):
        self.info("=== turn_on() called - turning ON all slots ===", True)
        if not self._scpi:
            self.error("Not connected")
            return
        
        success_count = 0
        for i, slot_id in enumerate(self._ids):
            try:
                self.info(f"Turning ON slot {slot_id}...", True)
                self._scpi.output_on(slot_id)
                self._states[i] = 1
                success_count += 1
                self.info(f"Successfully turned ON slot {slot_id}", True)
            except Exception as exc:
                self.error(f"Failed to turn ON slot {slot_id}: {exc}")
        
        self.info(f"turn_on() completed - {success_count}/{len(self._ids)} slots turned ON", True)
        self.set_state(DevState.ON)

    @command
    def turn_off(self):
        self.info("=== turn_off() called - turning OFF all slots ===", True)
        if not self._scpi:
            self.error("Not connected")
            return
        
        success_count = 0
        for i, slot_id in enumerate(self._ids):
            try:
                self.info(f"Turning OFF slot {slot_id}...", True)
                self._scpi.output_off(slot_id)
                self._states[i] = 0
                success_count += 1
                self.info(f"Successfully turned OFF slot {slot_id}", True)
            except Exception as exc:
                self.error(f"Failed to turn OFF slot {slot_id}: {exc}")
        
        self.info(f"turn_off() completed - {success_count}/{len(self._ids)} slots turned OFF", True)
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
    import sys
    import argparse
    
    # Parse command line arguments for logging
    parser = argparse.ArgumentParser(description='iTest PSU Device Server')
    parser.add_argument('--log_min', action='store_true', 
                       help='Minimal logging (errors, commands, init only) - DEFAULT')
    parser.add_argument('--log_normal', action='store_true', 
                       help='Normal logging (default operations without SCPI details)')
    parser.add_argument('--log_max', action='store_true', 
                       help='Maximum logging (full debugging including SCPI)')
    
    # Parse only known args to avoid conflicts with Tango args
    args, unknown = parser.parse_known_args()
    
    # Set log level based on arguments
    log_level = DS_iTest_PSU.LOG_MIN  # default is minimal logging
    if args.log_max:
        log_level = DS_iTest_PSU.LOG_MAX
    elif args.log_normal:
        log_level = DS_iTest_PSU.LOG_NORMAL
    
    # Store log level as class variable for new instances
    DS_iTest_PSU._default_log_level = log_level
    
    # Remove our custom args from sys.argv so Tango doesn't see them
    if args.log_min or args.log_normal or args.log_max:
        sys.argv = [sys.argv[0]] + unknown
    
    print(f"Starting iTest PSU Device Server with log level: {log_level} ({'MIN' if log_level == 0 else 'MAX' if log_level == 2 else 'NORMAL'})")
    DS_iTest_PSU.run_server()
