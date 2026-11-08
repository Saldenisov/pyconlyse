"""Implementation for int_time and related operations."""


def _bind_general_methods_int_time(api):
    """Bind implementation to the owning module and its runtime state."""

    def int_time(self, stop_event=None):
        """Clear transient errors until device teardown requests cancellation."""
        stop_event = stop_event or api.Event()
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

    def get_controller_status(self):
        with self._get_lifecycle_lock():
            if not self._power_dependency_allows_hardware_operation():
                return
            state = self.get_state()
            state_ok = self.check_func_allowance(self.get_controller_status)
            if state_ok != 1 or not self._fault_recovery_due(state):
                return

            result = self.get_controller_status_local()
            self._record_controller_status(result)
            self.send_state_archive()

    def turn_on(self):
        with self._get_lifecycle_lock():
            if not self._power_dependency_allows_hardware_operation(force=True):
                return
            if self.get_state() == api.DevState.ON:
                self.info(f"{self.device_name} is already ON.", True)
                return
            state_ok = self.check_func_allowance(self.turn_on)
            if state_ok == 1:
                self.info(f"Turning ON {self.device_name}.", True)
                result = self.turn_on_local()
                if not api.operation_succeeded(result):
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

    def turn_off(self):
        with self._get_lifecycle_lock():
            if self.get_state() == api.DevState.OFF:
                self.info(f"{self.device_name} is already OFF.", True)
                return
            state_ok = self.check_func_allowance(self.turn_off)
            if state_ok == 1:
                self.info(f"Turning off device {self.device_name}.", True)
                result = self.turn_off_local()
                if not api.operation_succeeded(result):
                    self.error(f"{result}")
                else:
                    self.info(f"{self.device_name} is turned OFF.", True)
                    data = self.form_archive_data(0, "State")
                    self.write_to_archive(data)
            else:
                self.error(
                    f"Turning OFF {self.device_name}, did not work, check state of the device {self.get_state()}."
                )

    def recover(self):
        """Run one immediate non-power-cycling health recovery attempt."""
        with self._get_lifecycle_lock():
            if not self._power_dependency_allows_hardware_operation(force=True):
                return "Recovery skipped: hardware power is not available"
            self._next_fault_recovery_at = 0.0
            result = self.get_controller_status_local()
            self._record_controller_status(result)
            self.send_state_archive()
            if api.operation_succeeded(result):
                return "Recovered"
            return f"Recovery failed: {result}"

    def write_to_archive(self, data: api.ArchiveData):
        archive = getattr(self, "archive", None)
        if archive is not None and getattr(archive, "state", 0) == 1:
            data_c = self.compress_data(data)
            archive.archive_it(data_c)

    def compress_data(self, data):
        msg_b = api.msgpack.packb(str(data))
        msg_b_c = api.zlib.compress(msg_b)
        msg_b_c_s = str(msg_b_c)
        return msg_b_c_s

    def form_archive_data(self, data, name: str, time_stamp=None, dt=None):
        if isinstance(data, float):
            if not dt:
                dt = "float32"
            data_s = api.Scalar(value=data, dtype=dt)
        elif isinstance(data, int):
            if not dt:
                if data <= 127 and data >= 0:
                    dt = "uint8"
                elif data >= 0:
                    dt = "uintc"
                else:
                    dt = "int"
            data_s = api.Scalar(value=data, dtype=dt)
        elif isinstance(data, api.np.ndarray):
            if not dt:
                dt = str(data.dtype)
                data.astype(dt)
            data_s = api.Array(value=data.tobytes(), shape=data.shape, dtype=dt)

        if time_stamp is None:
            time_stamp = api.time.time()

        archive_data = api.ArchiveData(
            tango_device=self.get_name(),
            data_timestamp=time_stamp,
            dataset_name=name,
            data=data_s,
        )
        return archive_data

    def register_order(self, value: int):
        import random
        import string

        s = 20  # number of characters in the string.
        name = "".join(random.choices(string.ascii_uppercase + string.digits, k=s))
        res = self.register_order_local(name, value)
        return name if res == 0 else "-1, could not register order"

    def register_order_local(self, name, value):
        pass

    def give_order_local(self, name) -> api.Any:
        pass

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
            coerced = api._str_to_bool(value)
        elif key in ("ARCHIVE_TIMEOUT_SECONDS",):
            try:
                coerced = int(value)
            except Exception:
                return f"ERROR: '{key}' expects integer value"
        else:
            coerced = str(value)
        api.GLOBAL_SETTINGS[key] = coerced
        # Apply immediately for archive-related changes
        if key == "DISABLE_ARCHIVE":
            if coerced:
                # Switch to mock archive now
                self._create_mock_archive()
                self.info("Global DISABLE_ARCHIVE set: switched to mock archive", True)
            else:
                # Try reconnect with configured timeout
                timeout_val = int(api.GLOBAL_SETTINGS.get("ARCHIVE_TIMEOUT_SECONDS", 5))
                self._init_archive_connection(timeout_seconds=timeout_val)
                self.info(
                    "Global DISABLE_ARCHIVE unset: attempted archive reconnect", True
                )
        return f"OK: {key} set to {api.GLOBAL_SETTINGS[key]}"

    def reload_global_variables(self) -> str:
        path = api._load_global_settings_from_file()
        # Overlay env again in case it is set
        try:
            if "DISABLE_ARCHIVE" in api.os.environ:
                api.GLOBAL_SETTINGS["DISABLE_ARCHIVE"] = api._str_to_bool(
                    api.os.environ.get("DISABLE_ARCHIVE", "")
                )
            if "ARCHIVE_TIMEOUT_SECONDS" in api.os.environ:
                api.GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] = int(
                    api.os.environ.get("ARCHIVE_TIMEOUT_SECONDS", "5")
                )
        except Exception:
            pass
        return "Reloaded from: " + path + "\n" + self.list_global_variables()

    def save_global_variables(self) -> str:
        path = api.os.environ.get(api.CONFIG_FILE_ENV, api._default_config_path())
        try:
            api.os.makedirs(api.os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        try:
            to_save = {
                k: api.GLOBAL_SETTINGS.get(k, api.CONFIG_DEFAULTS.get(k))
                for k in api.CONFIG_DEFAULTS
            }
            with open(path, "w", encoding="utf-8") as f:
                api.json.dump(to_save, f, indent=2)
            return f"Saved to: {path}"
        except Exception as e:
            return f"ERROR: Could not save to {path}: {e}"

    return {
        "int_time": int_time,
        "_init_archive_connection": _init_archive_connection,
        "_create_mock_archive": _create_mock_archive,
        "get_controller_status": get_controller_status,
        "turn_on": turn_on,
        "turn_off": turn_off,
        "recover": recover,
        "write_to_archive": write_to_archive,
        "compress_data": compress_data,
        "form_archive_data": form_archive_data,
        "register_order": register_order,
        "register_order_local": register_order_local,
        "give_order_local": give_order_local,
        "set_global_variable": set_global_variable,
        "reload_global_variables": reload_global_variables,
        "save_global_variables": save_global_variables,
    }
