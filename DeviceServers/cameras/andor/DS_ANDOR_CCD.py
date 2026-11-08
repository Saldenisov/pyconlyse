#!/usr/bin/python3 -u
from sys import modules as _refactor_modules

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from time import sleep, time, time_ns
from typing import Dict, Optional, Tuple, Union

import numpy as np
from tango import DevState
from tango.server import AttrWriteType, attribute, command, device_property

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from DeviceServers.cameras.andor.andor_ccd_methods_coerce_int import _bind_andor_ccd_methods_coerce_int
from DeviceServers.cameras.andor.andor_ccd_methods_v0_refresh_calibration import _bind_andor_ccd_methods_v0_refresh_calibration

from tango import DeviceProxy

from DeviceServers.andor.pylablib_backend import get_andor_module
from DeviceServers.base.camera import DS_CAMERA_CCD, OrderInfo
from DeviceServers.cameras.andor.poweroff_safety import begin_safe_poweroff, read_poweroff_safety
from DeviceServers.cameras.andor.v0_orders import V0Orders, canonical_json, sdk_configuration_mutation


@dataclass
class FrameOrderState(OrderInfo):
    frames_done: int = 0


class DS_ANDOR_CCD(DS_CAMERA_CCD):
    RULES = {**DS_CAMERA_CCD.RULES}

    _version_ = "0.2"
    _model_ = "ANDOR CCD (pylablib)"

    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000

    dll_path = device_property(dtype=str, default_value="")
    ini_path = device_property(dtype=str, default_value="")
    width = device_property(dtype=int, default_value=1064)
    wavelengths = device_property(dtype=str, default_value="[]")
    wavelengths_file = device_property(dtype=str, default_value="")
    camera_index = device_property(dtype=int, default_value=0)
    fan_mode = device_property(dtype=str, default_value="full")
    default_temperature = device_property(dtype=int, default_value=-50)
    linked_spectrograph_ds = device_property(dtype=str, default_value="")
    start_grabbing_on_init = device_property(dtype=int, default_value=0)

    TRIGGER_MODE_MAP = {
        0: "int",
        1: "ext",
        6: "ext_start",
        7: "ext_exp",
        9: "ext_fvb_em",
        10: "software",
    }
    TRIGGER_MODE_MAP_INV = {value: key for key, value in TRIGGER_MODE_MAP.items()}
    READ_MODE_MAP = {
        0: "fvb",
        1: "multi_track",
        2: "random_track",
        3: "single_track",
        4: "image",
    }
    READ_MODE_MAP_INV = {value: key for key, value in READ_MODE_MAP.items()}
    ACQ_MODE_MAP = {
        1: "single",
        2: "accum",
        3: "kinetic",
        4: "fast_kinetic",
        5: "cont",
    }
    ACQ_MODE_MAP_INV = {value: key for key, value in ACQ_MODE_MAP.items()}

    _andor_ccd_methods_coerce_int = _bind_andor_ccd_methods_coerce_int(_refactor_modules[__name__])
    _coerce_int = (staticmethod)(_andor_ccd_methods_coerce_int["_coerce_int"])

    _coerce_float = (staticmethod)(_andor_ccd_methods_coerce_int["_coerce_float"])

    _coerce_str = (staticmethod)(_andor_ccd_methods_coerce_int["_coerce_str"])

    def init_device(self):
        self._v0_orders = V0Orders()
        self._v0_wavelengths = np.array([], dtype=np.float64)
        self._v0_axis_source = "unavailable"
        default_width = self._coerce_int(self.width, 1064)
        default_temperature = self._coerce_float(self.default_temperature, -50.0)
        self.serial_number_real = -1
        self.head_name = ""
        self.status_real = 0
        self.exposure_time_local = 0.0
        self.accumulate_time_local = 0.0
        self.kinetic_time_local = 0.0
        self.n_gains_max = 0
        self.gain_value = 0
        self.height_value = 1
        self.current_width = default_width
        self.current_height = 1
        self.track_count_value = 1
        self.current_read_mode = "multi_track"
        self.current_acquisition_mode = "cont"
        self.temperature_value = default_temperature
        self.temperature_target_value = default_temperature
        self.temperature_status_value = "unknown"
        self.cooler_on_value = False
        self.vsspeed_value = 0
        self.ad_channel_value = 0
        self.oamp_value = 0
        self.hsspeed_value = 0
        self.binning_horizontal_value = 1
        self.binning_vertical_value = 1
        self.offsetX_value = 0
        self.offsetY_value = 0
        self.trigger_mode_value = 1
        self.trigger_source_value = 0
        self.trigger_type_value = 0
        self.grabbing_thread: Optional[Thread] = None
        self.abort = False
        self.n_kinetics = 1
        self.camera = None
        self._default_wavelengths = self._parse_wavelengths()
        self._v0_default_wavelengths = self._parse_wavelengths(dtype=np.float64)
        self.wavelengths_axis_value = np.array([], dtype=np.float32)

        super().init_device()
        self.register_variables_for_archive()
        self._refresh_wavelengths_axis(expected_width=self.current_width)

        if bool(self._coerce_int(self.start_grabbing_on_init, 0)):
            try:
                self.start_grabbing()
            except Exception as exc:
                self.warn(f"Auto-start grabbing failed: {exc}", True)

    @attribute(label="number of kinetics", dtype=int, access=AttrWriteType.READ_WRITE)
    def number_kinetics(self):
        return self.n_kinetics

    @sdk_configuration_mutation
    def write_number_kinetics(self, value: int):
        self.n_kinetics = max(1, int(value))
        if self.camera:
            self._apply_acquisition_mode_settings()

    @attribute(label="track count", dtype=int, access=AttrWriteType.READ)
    def track_count(self):
        return int(self.track_count_value)

    @attribute(
        label="wavelength axis",
        dtype=(float,),
        max_dim_x=4096,
        access=AttrWriteType.READ,
    )
    def wavelengths_axis(self):
        return np.asarray(self.wavelengths_axis_value, dtype=np.float32)

    @attribute(label="temperature current", dtype=float, access=AttrWriteType.READ)
    def temperature_current(self):
        self._update_temperature_status()
        return float(self.temperature_value)

    @attribute(label="temperature target", dtype=float, access=AttrWriteType.READ)
    def temperature_target(self):
        self._update_temperature_status()
        return float(self.temperature_target_value)

    @attribute(label="cooler on", dtype=bool, access=AttrWriteType.READ)
    def cooler_on(self):
        self._update_temperature_status()
        return bool(self.cooler_on_value)

    @attribute(label="temperature status", dtype=str, access=AttrWriteType.READ)
    def temperature_status(self):
        self._update_temperature_status()
        return str(self.temperature_status_value)

    @attribute(label="linked spectrograph ds", dtype=str, access=AttrWriteType.READ)
    def linked_spectrograph_device(self):
        return str(self.linked_spectrograph_ds or "")

    _parse_array_property = _andor_ccd_methods_coerce_int["_parse_array_property"]

    _parse_wavelengths = _andor_ccd_methods_coerce_int["_parse_wavelengths"]

    _create_camera = _andor_ccd_methods_coerce_int["_create_camera"]

    _with_temp_camera = _andor_ccd_methods_coerce_int["_with_temp_camera"]

    _sync_from_camera = _andor_ccd_methods_coerce_int["_sync_from_camera"]

    _update_image_geometry_from_mode = _andor_ccd_methods_coerce_int["_update_image_geometry_from_mode"]

    _update_temperature_status = _andor_ccd_methods_coerce_int["_update_temperature_status"]

    _update_amp_mode_state = _andor_ccd_methods_coerce_int["_update_amp_mode_state"]

    _refresh_wavelengths_axis = _andor_ccd_methods_coerce_int["_refresh_wavelengths_axis"]

    _normalize_frame = _andor_ccd_methods_coerce_int["_normalize_frame"]

    _consume_frame_for_orders = _andor_ccd_methods_coerce_int["_consume_frame_for_orders"]

    find_device = _andor_ccd_methods_coerce_int["find_device"]

    get_camera_friendly_name = _andor_ccd_methods_coerce_int["get_camera_friendly_name"]

    set_camera_friendly_name = _andor_ccd_methods_coerce_int["set_camera_friendly_name"]

    get_camera_serial_number = _andor_ccd_methods_coerce_int["get_camera_serial_number"]

    get_camera_model_name = _andor_ccd_methods_coerce_int["get_camera_model_name"]

    get_exposure_time = _andor_ccd_methods_coerce_int["get_exposure_time"]

    @sdk_configuration_mutation
    def set_exposure_time(self, value: float):
        self.exposure_time_local = float(value)
        if not self.camera:
            return

        restart = self.grabbing
        if restart:
            self.stop_grabbing_local()

        self.camera.set_exposure(float(value))
        self._apply_acquisition_mode_settings()

        if restart:
            self.start_grabbing_local()

    @sdk_configuration_mutation
    def set_trigger_delay(self, value: str):
        self.trigger_source_value = int(float(value))

    get_trigger_delay = _andor_ccd_methods_coerce_int["get_trigger_delay"]

    get_exposure_min = _andor_ccd_methods_coerce_int["get_exposure_min"]

    get_exposure_max = _andor_ccd_methods_coerce_int["get_exposure_max"]

    @sdk_configuration_mutation
    def set_gain(self, value: int):
        self.gain_value = int(value)
        if self.camera:
            self.camera.set_amp_mode(preamp=self.gain_value)

    get_gain = _andor_ccd_methods_coerce_int["get_gain"]

    get_gain_min = _andor_ccd_methods_coerce_int["get_gain_min"]

    get_gain_max = _andor_ccd_methods_coerce_int["get_gain_max"]

    get_width = _andor_ccd_methods_coerce_int["get_width"]

    @sdk_configuration_mutation
    def set_width(self, value: int):
        self.current_width = max(1, int(value))

    get_width_min = _andor_ccd_methods_coerce_int["get_width_min"]

    get_width_max = _andor_ccd_methods_coerce_int["get_width_max"]

    @sdk_configuration_mutation
    def set_height(self, value: int):
        self.current_height = max(1, int(value))

    get_height = _andor_ccd_methods_coerce_int["get_height"]

    get_height_min = _andor_ccd_methods_coerce_int["get_height_min"]

    get_height_max = _andor_ccd_methods_coerce_int["get_height_max"]

    get_offsetX = _andor_ccd_methods_coerce_int["get_offsetX"]

    @sdk_configuration_mutation
    def set_offsetX(self, value: int):
        self.offsetX_value = int(value)

    get_offsetY = _andor_ccd_methods_coerce_int["get_offsetY"]

    @sdk_configuration_mutation
    def set_offsetY(self, value: int):
        self.offsetY_value = int(value)

    set_format_pixel = _andor_ccd_methods_coerce_int["set_format_pixel"]

    get_format_pixel = _andor_ccd_methods_coerce_int["get_format_pixel"]

    get_framerate = _andor_ccd_methods_coerce_int["get_framerate"]

    @sdk_configuration_mutation
    def set_binning_horizontal(self, value: int):
        self.binning_horizontal_value = max(1, int(value))

    get_binning_horizontal = _andor_ccd_methods_coerce_int["get_binning_horizontal"]

    @sdk_configuration_mutation
    def set_binning_vertical(self, value: int):
        self.binning_vertical_value = max(1, int(value))

    get_binning_vertical = _andor_ccd_methods_coerce_int["get_binning_vertical"]

    get_sensor_readout_mode = _andor_ccd_methods_coerce_int["get_sensor_readout_mode"]

    turn_on_local = _andor_ccd_methods_coerce_int["turn_on_local"]

    turn_off_local = _andor_ccd_methods_coerce_int["turn_off_local"]

    release_power_dependency_local = _andor_ccd_methods_coerce_int["release_power_dependency_local"]

    probe_powered_hardware = _andor_ccd_methods_coerce_int["probe_powered_hardware"]

    set_param_after_init_local = _andor_ccd_methods_coerce_int["set_param_after_init_local"]

    @sdk_configuration_mutation
    def _apply_read_mode(self, read_mode_value, controls: Dict) -> None:
        read_mode = self.READ_MODE_MAP.get(int(read_mode_value), "multi_track")
        self.current_read_mode = read_mode

        if read_mode == "multi_track":
            number, height, offset = tuple(controls.get("MultiTrack", (2, 1, 0)))
            self.camera.setup_multi_track_mode(
                number=max(1, int(number)),
                height=max(1, int(height)),
                offset=max(0, int(offset)),
            )
        elif read_mode == "single_track":
            center, width = tuple(controls.get("SingleTrack", (0, 1)))
            self.camera.setup_single_track_mode(
                center=max(0, int(center)),
                width=max(1, int(width)),
            )
        elif read_mode == "image":
            self.camera.setup_image_mode(
                hstart=int(self.offsetX_value),
                hend=int(self.offsetX_value + self.current_width),
                vstart=int(self.offsetY_value),
                vend=int(self.offsetY_value + self.current_height),
                hbin=int(self.binning_horizontal_value),
                vbin=int(self.binning_vertical_value),
            )
        else:
            self.camera.set_read_mode(read_mode)

        self._update_image_geometry_from_mode(self.camera)

    @sdk_configuration_mutation
    def _apply_trigger_mode(self, mode_value) -> None:
        self.trigger_mode_value = int(mode_value)
        trigger_mode = self.TRIGGER_MODE_MAP.get(self.trigger_mode_value, "ext")
        self.camera.set_trigger_mode(trigger_mode)

    @sdk_configuration_mutation
    def _apply_amp_mode_from_controls(self, controls: Dict) -> None:
        channel = controls.get("ADChannel", self.ad_channel_value)
        preamp = controls.get("PreAmpGain", self.gain_value)
        hsspeed_value = controls.get("HSSpeed", (self.oamp_value, self.hsspeed_value))
        if isinstance(hsspeed_value, (tuple, list)):
            oamp = hsspeed_value[0] if len(hsspeed_value) >= 1 else self.oamp_value
            hsspeed = (
                hsspeed_value[1] if len(hsspeed_value) >= 2 else self.hsspeed_value
            )
        else:
            oamp = self.oamp_value
            hsspeed = hsspeed_value

        self.camera.set_amp_mode(
            channel=int(channel),
            oamp=int(oamp),
            hsspeed=int(hsspeed),
            preamp=int(preamp),
        )
        self._update_amp_mode_state(self.camera)

    @sdk_configuration_mutation
    def _apply_acquisition_mode_settings(self) -> None:
        if not self.camera:
            return

        acq_mode = str(self.current_acquisition_mode)
        if acq_mode == "kinetic":
            self.camera.setup_kinetic_mode(
                num_cycle=max(1, int(self.n_kinetics)),
                cycle_time=float(self.kinetic_time_local or 0.0),
                num_acc=max(1, int(self.n_average)),
                cycle_time_acc=float(self.accumulate_time_local or 0.0),
            )
        elif acq_mode == "accum":
            self.camera.setup_accum_mode(
                num_acc=max(1, int(self.n_average)),
                cycle_time_acc=float(self.accumulate_time_local or 0.0),
            )
        elif acq_mode == "fast_kinetic":
            self.camera.setup_fast_kinetic_mode(
                num_acc=max(1, int(self.n_kinetics)),
                cycle_time_acc=float(self.accumulate_time_local or 0.0),
            )
        elif acq_mode == "cont":
            self.camera.setup_cont_mode(cycle_time=float(self.kinetic_time_local or 0.0))
        else:
            self.camera.set_acquisition_mode(acq_mode)

    @sdk_configuration_mutation
    def _apply_parameters(self, controls: Dict):
        if not self.camera:
            return "Camera is not opened"

        controls = dict(controls or {})
        try:
            if "ReadMode" in controls:
                self._apply_read_mode(controls.get("ReadMode"), controls)

            if "TriggerMode" in controls:
                self._apply_trigger_mode(controls.get("TriggerMode"))

            if "ExposureTime" in controls:
                self.camera.set_exposure(float(controls.get("ExposureTime")))
                self.exposure_time_local = float(self.camera.get_exposure())

            acq_mode_value = controls.get(
                "AcquisitionMode",
                self.ACQ_MODE_MAP_INV.get(self.current_acquisition_mode, 5),
            )
            self.current_acquisition_mode = self.ACQ_MODE_MAP.get(
                int(acq_mode_value), "cont"
            )

            if "VSSpeed" in controls:
                self.camera.set_vsspeed(int(controls.get("VSSpeed")))
                self.vsspeed_value = int(self.camera.get_vsspeed())

            self._apply_amp_mode_from_controls(controls)

            if "Temperature" in controls:
                enable_cooler = bool(controls.get("Cooler", True))
                self.camera.set_temperature(
                    int(controls.get("Temperature")),
                    enable_cooler=enable_cooler,
                )
            elif "Cooler" in controls:
                self.camera.set_cooler(bool(controls.get("Cooler")))

            self._apply_acquisition_mode_settings()
            self._update_temperature_status(self.camera)
            self._update_image_geometry_from_mode(self.camera)
            self._refresh_wavelengths_axis(expected_width=self.current_width)
            return 0
        except Exception as exc:
            return f"Could not apply camera parameters: {exc}"

    get_image = _andor_ccd_methods_coerce_int["get_image"]
    del _andor_ccd_methods_coerce_int

    _andor_ccd_methods_v0_refresh_calibration = _bind_andor_ccd_methods_v0_refresh_calibration(_refactor_modules[__name__])
    _v0_refresh_calibration = _andor_ccd_methods_v0_refresh_calibration["_v0_refresh_calibration"]

    _v0_configuration = _andor_ccd_methods_v0_refresh_calibration["_v0_configuration"]

    _v0_worker_tick = _andor_ccd_methods_v0_refresh_calibration["_v0_worker_tick"]

    @command(dtype_out=str)
    def V0Capabilities(self):
        with self._get_lifecycle_lock():
            try:
                if self.camera is not None:
                    self._v0_refresh_calibration(int(self.camera.get_data_dimensions()[1]))
                configuration, active = self._v0_configuration()
                result = self._v0_orders.observe(configuration, active)
            except Exception as exc:
                result = self._v0_orders.unavailable(str(exc))
            return canonical_json(result)

    @command(dtype_in=str, dtype_out=str)
    def V0BeginOrder(self, value):
        """Queue only: armed=False until the worker establishes a watermark."""
        return canonical_json(self._v0_orders.begin(json.loads(value)))

    @command(dtype_in=str, dtype_out=str)
    def V0OrderStatus(self, order_id):
        return canonical_json(self._v0_orders.status(order_id))

    @command(dtype_in=str, dtype_out="bytes")
    def V0ReadOrder(self, order_id):
        """DevEncoded: JSON header and original <u2/<i4/<f4 samples, zlib C-order.

        Failed unsupported/mixed/geometry packets use typed diagnostic segments.
        """
        return self._v0_orders.read(order_id)

    @command(dtype_in=str, dtype_out=str)
    def V0CancelOrder(self, order_id):
        return canonical_json(self._v0_orders.cancel(order_id))

    @command(dtype_in=str, dtype_out=str)
    def V0ReleaseOrder(self, order_id):
        return canonical_json(self._v0_orders.release(order_id))

    wait = _andor_ccd_methods_v0_refresh_calibration["wait"]

    get_controller_status_local = _andor_ccd_methods_v0_refresh_calibration["get_controller_status_local"]

    start_grabbing_local = _andor_ccd_methods_v0_refresh_calibration["start_grabbing_local"]

    stop_grabbing_local = _andor_ccd_methods_v0_refresh_calibration["stop_grabbing_local"]

    grabbing_local = _andor_ccd_methods_v0_refresh_calibration["grabbing_local"]

    @sdk_configuration_mutation
    def set_trigger_mode(self, state):
        self.trigger_mode_value = int(state)
        if self.camera:
            self._apply_trigger_mode(state)

    get_trigger_mode = _andor_ccd_methods_v0_refresh_calibration["get_trigger_mode"]

    @sdk_configuration_mutation
    def set_trigger_source(self, value):
        self.trigger_source_value = int(value)

    get_trigger_source = _andor_ccd_methods_v0_refresh_calibration["get_trigger_source"]

    @sdk_configuration_mutation
    def set_trigger_type(self, value):
        self.trigger_type_value = int(value)

    get_trigger_type = _andor_ccd_methods_v0_refresh_calibration["get_trigger_type"]

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        self.archive_state["ExposureTime"] = (self.get_exposure_time, "float32")
        self.archive_state["Temperature"] = (
            lambda: float(self.temperature_value),
            "float32",
        )

    register_order_local = _andor_ccd_methods_v0_refresh_calibration["register_order_local"]

    give_order_local = _andor_ccd_methods_v0_refresh_calibration["give_order_local"]
    del _andor_ccd_methods_v0_refresh_calibration

    @command
    def RefreshCalibration(self):
        self._refresh_wavelengths_axis(expected_width=self.current_width)

    @command(dtype_out=str)
    def BeginSafePowerOff(self):
        """Stop acquisition and disable cooling, preserving power for warm-up."""
        with self._get_lifecycle_lock():
            book = getattr(self, "_v0_orders", None)
            if book is not None:
                book.unavailable("Camera warm-up started")
            self.abort = True
            result = begin_safe_poweroff(self.camera)
            if self.grabbing_thread and self.grabbing_thread.is_alive():
                self.grabbing_thread.join(timeout=2.0)
            if self.grabbing_thread and self.grabbing_thread.is_alive():
                raise RuntimeError("Andor grabbing worker did not stop; power retained")
            self.set_state(DevState.ON)
            return json.dumps(result)

    @command(dtype_out=str)
    def GetPowerOffSafety(self):
        """Read actual SDK acquisition/cooler/temperature, never cached defaults."""
        with self._get_lifecycle_lock():
            safety = read_poweroff_safety(self.camera)
            self.temperature_value = safety["temperature_c"]
            self.cooler_on_value = safety["cooler_on"]
            self.temperature_status_value = safety["temperature_status"]
            return json.dumps(safety)

    @command(dtype_out=str)
    def ReleaseAfterWarmup(self):
        """Release SDK only after fresh roomward warm-up and stopped acquisition."""
        with self._get_lifecycle_lock():
            safety = read_poweroff_safety(self.camera)
            # Conservative margin above SDK2 Classic/ICCD guidance (> -20 C).
            if safety["cooler_on"] or safety["acquisition_active"] or safety["temperature_c"] < 0:
                raise RuntimeError("Andor remains cold, cooling or acquiring; SDK and power retained")
            self.temperature_value = safety["temperature_c"]
            self.cooler_on_value = safety["cooler_on"]
            self.temperature_status_value = safety["temperature_status"]
            book = getattr(self, "_v0_orders", None)
            if book is not None:
                book.unavailable("Camera SDK released after warm-up")
            self.camera.close()  # Do not swallow a close failure or claim OFF.
            self.camera = None
            self.set_state(DevState.OFF)
            return "SDK released after verified warm-up"

    @command
    def TriggerSoftware(self):
        if not self.camera:
            raise RuntimeError("Camera is not opened")

        for method_name in ("send_software_trigger", "TriggerSoftware"):
            method = getattr(self.camera, method_name, None)
            if callable(method):
                method()
                return

        raise RuntimeError("Software trigger is not available for this camera")

    @command
    def Trigger(self):
        return self.TriggerSoftware()


if __name__ == "__main__":
    DS_ANDOR_CCD.run_server()
