"""Implementation for _parse_tango_dict and related operations."""


def _bind_pump_probe_v0_api_parts_parse_tango_dict(api):
    """Bind implementation to the owning module and its runtime state."""

    def _parse_tango_dict(value):
        import ast

        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = ast.literal_eval(str(value))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    _parse_tango_dict.__module__ = api.__name__
    _parse_tango_dict.__qualname__ = "_parse_tango_dict"

    def _tango_proxy(device_name, timeout_ms=3000):
        import tango

        proxy = tango.DeviceProxy(str(device_name))
        proxy.set_timeout_millis(int(timeout_ms))
        return proxy

    _tango_proxy.__module__ = api.__name__
    _tango_proxy.__qualname__ = "_tango_proxy"

    def _numeric_list(value):
        try:
            return [float(part.strip()) for part in str(value).split(",")]
        except ValueError:
            return None

    _numeric_list.__module__ = api.__name__
    _numeric_list.__qualname__ = "_numeric_list"

    def _values_match(expected, actual, tolerance=1e-9):
        expected_numbers = api._numeric_list(expected)
        actual_numbers = api._numeric_list(actual)
        if expected_numbers is not None and actual_numbers is not None:
            if len(expected_numbers) != len(actual_numbers):
                return False
            return all(abs(left - right) <= tolerance for left, right in zip(expected_numbers, actual_numbers))
        return str(expected).strip() == str(actual).strip()

    _values_match.__module__ = api.__name__
    _values_match.__qualname__ = "_values_match"

    def _axis_is_ready(state, position):
        """Tango get_status_axis returns numeric DevState, not an error string."""
        if not api.math.isfinite(position):
            return False
        text = str(state).strip().upper()
        if "DEVSTATE." in text:
            text = text.rsplit(".", 1)[-1]
        # DevState.ON=0, MOVING=6, RUNNING=10. In particular OFF=1 and FAULT=8
        # must not pass merely because their string lacks the word 'FAULT'.
        return text in {"0", "6", "10", "ON", "MOVING", "RUNNING"}

    _axis_is_ready.__module__ = api.__name__
    _axis_is_ready.__qualname__ = "_axis_is_ready"

    def _load_dg645_recall_config(config_path):
        path = api.Path(str(config_path or api.DEFAULT_DG645_RECALL_CONFIG)).expanduser()
        with open(path, "r", encoding="utf-8") as handle:
            return api.json.load(handle)

    _load_dg645_recall_config.__module__ = api.__name__
    _load_dg645_recall_config.__qualname__ = "_load_dg645_recall_config"

    def _server_name_for_device(device_name):
        import tango

        db = tango.Database()
        info = db.get_device_info(str(device_name))
        server_name = getattr(info, "ds_full_name", None) or getattr(info, "server", None)
        if not server_name:
            raise RuntimeError(f"Could not resolve server for {device_name}")
        return str(server_name)

    _server_name_for_device.__module__ = api.__name__
    _server_name_for_device.__qualname__ = "_server_name_for_device"

    def _starter_devices():
        import tango

        db = tango.Database()
        return [str(name) for name in db.get_device_exported("*") if str(name).startswith("tango/admin/")]

    _starter_devices.__module__ = api.__name__
    _starter_devices.__qualname__ = "_starter_devices"

    def _starter_for_server(server_name, preferred_starter=None):
        if preferred_starter:
            starter = api._tango_proxy(preferred_starter, timeout_ms=5000)
            running = set(starter.command_inout("DevGetRunningServers", False))
            stopped = set(starter.command_inout("DevGetStopServers", False))
            return preferred_starter, starter, running, stopped

        for starter_name in api._starter_devices():
            try:
                starter = api._tango_proxy(starter_name, timeout_ms=5000)
                running = set(starter.command_inout("DevGetRunningServers", False))
                stopped = set(starter.command_inout("DevGetStopServers", False))
                if server_name in running or server_name in stopped:
                    return starter_name, starter, running, stopped
            except Exception:
                continue
        raise RuntimeError(f"No Starter manages server {server_name}")

    _starter_for_server.__module__ = api.__name__
    _starter_for_server.__qualname__ = "_starter_for_server"

    def _restart_server_for_device(device_name, preferred_starter=None):
        server_name = api._server_name_for_device(device_name)
        if server_name.lower().startswith("ds_standa_motor/"):
            raise RuntimeError("V0 preparation never starts or restarts STANDA servers; check Elysium2")
        starter_name, starter, running, _stopped = api._starter_for_server(
            server_name,
            preferred_starter=preferred_starter,
        )

        def wait_exported():
            deadline = api.time.monotonic() + 25.0
            last_error = None
            while api.time.monotonic() < deadline:
                try:
                    proxy = api._tango_proxy(device_name, timeout_ms=3000)
                    proxy.state()
                    return proxy
                except Exception as exc:
                    last_error = exc
                    api.time.sleep(0.5)
            raise RuntimeError(f"{device_name} did not become available: {last_error}")

        api.start_managed_server(starter, server_name, wait_exported, restart_existing=False)
        return {"server": server_name, "starter": starter_name}

    _restart_server_for_device.__module__ = api.__name__
    _restart_server_for_device.__qualname__ = "_restart_server_for_device"

    def _linspace(start, stop, count):
        if count <= 1:
            return [float(start)]
        step = (stop - start) / (count - 1)
        return [float(start + index * step) for index in range(count)]

    _linspace.__module__ = api.__name__
    _linspace.__qualname__ = "_linspace"

    def _normalize_data_path(path):
        raw_path = str(path or "").strip() or api._data_root()
        if api.is_smb_path(raw_path):
            return api.normalize_smb_path(raw_path)
        return api.os.path.abspath(api.os.path.expanduser(raw_path))

    _normalize_data_path.__module__ = api.__name__
    _normalize_data_path.__qualname__ = "_normalize_data_path"

    def _is_data_path_allowed(path):
        root = api._normalize_data_path(api._data_root())
        normalized = api._normalize_data_path(path)
        if api.is_smb_path(root) or api.is_smb_path(normalized):
            return api.is_smb_path(root) and api.is_smb_path(normalized) and api.smb_is_within(normalized, root)
        try:
            return api.os.path.commonpath([normalized, root]) == root
        except ValueError:
            return False

    _is_data_path_allowed.__module__ = api.__name__
    _is_data_path_allowed.__qualname__ = "_is_data_path_allowed"

    def _local_listdir(folder):
        entries = []
        with api.os.scandir(folder) as iterator:
            for entry in iterator:
                is_file = entry.is_file()
                entries.append({
                    "name": entry.name,
                    "path": entry.path,
                    "is_dir": entry.is_dir(),
                    "is_file": is_file,
                    "size_bytes": int(entry.stat().st_size) if is_file else 0,
                })
        return entries

    _local_listdir.__module__ = api.__name__
    _local_listdir.__qualname__ = "_local_listdir"

    def _list_data_path(path):
        normalized = api._normalize_data_path(path)
        if not api._is_data_path_allowed(normalized):
            raise ValueError("Data path is outside pump-probe data root")
        if api.is_smb_path(normalized):
            return api.smb_listdir(normalized)
        return api._local_listdir(normalized)

    _list_data_path.__module__ = api.__name__
    _list_data_path.__qualname__ = "_list_data_path"

    def _parent_data_path(path):
        root = api._normalize_data_path(api._data_root())
        normalized = api._normalize_data_path(path)
        if normalized == root:
            return root
        if api.is_smb_path(normalized):
            parent = api.smb_parent(normalized)
            return parent if api._is_data_path_allowed(parent) else root
        parent = api.os.path.dirname(normalized)
        return parent if api._is_data_path_allowed(parent) else root

    _parent_data_path.__module__ = api.__name__
    _parent_data_path.__qualname__ = "_parent_data_path"

    def _safe_folder_name(name):
        text = str(name or "").strip()
        cleaned = "".join(char if char.isalnum() or char in " ._-+()" else "_" for char in text)
        cleaned = cleaned.strip(" .")
        if not cleaned:
            raise ValueError("Folder name is empty")
        return cleaned[:120]

    _safe_folder_name.__module__ = api.__name__
    _safe_folder_name.__qualname__ = "_safe_folder_name"

    def _mkdir_data_path(parent, name):
        parent_path = api._normalize_data_path(parent)
        if not api._is_data_path_allowed(parent_path):
            raise ValueError("Parent path is outside pump-probe data root")
        folder_name = api._safe_folder_name(name)
        if api.is_smb_path(parent_path):
            import smbclient

            server, _share, _remote_path = api.split_smb_path(parent_path)
            from treatment_network_path import _register_session

            _register_session(server)
            next_path = api.smb_join(parent_path, folder_name)
            smbclient.makedirs(api.smb_to_unc(next_path), exist_ok=True)
            return next_path
        next_path = api.os.path.join(parent_path, folder_name)
        api.Path(next_path).mkdir(parents=True, exist_ok=True)
        return next_path

    _mkdir_data_path.__module__ = api.__name__
    _mkdir_data_path.__qualname__ = "_mkdir_data_path"

    def _read_data_file(path):
        normalized = api._normalize_data_path(path)
        if not api._is_data_path_allowed(normalized):
            raise ValueError("Data file is outside pump-probe data root")
        if api.is_smb_path(normalized):
            import smbclient

            server, _share, _remote_path = api.split_smb_path(normalized)
            from treatment_network_path import _register_session

            _register_session(server)
            with smbclient.open_file(api.smb_to_unc(normalized), mode="rb") as handle:
                return normalized, handle.read()
        with open(normalized, "rb") as handle:
            return normalized, handle.read()

    _read_data_file.__module__ = api.__name__
    _read_data_file.__qualname__ = "_read_data_file"

    def _publish_data_file(directory, source_path):
        """Copy a staged run artifact to the selected local or SMB data folder."""
        target_directory = api._normalize_data_path(directory)
        if not api._is_data_path_allowed(target_directory):
            raise ValueError("Run output path is outside pump-probe data root")

        source = api.Path(source_path)
        target_name = source.name
        if api.is_smb_path(target_directory):
            import smbclient

            server, _share, _remote_path = api.split_smb_path(target_directory)
            from treatment_network_path import _register_session

            _register_session(server)
            target = api.smb_join(target_directory, target_name)
            with open(source, "rb") as input_handle:
                with smbclient.open_file(api.smb_to_unc(target), mode="wb") as output_handle:
                    api.shutil.copyfileobj(input_handle, output_handle)
            return target

        api.Path(target_directory).mkdir(parents=True, exist_ok=True)
        target = api.Path(target_directory) / target_name
        api.shutil.copy2(source, target)
        return str(target)

    _publish_data_file.__module__ = api.__name__
    _publish_data_file.__qualname__ = "_publish_data_file"

    def _data_file_name(path):
        if api.is_smb_path(path):
            return api.unquote(path.rstrip("/").split("/")[-1])
        return api.Path(path).name

    _data_file_name.__module__ = api.__name__
    _data_file_name.__qualname__ = "_data_file_name"

    class PumpProbeV0Controller:
        def __init__(self):
            self._lock = api.threading.RLock()
            self._hardware_config = dict(api.DEFAULT_HARDWARE_CONFIG)
            self._sample_position_mm = 0.0
            self._sample_set_position_mm = 0.0
            self._sample_last_motion_update = api.time.monotonic()
            self._counter_last_value = None
            self._counter_last_time = None
            self._counter_rate_hz = 0.0
            self._andor_order = None
            self._andor_error = ""
            self._run_writer = None
            self._run_status = "idle"
            self._run_error = ""
            self._run_artifacts = {}
            self._run_output_dir = ""
            self._run_sample_name = ""
            self._run_thread = None
            self._scan_plan = None
            self._resume_source = None
            self._tango_run_plan = None
            self._tango_stop_event = None
            self._tango_done_event = api.threading.Event()
            self._tango_done_event.set()
            self._tango_stop_status = "stopped"
            self._tango_order_id = None
            self._tango_rejected_cycles = 0
            self._tango_cleanup_errors = []
            self._tango_camera_fingerprint = None
            self._tango_reset_requested = False
            self._run_raw_groups = tuple(api.RAW_GROUPS)
            self._settings = {
                "point_count": 100,
                "scan_start_ps": -25.0,
                "delay_step_ps": 1.0,
                "scan_span_ps": 99.0,
                "pulses_per_point": 10,
                "real_zero_ps": 465.0,
                "delay_points_ps": None,
            }
            self._wavelengths = api._linspace(253.2375, 826.3287, api.PIXELS)
            self._rng = api.random.Random()
            self._reset_locked()

        _pump_probe_v0_api_methods_control_mode_locked = api._bind_pump_probe_v0_api_methods_control_mode_locked(api._refactor_modules[api.__name__])
        _control_mode_locked = _pump_probe_v0_api_methods_control_mode_locked["_control_mode_locked"]

        _configure_hardware_locked = _pump_probe_v0_api_methods_control_mode_locked["_configure_hardware_locked"]

        _reset_locked = _pump_probe_v0_api_methods_control_mode_locked["_reset_locked"]

        _make_delays_locked = _pump_probe_v0_api_methods_control_mode_locked["_make_delays_locked"]

        _delay_to_mm = _pump_probe_v0_api_methods_control_mode_locked["_delay_to_mm"]

        _make_od_row_locked = _pump_probe_v0_api_methods_control_mode_locked["_make_od_row_locked"]

        _make_spectra_locked = _pump_probe_v0_api_methods_control_mode_locked["_make_spectra_locked"]

        _sync_locked = _pump_probe_v0_api_methods_control_mode_locked["_sync_locked"]

        _decode_andor_order_locked = _pump_probe_v0_api_methods_control_mode_locked["_decode_andor_order_locked"]

        _sync_andor_spectra_locked = _pump_probe_v0_api_methods_control_mode_locked["_sync_andor_spectra_locked"]

        _sync_sample_stage_locked = _pump_probe_v0_api_methods_control_mode_locked["_sync_sample_stage_locked"]

        _emulator_raw_cycle_locked = _pump_probe_v0_api_methods_control_mode_locked["_emulator_raw_cycle_locked"]

        _current_scan_plan_locked = _pump_probe_v0_api_methods_control_mode_locked["_current_scan_plan_locked"]

        _resume_available_locked = _pump_probe_v0_api_methods_control_mode_locked["_resume_available_locked"]

        _load_tango_profile_locked = _pump_probe_v0_api_methods_control_mode_locked["_load_tango_profile_locked"]

        prepare_tango_run = _pump_probe_v0_api_methods_control_mode_locked["prepare_tango_run"]

        _start_tango_run_locked = _pump_probe_v0_api_methods_control_mode_locked["_start_tango_run_locked"]

        _request_tango_stop_locked = _pump_probe_v0_api_methods_control_mode_locked["_request_tango_stop_locked"]

        wait_for_tango_cleanup = _pump_probe_v0_api_methods_control_mode_locked["wait_for_tango_cleanup"]

        _run_tango_loop = _pump_probe_v0_api_methods_control_mode_locked["_run_tango_loop"]
        del _pump_probe_v0_api_methods_control_mode_locked

        _pump_probe_v0_api_methods_start_emulator_run_locked = api._bind_pump_probe_v0_api_methods_start_emulator_run_locked(api._refactor_modules[api.__name__])
        _start_emulator_run_locked = _pump_probe_v0_api_methods_start_emulator_run_locked["_start_emulator_run_locked"]

        _run_emulator_loop = _pump_probe_v0_api_methods_start_emulator_run_locked["_run_emulator_loop"]

        _finalize_run_locked = _pump_probe_v0_api_methods_start_emulator_run_locked["_finalize_run_locked"]

        _apply_pulse_locked = _pump_probe_v0_api_methods_start_emulator_run_locked["_apply_pulse_locked"]

        configure = _pump_probe_v0_api_methods_start_emulator_run_locked["configure"]

        hardware_config = _pump_probe_v0_api_methods_start_emulator_run_locked["hardware_config"]

        set_running = _pump_probe_v0_api_methods_start_emulator_run_locked["set_running"]

        set_real_time = _pump_probe_v0_api_methods_start_emulator_run_locked["set_real_time"]

        set_faraday = _pump_probe_v0_api_methods_start_emulator_run_locked["set_faraday"]

        move_stage = _pump_probe_v0_api_methods_start_emulator_run_locked["move_stage"]

        stop_stage = _pump_probe_v0_api_methods_start_emulator_run_locked["stop_stage"]

        move_sample_stage = _pump_probe_v0_api_methods_start_emulator_run_locked["move_sample_stage"]

        stop_sample_stage = _pump_probe_v0_api_methods_start_emulator_run_locked["stop_sample_stage"]

        _owis_aggregator_locked = _pump_probe_v0_api_methods_start_emulator_run_locked["_owis_aggregator_locked"]

        _move_owis_axis_locked = _pump_probe_v0_api_methods_start_emulator_run_locked["_move_owis_axis_locked"]

        _stop_owis_axis_locked = _pump_probe_v0_api_methods_start_emulator_run_locked["_stop_owis_axis_locked"]

        _preflight_dg645_locked = _pump_probe_v0_api_methods_start_emulator_run_locked["_preflight_dg645_locked"]

        _check_device = _pump_probe_v0_api_methods_start_emulator_run_locked["_check_device"]

        _netio_outputs_for_device = _pump_probe_v0_api_methods_start_emulator_run_locked["_netio_outputs_for_device"]

        _check_netio_output = _pump_probe_v0_api_methods_start_emulator_run_locked["_check_netio_output"]
        del _pump_probe_v0_api_methods_start_emulator_run_locked

        _pump_probe_v0_api_methods_check_owis_axes = api._bind_pump_probe_v0_api_methods_check_owis_axes(api._refactor_modules[api.__name__])
        _check_owis_axes = _pump_probe_v0_api_methods_check_owis_axes["_check_owis_axes"]

        _check_camera_stream = _pump_probe_v0_api_methods_check_owis_axes["_check_camera_stream"]

        _check_laser_pointing = _pump_probe_v0_api_methods_check_owis_axes["_check_laser_pointing"]

        _read_daq_counter = _pump_probe_v0_api_methods_check_owis_axes["_read_daq_counter"]

        _counter_status_locked = _pump_probe_v0_api_methods_check_owis_axes["_counter_status_locked"]

        _check_counter_activity = _pump_probe_v0_api_methods_check_owis_axes["_check_counter_activity"]

        _check_dg645_recall = _pump_probe_v0_api_methods_check_owis_axes["_check_dg645_recall"]

        _starter_server_snapshot = _pump_probe_v0_api_methods_check_owis_axes["_starter_server_snapshot"]

        _everest_server_snapshot = _pump_probe_v0_api_methods_check_owis_axes["_everest_server_snapshot"]

        _v0_preparation_checks = _pump_probe_v0_api_methods_check_owis_axes["_v0_preparation_checks"]

        hardware_preflight = _pump_probe_v0_api_methods_check_owis_axes["hardware_preflight"]

        _read_tango_motion_state_locked = _pump_probe_v0_api_methods_check_owis_axes["_read_tango_motion_state_locked"]

        move_crystal = _pump_probe_v0_api_methods_check_owis_axes["move_crystal"]

        reset = _pump_probe_v0_api_methods_check_owis_axes["reset"]

        state = _pump_probe_v0_api_methods_check_owis_axes["state"]
        del _pump_probe_v0_api_methods_check_owis_axes

    PumpProbeV0Controller.__module__ = api.__name__
    PumpProbeV0Controller.__qualname__ = "PumpProbeV0Controller"

    def _v0_lifecycle():
        global _v0_lifecycle_instance
        with api._v0_lifecycle_factory_lock:
            if api._v0_lifecycle_instance is None:
                path = api.os.environ.get("PYCONLYSE_V0_EXPERIMENT_STATE_DB") or str(api.Path.home() / ".pyconlyse" / "experiment_preparation_v0.sqlite3")
                _v0_lifecycle_instance = api.ExperimentLifecycle(path, experiment="V0")
            return api._v0_lifecycle_instance

    _v0_lifecycle.__module__ = api.__name__
    _v0_lifecycle.__qualname__ = "_v0_lifecycle"

    class V0PreparationFailure(RuntimeError):
        code = "v0_preparation_incomplete"

        def __init__(self, result):
            self.checks = list(result.get("checks", []))
            self.steps = [{**check, "step": check["label"],
                           "status": "verified" if check.get("ok") else "failed"}
                          for check in self.checks]
            super().__init__(result.get("recommendation") or result.get("message") or "V0 preparation incomplete")

    V0PreparationFailure.__module__ = api.__name__
    V0PreparationFailure.__qualname__ = "V0PreparationFailure"

    def _prepare_v0_experiment(steps=None):
        # Do not initialise shared controls while a live experiment owns them.
        import pump_probe_vd2_api as vd2
        with api._emulator._lock:
            if api._emulator._running or api._emulator._real_time or vd2._measurement_protocol.status().get("status") in {"acquiring", "saving"}:
                raise RuntimeError("Acquisition is active; V0 preparation did not change hardware")
        result = api._emulator.hardware_preflight(fix=True, progress=steps)
        if not result["success"]:
            raise api.V0PreparationFailure(result)
        return {**result, "steps": list(steps) if steps is not None else [
            {**check, "step": check["label"], "status": "verified"} for check in result["checks"]]}

    _prepare_v0_experiment.__module__ = api.__name__
    _prepare_v0_experiment.__qualname__ = "_prepare_v0_experiment"

    def _serialized_v0_mutation(function):
        @api.wraps(function)
        def wrapped(*args, **kwargs):
            if not api.EXPERIMENT_MUTATION_LOCK.acquire(blocking=False):
                return api.jsonify({"success": False, "error": "Experiment preparation/shutdown is in progress; hardware commands are locked"}), 409
            try:
                return function(*args, **kwargs)
            finally:
                api.EXPERIMENT_MUTATION_LOCK.release()
        return wrapped

    _serialized_v0_mutation.__module__ = api.__name__
    _serialized_v0_mutation.__qualname__ = "_serialized_v0_mutation"

    def _v0_shutdown_vd2_status():
        import pump_probe_vd2_api as vd2
        streak = api._tango_proxy(vd2.STREAK_DEVICE, timeout_ms=2500)
        return {"application_running": bool(streak.read_attribute("application_running").value),
                "connected": bool(streak.read_attribute("connected").value),
                "protocol_active": vd2._measurement_protocol.status().get("status") in {"acquiring", "saving"},
                "lifecycle_active": vd2._lifecycle().snapshot().get("status") == "running"}

    _v0_shutdown_vd2_status.__module__ = api.__name__
    _v0_shutdown_vd2_status.__qualname__ = "_v0_shutdown_vd2_status"

    def _stop_v0_web_sequence():
        api._emulator.set_running(False)
        api._emulator.wait_for_tango_cleanup()
        api._emulator.set_real_time(False)

    _stop_v0_web_sequence.__module__ = api.__name__
    _stop_v0_web_sequence.__qualname__ = "_stop_v0_web_sequence"

    def _v0_shutdown_authorization():
        targets = [{"device": api.V0_SHUTDOWN_CAMERA, "command": command}
                   for command in ("BeginSafePowerOff", "GetPowerOffSafety", "ReleaseAfterWarmup")]
        targets.extend({"device": device, "command": "set_channels_states"}
                       for device in dict.fromkeys(item[0] for item in api.V0_SHUTDOWN_OUTPUT_PLAN))
        targets.extend({"device": api.V0_SHUTDOWN_STAGE, "command": command}
                       for command in ("move_axis", "stop_axis"))
        return targets, {"pdu_output_states": [{"device": device, "output_id": output, "state": 0}
                                               for device, output, _label in api.V0_SHUTDOWN_OUTPUT_PLAN],
                         "translation_stage_return": {"device": api.V0_SHUTDOWN_STAGE, "backend": api.V0_SHUTDOWN_STAGE_BACKEND,
                                                      "axis": api.V0_SHUTDOWN_STAGE_AXIS, "position_mm": 0.0,
                                                      "tolerance_mm": api.V0_SHUTDOWN_STAGE_TOLERANCE,
                                                      "timeout_s": api.V0_SHUTDOWN_STAGE_TIMEOUT,
                                                      "home_or_redefine": False},
                         "camera_warmup_minimum_c": 0, "camera_warmup_timeout_s": 900,
                         "preserve": "Elysium2/STANDA, shared OWIS power and other axes, all VD2 outlets, Xe cooling",
                         "block_if_vd2_active": True, "server_start_or_restart": False}

    _v0_shutdown_authorization.__module__ = api.__name__
    _v0_shutdown_authorization.__qualname__ = "_v0_shutdown_authorization"

    def _v0_hardware_config(payload=None):
        config = api._emulator.hardware_config()
        payload = payload or {}
        requested = payload.get("hardware_config") if isinstance(payload, dict) else None
        if isinstance(requested, dict):
            config = {**config, **{key: value for key, value in requested.items() if key in api.DEFAULT_HARDWARE_CONFIG}}
        if isinstance(payload, dict) and "control_mode" in payload:
            config["control_mode"] = payload["control_mode"]
        return config

    _v0_hardware_config.__module__ = api.__name__
    _v0_hardware_config.__qualname__ = "_v0_hardware_config"

    def _v0_reject_runtime_hardware_rewire(payload):
        """Production/local-auth policy owns physical V0 topology, not requests."""
        if not api.authorization_required() or not isinstance(payload, dict):
            return None
        raw_config = payload.get("hardware_config")
        if raw_config is None:
            return None
        if not isinstance(raw_config, dict) or set(raw_config) - {"control_mode"}:
            return api.jsonify({
                "success": False,
                "error": "Hardware configuration rewiring is not authorized",
                "code": "hardware_not_authorized",
            }), 403
        return None

    _v0_reject_runtime_hardware_rewire.__module__ = api.__name__
    _v0_reject_runtime_hardware_rewire.__qualname__ = "_v0_reject_runtime_hardware_rewire"

    def _v0_tango_active(payload=None):
        current = api._clean_control_mode(api._emulator.hardware_config().get("control_mode"))
        requested = api._clean_control_mode(api._v0_hardware_config(payload).get("control_mode"))
        return current == "tango" or requested == "tango"

    _v0_tango_active.__module__ = api.__name__
    _v0_tango_active.__qualname__ = "_v0_tango_active"

    def _v0_reject_unbound_tango_sequence():
        """Fail closed until V0 can bind its complete runtime plan to approval."""
        return api.jsonify({
            "success": False,
            "error": "A precomputed exact hardware plan is required",
            "code": "hardware_not_authorized",
        }), 403

    _v0_reject_unbound_tango_sequence.__module__ = api.__name__
    _v0_reject_unbound_tango_sequence.__qualname__ = "_v0_reject_unbound_tango_sequence"

    return {
        "_parse_tango_dict": _parse_tango_dict,
        "_tango_proxy": _tango_proxy,
        "_numeric_list": _numeric_list,
        "_values_match": _values_match,
        "_axis_is_ready": _axis_is_ready,
        "_load_dg645_recall_config": _load_dg645_recall_config,
        "_server_name_for_device": _server_name_for_device,
        "_starter_devices": _starter_devices,
        "_starter_for_server": _starter_for_server,
        "_restart_server_for_device": _restart_server_for_device,
        "_linspace": _linspace,
        "_normalize_data_path": _normalize_data_path,
        "_is_data_path_allowed": _is_data_path_allowed,
        "_local_listdir": _local_listdir,
        "_list_data_path": _list_data_path,
        "_parent_data_path": _parent_data_path,
        "_safe_folder_name": _safe_folder_name,
        "_mkdir_data_path": _mkdir_data_path,
        "_read_data_file": _read_data_file,
        "_publish_data_file": _publish_data_file,
        "_data_file_name": _data_file_name,
        "PumpProbeV0Controller": PumpProbeV0Controller,
        "_v0_lifecycle": _v0_lifecycle,
        "V0PreparationFailure": V0PreparationFailure,
        "_prepare_v0_experiment": _prepare_v0_experiment,
        "_serialized_v0_mutation": _serialized_v0_mutation,
        "_v0_shutdown_vd2_status": _v0_shutdown_vd2_status,
        "_stop_v0_web_sequence": _stop_v0_web_sequence,
        "_v0_shutdown_authorization": _v0_shutdown_authorization,
        "_v0_hardware_config": _v0_hardware_config,
        "_v0_reject_runtime_hardware_rewire": _v0_reject_runtime_hardware_rewire,
        "_v0_tango_active": _v0_tango_active,
        "_v0_reject_unbound_tango_sequence": _v0_reject_unbound_tango_sequence,
    }
