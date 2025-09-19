import json
import os
import time
import zlib
from abc import abstractmethod
from pathlib import Path
from threading import Thread
from time import sleep
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
    "ARCHIVE_TIMEOUT_SECONDS": 5,  # Default archive connection timeout,
    "DEBUG_INIT_TIMING": False,  # Print init timing breakdown,
    "DEBUG_TIMING_THRESHOLD_MS": 10,  # Only show steps >= this threshold
    "DEBUG_FUNCTION_TIMING": False,  # Time essential DS functions
    "DEBUG_FUNCTION_MIN_MS": 25,  # Only show function timings >= this threshold
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
    if "DEBUG_INIT_TIMING" in os.environ:
        GLOBAL_SETTINGS["DEBUG_INIT_TIMING"] = _str_to_bool(
            os.environ.get("DEBUG_INIT_TIMING", "")
        )
    if "DEBUG_TIMING_THRESHOLD_MS" in os.environ:
        GLOBAL_SETTINGS["DEBUG_TIMING_THRESHOLD_MS"] = int(
            os.environ.get("DEBUG_TIMING_THRESHOLD_MS", "10")
        )
    if "DEBUG_FUNCTION_TIMING" in os.environ:
        GLOBAL_SETTINGS["DEBUG_FUNCTION_TIMING"] = _str_to_bool(
            os.environ.get("DEBUG_FUNCTION_TIMING", "")
        )
    if "DEBUG_FUNCTION_MIN_MS" in os.environ:
        GLOBAL_SETTINGS["DEBUG_FUNCTION_MIN_MS"] = int(
            os.environ.get("DEBUG_FUNCTION_MIN_MS", "25")
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
from dataclasses import dataclass


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
    debug_init_timing = device_property(dtype=int, default_value=0)
    debug_function_timing = device_property(dtype=int, default_value=0)
    archive_enabled = device_property(dtype=int, default_value=0)
    archive = "manip/general/archive"
    polling_main = 300

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

    def info(self, info_in, printing=False):
        self.info_stream(info_in)
        self._comment = info_in
        if printing:
            print(info_in)

    # ----- Debug helpers for function timing -----
    def _debug_functions_on(self) -> bool:
        try:
            return (
                bool(GLOBAL_SETTINGS.get("DEBUG_FUNCTION_TIMING", False))
                or getattr(self, "debug_function_timing", 0) == 1
            )
        except Exception:
            return False

    def _debug_functions_threshold_ms(self) -> int:
        try:
            return int(GLOBAL_SETTINGS.get("DEBUG_FUNCTION_MIN_MS", 25))
        except Exception:
            return 25

    def _time_call(self, label: str, func, *args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        if self._debug_functions_on():
            dt_ms = (time.time() - t0) * 1000.0
            if dt_ms >= self._debug_functions_threshold_ms():
                # Use ASCII-only output to avoid Windows console encoding issues
                self.info(f"{label}: {dt_ms:.1f} ms", True)
        return result

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
        # Debug timing setup
        debug_on = (
            bool(GLOBAL_SETTINGS.get("DEBUG_INIT_TIMING", False))
            or getattr(self, "debug_init_timing", 0) == 1
        )
        self._init_marks = []
        self._init_t0 = time.time()

        def _mark(label: str):
            if debug_on:
                self._init_marks.append((label, time.time() - self._init_t0))

        def _print_init_timing():
            if not debug_on or not getattr(self, "_init_marks", None):
                return
            threshold = int(GLOBAL_SETTINGS.get("DEBUG_TIMING_THRESHOLD_MS", 10))
            self.info("=== INIT TIMING (ms) ===", True)
            prev = 0.0
            for label, t in self._init_marks:
                dt = (t - prev) * 1000.0
                if dt >= threshold:
                    self.info(f"{label}: {dt:.1f} ms (t={t * 1000.0:.1f})", True)
                prev = t
            total = (self._init_marks[-1][1]) * 1000.0
            self.info(f"Total init: {total:.1f} ms", True)

        _mark("start")
        self.orders: Dict[str, GeneralOrderInfo] = {}
        self.previous_archive_state: Dict[str, Any] = {}
        self.archive_state: Dict[str, Any] = {}
        self.locking_client_token = ""
        self.locked_client = False
        self._comment = "..."
        self._error = "..."
        self._n = 0
        internal_time = Thread(target=self.int_time)
        internal_time.daemon = True
        internal_time.start()
        _mark("internal_time_started")
        self._status_check_fault = 0
        self.prev_state = DevState.FAULT
        Device.init_device(self)
        _mark("tango_Device.init_device")
        if hasattr(self, "parameters"):
            self.parameters = eval(str(self.parameters))
        _mark("parameters_parsed")

        # Initialize archive connection with optional global disable flag
        global_disable = bool(GLOBAL_SETTINGS.get("DISABLE_ARCHIVE", False))
        if getattr(self, "archive_enabled", 1) == 0 or global_disable:
            self.info(
                "Archive disabled: Using mock archive (no connection attempt)", True
            )
            self._create_mock_archive()
        else:
            # Initialize archive connection with timeout handling
            timeout_val = int(GLOBAL_SETTINGS.get("ARCHIVE_TIMEOUT_SECONDS", 5))
            self._init_archive_connection(timeout_seconds=timeout_val)
        _mark("archive_init")

        self.set_state(DevState.OFF)
        self._device_id_internal = -1
        self._uri = b""
        self.find_device()
        _mark("find_device")

        if self._device_id_internal != -1:
            self.info(f"{self.device_name} was found.", True)
        else:
            self.info(f"{self.device_name} was NOT found.", True)
            self.set_state(DevState.FAULT)
        _mark("post_find_device")
        _print_init_timing()

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

    def int_time(self):
        try:
            while 1:
                sleep(0.5)
                self._n += 1
                if self._n > 10:
                    self._error = ""
                    self._n = 0
        except KeyboardInterrupt:
            return

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
        return f"Device {self.device_id} {self.friendly_name}"

    @command(polling_period=polling_main)
    def get_controller_status(self):
        state_ok = self.check_func_allowance(self.get_controller_status)
        if state_ok == 1:
            res = self._time_call(
                "get_controller_status_local", self.get_controller_status_local
            )
            self._time_call("send_state_archive", self.send_state_archive)
            if res != 0:
                self.error(f"{res}")
            if self.get_state() != DevState.ON and self.always_on == 1:
                self._time_call("turn_on", self.turn_on)

    @abstractmethod
    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    @command
    def turn_on(self):
        state_ok = self.check_func_allowance(self.turn_on)
        if state_ok == 1:
            self.info(f"Turning ON {self.device_name}.", True)
            res = self._time_call("turn_on_local", self.turn_on_local)
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Device {self.device_name} WAS turned ON.", True)
                self._time_call("fix_state", self.fix_state)
        else:
            self.error(
                f"Turning ON {self.device_name}, did not work, check state of the device {self.get_state()}."
            )

    @abstractmethod
    def turn_on_local(self) -> Union[int, str]:
        pass

    @command
    def turn_off(self):
        state_ok = self.check_func_allowance(self.turn_off)
        if state_ok == 1:
            self.info(f"Turning off device {self.device_name}.", True)
            res = self._time_call("turn_off_local", self.turn_off_local)
            if res != 0:
                self.error(f"{res}")
            else:
                self.info(f"Device {self.device_name} is turned OFF.", True)
                data = self.form_archive_data(0, "State")
                self._time_call(
                    "write_to_archive(State=0)", self.write_to_archive, data
                )
        else:
            self.error(
                f"Turning OFF {self.device_name}, did not work, check state of the device {self.get_state()}."
            )

    @abstractmethod
    def turn_off_local(self) -> Union[int, str]:
        pass

    def write_to_archive(self, data: ArchiveData):
        if self.archive.state == 1:
            if (
                bool(GLOBAL_SETTINGS.get("DEBUG_FUNCTION_TIMING", False))
                or getattr(self, "debug_function_timing", 0) == 1
            ):
                t0 = time.time()
                data_c = self.compress_data(data)
                t1 = time.time()
                self.archive.archive_it(data_c)
                t2 = time.time()
                comp_ms = (t1 - t0) * 1000.0
                arch_ms = (t2 - t1) * 1000.0
                total_ms = (t2 - t0) * 1000.0
                thr = int(GLOBAL_SETTINGS.get("DEBUG_FUNCTION_MIN_MS", 25))
                if comp_ms >= thr:
                    self.info(f"compress_data: {comp_ms:.1f} ms", True)
                if arch_ms >= thr:
                    self.info(f"archive_it: {arch_ms:.1f} ms", True)
                if total_ms >= thr:
                    self.info(f"write_to_archive: {total_ms:.1f} ms", True)
            else:
                data_c = self.compress_data(data)
                self.archive.archive_it(data_c)

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

        if not time_stamp:
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
        order = self.orders[name]
        res = -1
        if name in self.orders:
            order.order_done = True
            res = 0
        return res

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
