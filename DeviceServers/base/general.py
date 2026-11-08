from sys import modules as _refactor_modules

from DeviceServers.base.general_methods_write_always_on_value import _bind_general_methods_write_always_on_value

from DeviceServers.base.general_methods_int_time import _bind_general_methods_int_time

import ast
import json
import os
import time
import zlib
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, RLock, Thread, current_thread
from typing import Any, Dict, Union

import msgpack
import numpy as np
from tango import AttrWriteType, DevState, DispLevel
from tango.server import Device, attribute, command, device_property, pipe

from DeviceServers.base.power_dependency import (
    PowerDependencyState,
    read_power_dependency_state,
)
from DeviceServers.base.hardware_lifecycle import (
    HardwareConnectionState,
    InitializationState,
    lifecycle_value,
)

PROCESS_STARTED_AT_UTC = datetime.now(timezone.utc).isoformat()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Centralized global settings for all DeviceServers
# These can be overridden via a single JSON config file, environment variables, or at runtime via commands


def _str_to_bool(val: str) -> bool:
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


# Defaults for global settings
CONFIG_DEFAULTS = {
    "DISABLE_ARCHIVE": False,  # Disable archive connections globally
    "ARCHIVE_TIMEOUT_SECONDS": 5,  # Default archive connection timeout
}

# Determine config file path
CONFIG_FILE_ENV = "PYCONLYSE_GLOBAL_CONFIG"
DEFAULT_CONFIG_FILENAME = "global_settings.json"


def _default_config_path() -> str:
    # Place default in DeviceServers/ folder
    return str(Path(__file__).resolve().parents[1] / DEFAULT_CONFIG_FILENAME)


# Initialize GLOBAL_SETTINGS from defaults, then file, then env
GLOBAL_SETTINGS = CONFIG_DEFAULTS.copy()


def _load_global_settings_from_file() -> str:
    path = os.environ.get(CONFIG_FILE_ENV, _default_config_path())
    try:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k in CONFIG_DEFAULTS:
                    if k in data:
                        if k == "DISABLE_ARCHIVE":
                            GLOBAL_SETTINGS[k] = (
                                data[k]
                                if isinstance(data[k], bool)
                                else _str_to_bool(str(data[k]))
                            )
                        elif k == "ARCHIVE_TIMEOUT_SECONDS":
                            try:
                                GLOBAL_SETTINGS[k] = int(data[k])
                            except Exception:
                                pass
        return path
    except Exception:
        return path


# Load from file first
_current_config_path = _load_global_settings_from_file()

# Then overlay env vars
try:
    if "DISABLE_ARCHIVE" in os.environ:
        GLOBAL_SETTINGS["DISABLE_ARCHIVE"] = _str_to_bool(
            os.environ.get("DISABLE_ARCHIVE", "")
        )
    if "ARCHIVE_TIMEOUT_SECONDS" in os.environ:
        GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] = int(
            os.environ.get("ARCHIVE_TIMEOUT_SECONDS", "5")
        )
except Exception:
    # Fallback silently if env parsing fails
    pass

from utilities.datastructures.mes_independent.measurments_dataclass import (
    ArchiveData,
    Array,
    Scalar,
)

standard_str_output = "str: 0 if success, else error."


class ConfigurationError(ValueError):
    """Raised when a Tango property cannot be treated as inert data."""


def operation_succeeded(result) -> bool:
    """Return true only for explicit numeric-zero adapter results."""
    return (
        isinstance(result, (int, float))
        and not isinstance(result, bool)
        and result == 0
    )


def _validate_config_value(value, *, path="parameters"):
    """Return only JSON-compatible values accepted by device configuration."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        return [
            _validate_config_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        return tuple(
            _validate_config_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, dict):
        validated = {}
        for key, item in value.items():
            if not isinstance(key, (str, int, float, bool)):
                raise ConfigurationError(
                    f"{path} contains unsupported key type {type(key).__name__}"
                )
            validated[key] = _validate_config_value(item, path=f"{path}[{key!r}]")
        return validated
    raise ConfigurationError(
        f"{path} contains unsupported value type {type(value).__name__}"
    )


def parse_structured_config(raw_value, *, name="parameters"):
    """Parse JSON first, then legacy Python literals without executing code."""
    if raw_value is None or isinstance(
        raw_value, (dict, list, tuple, int, float, bool)
    ):
        return _validate_config_value(raw_value, path=name)
    if not isinstance(raw_value, str):
        raise ConfigurationError(
            f"{name} must be JSON or a legacy Python literal, got "
            f"{type(raw_value).__name__}"
        )

    source = raw_value.strip()
    if not source:
        raise ConfigurationError(f"{name} cannot be empty")

    try:
        parsed = json.loads(source)
    except json.JSONDecodeError as json_error:
        try:
            parsed = ast.literal_eval(source)
        except (SyntaxError, ValueError) as literal_error:
            raise ConfigurationError(
                f"{name} is neither valid JSON nor a supported legacy literal: "
                f"{literal_error}"
            ) from json_error
    return _validate_config_value(parsed, path=name)


@dataclass
class GeneralOrderInfo:
    order_done: bool
    order_timestamp: int
    ready_to_delete: bool


class DS_General(Device):
    device_id = device_property(dtype=str)
    friendly_name = device_property(dtype=str)
    server_id = device_property(dtype=int)
    always_on = device_property(dtype=int, default_value=0)
    archive_enabled = device_property(dtype=int, default_value=0)
    fault_recovery_enabled = device_property(dtype=int, default_value=1)
    fault_recovery_cooldown_s = device_property(dtype=float, default_value=3.0)
    power_dependency_device = device_property(dtype=str, default_value="")
    power_dependency_output_id = device_property(dtype=int, default_value=0)
    power_on_settle_seconds = device_property(dtype=float, default_value=5.0)
    power_dependency_poll_interval_s = device_property(dtype=float, default_value=1.0)
    power_dependency_reconnect_seconds = device_property(dtype=float, default_value=5.0)
    power_dependency_auto_probe = device_property(dtype=int, default_value=1)
    power_dependency_auto_turn_on = device_property(dtype=int, default_value=0)
    archive = "manip/general/archive"
    # Health checks must not compete with commands that open, close, or
    # configure a transport. Acquisition loops use their own explicit rates.
    polling_main = 1000

    # Expose allowed global variable keys (for management commands)
    ALLOWED_GLOBAL_VARS = tuple(CONFIG_DEFAULTS.keys())
    RULES = {
        "turn_on": [DevState.OFF, DevState.FAULT, DevState.STANDBY, DevState.INIT],
        "turn_off": [DevState.ON, DevState.STANDBY, DevState.INIT, DevState.RUNNING],
        "find_device": [DevState.OFF, DevState.FAULT, DevState.STANDBY, DevState.INIT],
        "get_controller_status": [
            DevState.ON,
            DevState.MOVING,
            DevState.RUNNING,
            DevState.INIT,
            DevState.FAULT,
        ],
    }

    _TRACKING_EVENT_ATTRIBUTES = (
        "State",
        "Status",
        "last_error",
        "process_started_at_utc",
        "initialization_started_at_utc",
        "initialization_completed_at_utc",
        "initialization_duration_ms",
        "last_error_at_utc",
        "error_count",
        "last_state_change_at_utc",
        "hardware_connection_state",
        "initialization_state",
        "hardware_lifecycle_status",
    )

    @property
    def _version_(self):
        raise NotImplementedError

    @property
    def _model_(self):
        raise NotImplementedError

    @pipe(label="DS_Info", doc="General info about DS")
    def read_info_ds(self):
        return (
            "info_ds",
            dict(
                manufacturer=f"{self.__class__.__name__}",
                model=self._model_,
                version_number=self._version_,
                device_id=self.device_id,
            ),
        )

    @attribute(
        label="Always on?",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
    )
    def always_on_value(self):
        return self.always_on

    _general_methods_write_always_on_value = _bind_general_methods_write_always_on_value(_refactor_modules[__name__])
    write_always_on_value = _general_methods_write_always_on_value["write_always_on_value"]

    @attribute(
        label="Friendly name",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
    )
    def device_friendly_name(self):
        return self.friendly_name

    write_device_friendly_name = _general_methods_write_always_on_value["write_device_friendly_name"]

    @attribute(
        label="comments",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Last essential comment.",
        polling_period=polling_main,
    )
    def last_comment(self):
        return self._comment

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, value):
        self._comment = value

    @attribute(
        label="error",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Last error.",
        polling_period=polling_main,
    )
    def last_error(self):
        return self._error

    @attribute(
        label="Process started at (UTC)",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling_main,
    )
    def process_started_at_utc(self):
        return getattr(self, "_process_started_at_utc", PROCESS_STARTED_AT_UTC)

    @attribute(
        label="Initialisation started at (UTC)",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling_main,
    )
    def initialization_started_at_utc(self):
        return getattr(self, "_initialization_started_at_utc", "")

    @attribute(
        label="Initialisation completed at (UTC)",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling_main,
    )
    def initialization_completed_at_utc(self):
        return getattr(self, "_initialization_completed_at_utc", "")

    @attribute(
        label="Initialisation duration (ms)",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling_main,
    )
    def initialization_duration_ms(self):
        return float(getattr(self, "_initialization_duration_ms", 0.0))

    @attribute(
        label="Last error at (UTC)",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling_main,
    )
    def last_error_at_utc(self):
        return getattr(self, "_last_error_at_utc", "")

    @attribute(
        label="Error count since process start",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling_main,
    )
    def error_count(self):
        return int(getattr(self, "_error_count", 0))

    @attribute(
        label="Last Tango state change at (UTC)",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling_main,
    )
    def last_state_change_at_utc(self):
        return getattr(self, "_last_state_change_at_utc", "")

    set_state = _general_methods_write_always_on_value["set_state"]

    set_status = _general_methods_write_always_on_value["set_status"]

    _configure_tracking_events = _general_methods_write_always_on_value["_configure_tracking_events"]

    _push_tracking_event = _general_methods_write_always_on_value["_push_tracking_event"]

    @attribute(
        label="Hardware connection",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Physical power and transport condition; independent from Tango reachability.",
        polling_period=polling_main,
    )
    def hardware_connection_state(self):
        return getattr(self, "_hardware_connection_state", HardwareConnectionState.UNKNOWN.value)

    @attribute(
        label="Initialisation",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Operational initialisation result; independent from power and transport.",
        polling_period=polling_main,
    )
    def initialization_state(self):
        return getattr(self, "_initialization_state", InitializationState.UNKNOWN.value)

    @attribute(
        label="Hardware lifecycle status",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Human-readable explanation for hardware connection and initialisation state.",
        polling_period=polling_main,
    )
    def hardware_lifecycle_status(self):
        return getattr(self, "_hardware_lifecycle_status", "not initialised")

    set_hardware_lifecycle = _general_methods_write_always_on_value["set_hardware_lifecycle"]

    @attribute(
        label="URI",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="The URI of device.",
    )
    def uri(self):
        return self._uri

    error = _general_methods_write_always_on_value["error"]

    warn = _general_methods_write_always_on_value["warn"]

    info = _general_methods_write_always_on_value["info"]


    @command(dtype_in=str)
    def register_client_lock(self, name):
        if name:
            self.locking_client_token = name
            self.locked_client = True

    @command
    def unregister_client_lock(self):
        self.locking_client_token = ""
        self.locked_client = False

    @abstractmethod
    def init_device(self):
        self._process_started_at_utc = PROCESS_STARTED_AT_UTC
        self._initialization_started_at_utc = _utc_now_iso()
        self._initialization_started_monotonic = time.monotonic()
        self._initialization_completed_at_utc = ""
        self._initialization_duration_ms = 0.0
        self._last_error_at_utc = ""
        self._error_count = 0
        self._last_state_change_at_utc = self._initialization_started_at_utc
        self._tracked_tango_state = None
        self._tracked_tango_status = None
        self._tracking_events_ready = False
        self._stop_error_timer()
        self._stop_power_dependency_monitor()
        self._lifecycle_lock = RLock()
        self._fault_recovery_attempts = 0
        self._next_fault_recovery_at = 0.0
        self._last_fault_recovery_error = ""
        self._power_dependency_observed = False
        self._power_dependency_state = PowerDependencyState(
            False, None, "power dependency is not configured"
        )
        self._power_probe_pending = False
        self._power_probe_due_at = 0.0
        self._last_power_probe_error = ""
        self._power_dependency_status = "power dependency is not configured"
        self.set_hardware_lifecycle(
            HardwareConnectionState.UNKNOWN,
            InitializationState.UNKNOWN,
            "device server started; hardware has not been probed",
        )
        self.orders: Dict[str, GeneralOrderInfo] = {}
        self.previous_archive_state: Dict[str, Any] = {}
        self.archive_state: Dict[str, Any] = {}
        self.locking_client_token = ""
        self.locked_client = False
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._status_check_fault = 0
        self.prev_state = DevState.FAULT
        try:
            Device.init_device(self)
        except BaseException:
            self._stop_error_timer()
            raise

        self._configure_tracking_events()
        self._push_tracking_event(
            "process_started_at_utc", self._process_started_at_utc
        )
        self._push_tracking_event(
            "initialization_started_at_utc", self._initialization_started_at_utc
        )

        self._start_error_timer()
        try:
            configuration_valid = True
            if hasattr(self, "parameters"):
                try:
                    self.parameters = parse_structured_config(self.parameters)
                except ConfigurationError as error:
                    self.error(f"Invalid parameters for {self.device_name}: {error}")
                    self.set_state(DevState.FAULT)
                    configuration_valid = False

            if not configuration_valid:
                self.set_hardware_lifecycle(
                    HardwareConnectionState.UNKNOWN,
                    InitializationState.FAILED,
                    "device configuration is invalid",
                )
                self._create_mock_archive()
                self._device_id_internal = -1
                self._uri = b""
                return

            global_disable = bool(GLOBAL_SETTINGS.get("DISABLE_ARCHIVE", False))
            if getattr(self, "archive_enabled", 1) == 0 or global_disable:
                self.info(
                    "Archive disabled: Using mock archive (no connection attempt)", True
                )
                self._create_mock_archive()
            else:
                timeout_val = int(GLOBAL_SETTINGS.get("ARCHIVE_TIMEOUT_SECONDS", 5))
                self._init_archive_connection(timeout_seconds=timeout_val)

            self.set_state(DevState.OFF)
            self._device_id_internal = -1
            self._uri = b""
            power_state = self._observe_power_dependency(force=True, initial=True)
            self._start_power_dependency_monitor()
            if power_state.configured and power_state.powered is not True:
                return
            self.find_device()

            if self._device_id_internal != -1:
                self.set_hardware_lifecycle(
                    HardwareConnectionState.CONNECTED,
                    InitializationState.NOT_REQUESTED,
                    "hardware transport connected; operational initialisation has not been requested",
                )
                self.info(f"{self.device_name} was found.", True)
                if power_state.configured:
                    self.set_state(self.power_dependency_ready_state())
                    if self._power_dependency_auto_turn_on_enabled():
                        settle_seconds = max(0.0, float(self.power_on_settle_seconds or 0.0))
                        self._power_probe_due_at = time.monotonic() + settle_seconds
                        self._power_probe_pending = True
                        self._power_dependency_status = (
                            f"{power_state.detail}; waiting {settle_seconds:.1f}s before "
                            "safe probe and automatic turn_on"
                        )
                        self.info(self._power_dependency_status, True)
                    else:
                        self.info(
                            f"{self.device_name} power is available; awaiting explicit turn_on.",
                            True,
                        )
            else:
                self.set_hardware_lifecycle(
                    HardwareConnectionState.DISCONNECTED,
                    InitializationState.NOT_REQUESTED,
                    "hardware was not found during passive transport probe",
                )
                self.info(f"{self.device_name} was NOT found.", True)
                self.set_state(DevState.FAULT)
                if power_state.configured and power_state.powered is True:
                    self._schedule_power_probe(
                        float(self.power_dependency_reconnect_seconds or 5.0)
                    )
        except BaseException:
            self._stop_error_timer()
            self._stop_power_dependency_monitor()
            raise

    _start_error_timer = _general_methods_write_always_on_value["_start_error_timer"]

    _power_dependency_is_configured = _general_methods_write_always_on_value["_power_dependency_is_configured"]

    _power_dependency_auto_turn_on_enabled = _general_methods_write_always_on_value["_power_dependency_auto_turn_on_enabled"]

    _read_power_dependency_state = _general_methods_write_always_on_value["_read_power_dependency_state"]

    _power_dependency_proxy = (staticmethod)(_general_methods_write_always_on_value["_power_dependency_proxy"])

    _observe_power_dependency = _general_methods_write_always_on_value["_observe_power_dependency"]

    _apply_power_dependency_state = _general_methods_write_always_on_value["_apply_power_dependency_state"]

    _schedule_power_probe = _general_methods_write_always_on_value["_schedule_power_probe"]

    _mark_hardware_power_off = _general_methods_write_always_on_value["_mark_hardware_power_off"]

    _handle_power_dependency_off = _general_methods_write_always_on_value["_handle_power_dependency_off"]

    _handle_power_dependency_unavailable = _general_methods_write_always_on_value["_handle_power_dependency_unavailable"]

    release_power_dependency_local = _general_methods_write_always_on_value["release_power_dependency_local"]

    power_dependency_ready_state = _general_methods_write_always_on_value["power_dependency_ready_state"]

    _release_power_dependency_transport = _general_methods_write_always_on_value["_release_power_dependency_transport"]

    probe_powered_hardware = _general_methods_write_always_on_value["probe_powered_hardware"]

    _power_dependency_monitor_loop = _general_methods_write_always_on_value["_power_dependency_monitor_loop"]

    _run_power_dependency_probe_if_due = _general_methods_write_always_on_value["_run_power_dependency_probe_if_due"]

    _start_power_dependency_monitor = _general_methods_write_always_on_value["_start_power_dependency_monitor"]

    _stop_power_dependency_monitor = _general_methods_write_always_on_value["_stop_power_dependency_monitor"]

    _stop_error_timer = _general_methods_write_always_on_value["_stop_error_timer"]

    def delete_device(self):
        """Release local maintenance resources when Tango removes this device."""
        self._stop_error_timer()
        self._stop_power_dependency_monitor()
        parent_delete = getattr(super(), "delete_device", None)
        if parent_delete is not None:
            parent_delete()

    @abstractmethod
    def register_variables_for_archive(self):
        self.archive_state["State"] = (self.get_state, "int8")

    send_state_archive = _general_methods_write_always_on_value["send_state_archive"]

    fix_state = _general_methods_write_always_on_value["fix_state"]

    @abstractmethod
    def find_device(self):
        """Sets device_id_internal and uri if applicable"""

    check_func_allowance = _general_methods_write_always_on_value["check_func_allowance"]

    _get_lifecycle_lock = _general_methods_write_always_on_value["_get_lifecycle_lock"]

    _fault_recovery_due = _general_methods_write_always_on_value["_fault_recovery_due"]

    _record_controller_status = _general_methods_write_always_on_value["_record_controller_status"]

    @attribute(label="Fault recovery status", dtype=str, access=AttrWriteType.READ)
    def fault_recovery_status(self) -> str:
        return (
            f"attempts={getattr(self, '_fault_recovery_attempts', 0)}; "
            f"last_error={getattr(self, '_last_fault_recovery_error', '')}"
        )

    @attribute(
        label="Power dependency status",
        dtype=str,
        access=AttrWriteType.READ,
        doc="Read-only Netio dependency state; no PDU output is controlled.",
    )
    def power_dependency_status(self) -> str:
        return str(getattr(self, "_power_dependency_status", "not initialised"))

    _power_dependency_allows_hardware_operation = _general_methods_write_always_on_value["_power_dependency_allows_hardware_operation"]
    del _general_methods_write_always_on_value

    _general_methods_int_time = _bind_general_methods_int_time(_refactor_modules[__name__])
    int_time = _general_methods_int_time["int_time"]

    _init_archive_connection = _general_methods_int_time["_init_archive_connection"]

    _create_mock_archive = _general_methods_int_time["_create_mock_archive"]

    @property
    def device_name(self) -> str:
        friendly_name = getattr(self, "friendly_name", None)
        if not friendly_name:
            return f"Device Unknown {self.__class__.__name__}"
        device_id = getattr(self, "device_id", None)
        if device_id:
            return f"Device {device_id} {friendly_name}"
        return f"Device {friendly_name}"

    get_controller_status = (command(polling_period=polling_main))(_general_methods_int_time["get_controller_status"])

    @abstractmethod
    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    turn_on = (command)(_general_methods_int_time["turn_on"])

    @abstractmethod
    def turn_on_local(self) -> Union[int, str]:
        pass

    turn_off = (command)(_general_methods_int_time["turn_off"])

    recover = (command(dtype_out=str))(_general_methods_int_time["recover"])

    @abstractmethod
    def turn_off_local(self) -> Union[int, str]:
        pass

    write_to_archive = _general_methods_int_time["write_to_archive"]

    compress_data = _general_methods_int_time["compress_data"]

    form_archive_data = _general_methods_int_time["form_archive_data"]

    register_order = (command(
        dtype_in=[
            int,
        ],
        dtype_out=str,
        doc_in="Takes an order",
        doc_out="return name of order",
    ))(_general_methods_int_time["register_order"])

    register_order_local = _general_methods_int_time["register_order_local"]

    @command(dtype_in=str, doc_in="Order name", dtype_out=bool)
    def is_order_ready(self, name):
        res = False
        if name in self.orders:
            order = self.orders[name]
            res = order.order_done
        return res

    @command(dtype_in=str, doc_in="Order name", dtype_out=str)
    def give_order(self, name):
        res = self.give_order_local(name)
        try:
            res = res.tobytes()
        except AttributeError:
            res = str(res).encode("utf-8")
        res = zlib.compress(res)
        return str(res)

    @command(
        dtype_in=str,
        doc_in="Order name",
        dtype_out=int,
        doc_out="0 if Ok -1 if order is not present in orders",
    )
    def stop_order(self, name):
        order = self.orders.get(name)
        if order is None:
            return -1
        order.order_done = True
        return 0

    give_order_local = _general_methods_int_time["give_order_local"]

    # ----- Centralized global settings management commands -----
    set_global_variable = (command(
        dtype_in=[str],
        dtype_out=str,
        doc_in="['name','value'] (global setting to change)",
        doc_out="Result message",
    ))(_general_methods_int_time["set_global_variable"])

    @command(
        dtype_in=str,
        dtype_out=str,
        doc_in="name (global setting to read)",
        doc_out="Value as string",
    )
    def get_global_variable(self, name: str) -> str:
        key = str(name).strip().upper()
        if key not in self.ALLOWED_GLOBAL_VARS:
            return f"ERROR: Unknown global variable '{key}'. Allowed: {self.ALLOWED_GLOBAL_VARS}"
        return str(GLOBAL_SETTINGS.get(key, CONFIG_DEFAULTS.get(key)))

    @command(
        dtype_out=str,
        doc_out="All global settings as 'key=value' lines",
    )
    def list_global_variables(self) -> str:
        lines = []
        for k in self.ALLOWED_GLOBAL_VARS:
            v = GLOBAL_SETTINGS.get(k, CONFIG_DEFAULTS.get(k))
            lines.append(f"{k}={v}")
        return "\n".join(lines)

    @command(
        dtype_out=str,
        doc_out="Path to the global settings JSON file",
    )
    def get_global_config_path(self) -> str:
        return os.environ.get(CONFIG_FILE_ENV, _default_config_path())

    reload_global_variables = (command(
        dtype_out=str,
        doc_out="Reload result and current settings",
    ))(_general_methods_int_time["reload_global_variables"])

    save_global_variables = (command(
        dtype_out=str,
        doc_out="Save result and path",
    ))(_general_methods_int_time["save_global_variables"])
    del _general_methods_int_time
