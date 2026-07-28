import ast
import json
import os
import time
import zlib
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from threading import Event, RLock, Thread, current_thread
from typing import Any, Dict, Union

import msgpack
import numpy as np
from tango import AttrWriteType, DevState, DispLevel
from tango.server import Device, attribute, command, device_property, pipe

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

    def write_always_on_value(self, value: int):
        self.always_on = value

    @attribute(
        label="Friendly name",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
    )
    def device_friendly_name(self):
        return self.friendly_name

    def write_device_friendly_name(self, friendly_name):
        self.friendly_name = friendly_name

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
        label="URI",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="The URI of device.",
    )
    def uri(self):
        return self._uri

    def error(self, error_in):
        self.error_stream(error_in)
        self._error = error_in
        self._n = 0
        print(error_in)

    def warn(self, warn_in, printing=False):
        # Log a warning and optionally print
        try:
            self.warn_stream(warn_in)
        except Exception:
            # Fallback if warn_stream is unavailable
            self.info_stream(f"WARNING: {warn_in}")
        self._comment = warn_in
        if printing:
            print(warn_in)

    def info(self, info_in, printing=False):
        self.info_stream(info_in)
        self._comment = info_in
        if printing:
            print(info_in)


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
        self._stop_error_timer()
        self._lifecycle_lock = RLock()
        self._fault_recovery_attempts = 0
        self._next_fault_recovery_at = 0.0
        self._last_fault_recovery_error = ""
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
            self.find_device()

            if self._device_id_internal != -1:
                self.info(f"{self.device_name} was found.", True)
            else:
                self.info(f"{self.device_name} was NOT found.", True)
                self.set_state(DevState.FAULT)
        except BaseException:
            self._stop_error_timer()
            raise

    def _start_error_timer(self):
        """Start one bounded maintenance timer per device instance."""
        self._stop_error_timer()
        self._error_timer_stop = Event()
        self._error_timer_thread = Thread(
            target=self.int_time,
            args=(self._error_timer_stop,),
            name=f"{self.__class__.__name__}-error-timer",
            daemon=True,
        )
        self._error_timer_thread.start()

    def _stop_error_timer(self):
        stop_event = getattr(self, "_error_timer_stop", None)
        timer_thread = getattr(self, "_error_timer_thread", None)
        if stop_event is not None:
            stop_event.set()
        if (
            timer_thread is not None
            and timer_thread.is_alive()
            and timer_thread is not current_thread()
        ):
            timer_thread.join(timeout=1.0)
        self._error_timer_stop = None
        self._error_timer_thread = None

    def delete_device(self):
        """Release local maintenance resources when Tango removes this device."""
        self._stop_error_timer()
        parent_delete = getattr(super(), "delete_device", None)
        if parent_delete is not None:
            parent_delete()

    @abstractmethod
    def register_variables_for_archive(self):
        self.archive_state["State"] = (self.get_state, "int8")

    def send_state_archive(self):
        res = {}
        for key, prev_value in self.previous_archive_state.items():
            current_value = self.archive_state[key][0]()
            dt = self.archive_state[key][1]
            res[key] = current_value
            if prev_value != current_value:
                data = self.form_archive_data(current_value, key, dt)
                self.write_to_archive(data)
        self.previous_archive_state = res

    def fix_state(self):
        res = {}
        for key, value in self.archive_state.items():
            res[key] = value[0]()
        self.previous_archive_state = res
        self.info("Fixing archiving state", True)

    @abstractmethod
    def find_device(self):
        """Sets device_id_internal and uri if applicable"""

    def check_func_allowance(self, func) -> int:
        state_ok = -1
        if func.__name__ in self.RULES:
            rules_for_func = self.RULES[func.__name__]
            state = self.get_state()
            if state in rules_for_func:
                state_ok = 1
        else:
            self.error(f"Function {func} is not in RULES: {self.RULES}.")
        return state_ok

    def _get_lifecycle_lock(self):
        """Return a per-device reentrant lock for state-changing operations."""
        lock = getattr(self, "_lifecycle_lock", None)
        if lock is None:
            lock = RLock()
            self._lifecycle_lock = lock
        return lock

    def _fault_recovery_due(self, state) -> bool:
        if state != DevState.FAULT:
            return True
        if not bool(int(getattr(self, "fault_recovery_enabled", 1) or 0)):
            return False
        now = time.monotonic()
        if now < getattr(self, "_next_fault_recovery_at", 0.0):
            return False
        cooldown = max(0.1, float(getattr(self, "fault_recovery_cooldown_s", 3.0)))
        self._next_fault_recovery_at = now + cooldown
        self._fault_recovery_attempts = getattr(self, "_fault_recovery_attempts", 0) + 1
        return True

    def _record_controller_status(self, result) -> None:
        if operation_succeeded(result):
            # Older adapters sometimes reported success but left their previous
            # FAULT untouched. A successful health check is authoritative.
            if self.get_state() == DevState.FAULT:
                self.set_state(DevState.ON)
            self._fault_recovery_attempts = 0
            self._next_fault_recovery_at = 0.0
            self._last_fault_recovery_error = ""
            return
        self._last_fault_recovery_error = str(result)
        self.error(str(result))

    @attribute(label="Fault recovery status", dtype=str, access=AttrWriteType.READ)
    def fault_recovery_status(self) -> str:
        return (
            f"attempts={getattr(self, '_fault_recovery_attempts', 0)}; "
            f"last_error={getattr(self, '_last_fault_recovery_error', '')}"
        )

    def int_time(self, stop_event=None):
        """Clear transient errors until device teardown requests cancellation."""
        stop_event = stop_event or Event()
        while not stop_event.wait(0.5):
            self._n += 1
            if self._n > 10:
                self._error = ""
                self._n = 0

    def _init_archive_connection(self, timeout_seconds=5):
        """Initialize archive connection with timeout and graceful fallback"""
        import queue
        import threading

        # Lazy import taurus only when archive is enabled to avoid heavy startup cost
        try:
            import taurus  # noqa: F401
        except Exception as e:
            self.info(f"Taurus not available ({e}); using mock archive", True)
            self._create_mock_archive()
            return

        self.info(
            f"Attempting archive connection to {self.archive} (timeout: {timeout_seconds}s)",
            True,
        )

        def connect_to_archive(result_queue):
            """Thread function to connect to archive"""
            try:
                import taurus as _taurus

                archive_device = _taurus.Device(self.archive)
                result_queue.put(("success", archive_device))
            except Exception as e:
                result_queue.put(("error", str(e)))

        # Create queue and thread for timeout handling
        result_queue = queue.Queue()
        connect_thread = threading.Thread(
            target=connect_to_archive, args=(result_queue,)
        )
        connect_thread.daemon = True
        connect_thread.start()

        # Wait for result with timeout
        try:
            status, result = result_queue.get(timeout=timeout_seconds)
            if status == "success":
                self.archive = result
                self.info(f"Archive connection successful: {self.archive}", True)
            else:
                self._create_mock_archive()
                self.info(
                    f"Archive connection failed: {result}, using mock archive", True
                )
        except queue.Empty:
            # Timeout occurred
            self._create_mock_archive()
            self.info(
                f"Archive connection timed out after {timeout_seconds}s, using mock archive",
                True,
            )

    def _create_mock_archive(self):
        """Create a mock archive object that doesn't cause errors"""

        class MockArchive:
            def __init__(self):
                self.state = 0  # Disabled state

            def archive_it(self, data):
                # Do nothing - archive is disabled
                pass

        self.archive = MockArchive()

    @property
    def device_name(self) -> str:
        friendly_name = getattr(self, "friendly_name", None)
        if not friendly_name:
            return f"Device Unknown {self.__class__.__name__}"
        device_id = getattr(self, "device_id", None)
        if device_id:
            return f"Device {device_id} {friendly_name}"
        return f"Device {friendly_name}"

    @command(polling_period=polling_main)
    def get_controller_status(self):
        with self._get_lifecycle_lock():
            state = self.get_state()
            state_ok = self.check_func_allowance(self.get_controller_status)
            if state_ok != 1 or not self._fault_recovery_due(state):
                return

            result = self.get_controller_status_local()
            self._record_controller_status(result)
            self.send_state_archive()

    @abstractmethod
    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    @command
    def turn_on(self):
        with self._get_lifecycle_lock():
            if self.get_state() == DevState.ON:
                self.info(f"{self.device_name} is already ON.", True)
                return
            state_ok = self.check_func_allowance(self.turn_on)
            if state_ok == 1:
                self.info(f"Turning ON {self.device_name}.", True)
                result = self.turn_on_local()
                if not operation_succeeded(result):
                    self._last_fault_recovery_error = str(result)
                    self.error(f"{result}")
                else:
                    self._fault_recovery_attempts = 0
                    self._next_fault_recovery_at = 0.0
                    self._last_fault_recovery_error = ""
                    self.info(f"{self.device_name} WAS turned ON.", True)
                    self.fix_state()
            else:
                self.error(
                    f"Turning ON {self.device_name}, did not work, check state of the device {self.get_state()}."
                )

    @abstractmethod
    def turn_on_local(self) -> Union[int, str]:
        pass

    @command
    def turn_off(self):
        with self._get_lifecycle_lock():
            if self.get_state() == DevState.OFF:
                self.info(f"{self.device_name} is already OFF.", True)
                return
            state_ok = self.check_func_allowance(self.turn_off)
            if state_ok == 1:
                self.info(f"Turning off device {self.device_name}.", True)
                result = self.turn_off_local()
                if not operation_succeeded(result):
                    self.error(f"{result}")
                else:
                    self.info(f"{self.device_name} is turned OFF.", True)
                    data = self.form_archive_data(0, "State")
                    self.write_to_archive(data)
            else:
                self.error(
                    f"Turning OFF {self.device_name}, did not work, check state of the device {self.get_state()}."
                )

    @command(dtype_out=str)
    def recover(self):
        """Run one immediate non-power-cycling health recovery attempt."""
        with self._get_lifecycle_lock():
            self._next_fault_recovery_at = 0.0
            result = self.get_controller_status_local()
            self._record_controller_status(result)
            self.send_state_archive()
            if operation_succeeded(result):
                return "Recovered"
            return f"Recovery failed: {result}"

    @abstractmethod
    def turn_off_local(self) -> Union[int, str]:
        pass

    def write_to_archive(self, data: ArchiveData):
        archive = getattr(self, "archive", None)
        if archive is not None and getattr(archive, "state", 0) == 1:
            data_c = self.compress_data(data)
            archive.archive_it(data_c)

    def compress_data(self, data):
        msg_b = msgpack.packb(str(data))
        msg_b_c = zlib.compress(msg_b)
        msg_b_c_s = str(msg_b_c)
        return msg_b_c_s

    def form_archive_data(self, data, name: str, time_stamp=None, dt=None):
        if isinstance(data, float):
            if not dt:
                dt = "float32"
            data_s = Scalar(value=data, dtype=dt)
        elif isinstance(data, int):
            if not dt:
                if data <= 127 and data >= 0:
                    dt = "uint8"
                elif data >= 0:
                    dt = "uintc"
                else:
                    dt = "int"
            data_s = Scalar(value=data, dtype=dt)
        elif isinstance(data, np.ndarray):
            if not dt:
                dt = str(data.dtype)
                data.astype(dt)
            data_s = Array(value=data.tobytes(), shape=data.shape, dtype=dt)

        if time_stamp is None:
            time_stamp = time.time()

        archive_data = ArchiveData(
            tango_device=self.get_name(),
            data_timestamp=time_stamp,
            dataset_name=name,
            data=data_s,
        )
        return archive_data

    @command(
        dtype_in=[
            int,
        ],
        dtype_out=str,
        doc_in="Takes an order",
        doc_out="return name of order",
    )
    def register_order(self, value: int):
        import random
        import string

        s = 20  # number of characters in the string.
        name = "".join(random.choices(string.ascii_uppercase + string.digits, k=s))
        res = self.register_order_local(name, value)
        return name if res == 0 else "-1, could not register order"

    def register_order_local(self, name, value):
        pass

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

    def give_order_local(self, name) -> Any:
        pass

    # ----- Centralized global settings management commands -----
    @command(
        dtype_in=[str],
        dtype_out=str,
        doc_in="['name','value'] (global setting to change)",
        doc_out="Result message",
    )
    def set_global_variable(self, name_value: list) -> str:
        try:
            name, value = name_value[0], name_value[1]
        except Exception:
            return "ERROR: Provide ['name','value'] as a two-element string array"
        key = str(name).strip().upper()
        if key not in self.ALLOWED_GLOBAL_VARS:
            return f"ERROR: Unknown global variable '{key}'. Allowed: {self.ALLOWED_GLOBAL_VARS}"
        # Coerce value
        if key in ("DISABLE_ARCHIVE",):
            coerced = _str_to_bool(value)
        elif key in ("ARCHIVE_TIMEOUT_SECONDS",):
            try:
                coerced = int(value)
            except Exception:
                return f"ERROR: '{key}' expects integer value"
        else:
            coerced = str(value)
        GLOBAL_SETTINGS[key] = coerced
        # Apply immediately for archive-related changes
        if key == "DISABLE_ARCHIVE":
            if coerced:
                # Switch to mock archive now
                self._create_mock_archive()
                self.info("Global DISABLE_ARCHIVE set: switched to mock archive", True)
            else:
                # Try reconnect with configured timeout
                timeout_val = int(GLOBAL_SETTINGS.get("ARCHIVE_TIMEOUT_SECONDS", 5))
                self._init_archive_connection(timeout_seconds=timeout_val)
                self.info(
                    "Global DISABLE_ARCHIVE unset: attempted archive reconnect", True
                )
        return f"OK: {key} set to {GLOBAL_SETTINGS[key]}"

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

    @command(
        dtype_out=str,
        doc_out="Reload result and current settings",
    )
    def reload_global_variables(self) -> str:
        path = _load_global_settings_from_file()
        # Overlay env again in case it is set
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
            pass
        return "Reloaded from: " + path + "\n" + self.list_global_variables()

    @command(
        dtype_out=str,
        doc_out="Save result and path",
    )
    def save_global_variables(self) -> str:
        path = os.environ.get(CONFIG_FILE_ENV, _default_config_path())
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        try:
            to_save = {
                k: GLOBAL_SETTINGS.get(k, CONFIG_DEFAULTS.get(k))
                for k in CONFIG_DEFAULTS
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2)
            return f"Saved to: {path}"
        except Exception as e:
            return f"ERROR: Could not save to {path}: {e}"
