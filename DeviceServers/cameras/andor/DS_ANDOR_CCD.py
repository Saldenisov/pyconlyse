#!/usr/bin/python3 -u
import ast
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

from tango import DeviceProxy

from DeviceServers.andor.pylablib_backend import get_andor_module
from DeviceServers.base.camera import DS_CAMERA_CCD, OrderInfo


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
    camera_index = device_property(dtype=int, default_value=0)
    fan_mode = device_property(dtype=str, default_value="off")
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

    @staticmethod
    def _coerce_int(value, default: int) -> int:
        try:
            if value is None or value == "":
                return int(default)
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _coerce_float(value, default: float) -> float:
        try:
            if value is None or value == "":
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _coerce_str(value, default: str) -> str:
        if value is None:
            return str(default)
        text = str(value).strip()
        return text if text else str(default)

    def init_device(self):
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
        self._default_wavelengths = self._parse_array_property(self.wavelengths)
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

    def _parse_array_property(self, raw_value) -> np.ndarray:
        if isinstance(raw_value, np.ndarray):
            return raw_value.astype(np.float32)

        text = str(raw_value or "").strip()
        if not text:
            return np.array([], dtype=np.float32)

        try:
            parsed = ast.literal_eval(text)
        except Exception:
            return np.array([], dtype=np.float32)

        try:
            return np.asarray(parsed, dtype=np.float32).reshape(-1)
        except Exception:
            return np.array([], dtype=np.float32)

    def _create_camera(self):
        Andor = get_andor_module(sdk_path=self.dll_path)
        ini_path = self._coerce_str(self.ini_path, "")
        return Andor.AndorSDK2Camera(
            idx=self._coerce_int(self.camera_index, 0),
            ini_path=ini_path,
            temperature=self._coerce_int(self.default_temperature, -50),
            fan_mode=self._coerce_str(self.fan_mode, "off"),
        )

    def _with_temp_camera(self):
        camera = self._create_camera()
        try:
            yield camera
        finally:
            try:
                camera.close()
            except Exception:
                pass

    def _sync_from_camera(self, camera) -> None:
        info = camera.get_device_info()
        if hasattr(info, "serial_number") or hasattr(info, "head_model"):
            self.serial_number_real = getattr(info, "serial_number", -1)
            self.head_name = getattr(info, "head_model", "Andor")
        elif isinstance(info, tuple):
            if len(info) >= 3:
                self.serial_number_real = info[2]
            if len(info) >= 2:
                self.head_name = str(info[1])
            elif len(info) >= 1:
                self.head_name = str(info[0])
        detector_width, detector_height = camera.get_detector_size()
        self.current_width = int(detector_width)
        self.current_height = int(camera.get_data_dimensions()[0])
        self.height_value = int(detector_height)
        self.track_count_value = max(1, int(camera.get_data_dimensions()[0]))
        self.exposure_time_local = float(camera.get_exposure())
        timings = camera.get_cycle_timings()
        self.accumulate_time_local = float(getattr(timings, "accum_cycle_time", 0.0))
        self.kinetic_time_local = float(getattr(timings, "kinetic_cycle_time", 0.0))
        self.current_read_mode = str(camera.get_read_mode())
        self.current_acquisition_mode = str(camera.get_acquisition_mode())
        self._update_amp_mode_state(camera)
        self._update_temperature_status(camera)
        self._update_image_geometry_from_mode(camera)

    def _update_image_geometry_from_mode(self, camera) -> None:
        try:
            dims = camera.get_data_dimensions()
            if len(dims) == 2:
                self.current_height = int(dims[0])
                self.current_width = int(dims[1])
                self.track_count_value = max(1, int(dims[0]))
        except Exception:
            pass

        if self.current_read_mode == "image":
            try:
                _, _, _, _, hbin, vbin = camera.get_image_mode_parameters()
                self.binning_horizontal_value = int(hbin)
                self.binning_vertical_value = int(vbin)
            except Exception:
                self.binning_horizontal_value = 1
                self.binning_vertical_value = 1
        else:
            self.binning_horizontal_value = 1
            self.binning_vertical_value = 1

    def _update_temperature_status(self, camera=None) -> None:
        cam = camera or self.camera
        if cam is None:
            return

        try:
            self.temperature_value = float(cam.get_temperature())
        except Exception:
            pass
        try:
            self.temperature_target_value = float(cam.get_temperature_setpoint())
        except Exception:
            pass
        try:
            self.temperature_status_value = str(cam.get_temperature_status())
        except Exception:
            pass
        try:
            self.cooler_on_value = bool(cam.is_cooler_on())
        except Exception:
            pass

    def _update_amp_mode_state(self, camera) -> None:
        try:
            amp_mode = camera.get_amp_mode(full=False)
            if len(amp_mode) >= 4:
                self.ad_channel_value = int(amp_mode[0])
                self.oamp_value = int(amp_mode[1])
                self.hsspeed_value = int(amp_mode[2])
                self.gain_value = int(amp_mode[3])
        except Exception:
            pass

        try:
            amp_modes = camera.get_all_amp_modes()
            if amp_modes:
                self.n_gains_max = max(int(mode[6]) for mode in amp_modes)
        except Exception:
            self.n_gains_max = max(self.n_gains_max, self.gain_value)

        try:
            self.vsspeed_value = int(camera.get_vsspeed())
        except Exception:
            pass

    def _refresh_wavelengths_axis(self, expected_width: Optional[int] = None) -> None:
        width = self._coerce_int(expected_width or self.current_width or self.width, 1064)
        axis = np.array([], dtype=np.float32)

        linked_device_name = self._coerce_str(self.linked_spectrograph_ds, "").strip()
        if linked_device_name:
            try:
                linked_ds = DeviceProxy(linked_device_name)
                linked_axis = linked_ds.read_attribute("calibration").value
                axis = np.asarray(linked_axis, dtype=np.float32).reshape(-1)
            except Exception as exc:
                self.warn(f"Could not read calibration from {linked_device_name}: {exc}")

        if axis.size == 0:
            axis = np.asarray(self._default_wavelengths, dtype=np.float32).reshape(-1)

        if axis.size != width:
            axis = np.arange(width, dtype=np.float32)

        self.wavelengths_axis_value = axis
        self.current_width = int(axis.size)

    def _normalize_frame(self, frame) -> np.ndarray:
        frame_array = np.asarray(frame, dtype=np.float32)
        if frame_array.ndim == 1:
            frame_array = frame_array[np.newaxis, :]
        elif frame_array.ndim > 2:
            frame_array = frame_array.reshape(frame_array.shape[0], -1)

        self.current_height = int(frame_array.shape[0])
        self.current_width = int(frame_array.shape[1])
        self.track_count_value = max(1, int(frame_array.shape[0]))
        self._refresh_wavelengths_axis(expected_width=self.current_width)
        return frame_array

    def _consume_frame_for_orders(self, frame: np.ndarray) -> None:
        time_stamp = time_ns()
        self.time_stamp_deque.append(time_stamp)
        self.data_deque.append(frame.copy())

        if not self.orders:
            return

        orders_to_delete = []
        for order_name, order_info in list(self.orders.items()):
            if (time() - order_info.order_timestamp) >= 100:
                orders_to_delete.append(order_name)
                continue

            if order_info.order_done:
                continue

            order_info.order_array = np.vstack([order_info.order_array, frame])
            order_info.frames_done += 1
            if order_info.frames_done >= order_info.order_length:
                order_info.order_done = True

        for order_name in orders_to_delete:
            self.orders.pop(order_name, None)

    def find_device(self) -> Tuple[int, str]:
        self.info(f"Searching for Andor camera {self.device_name}", True)
        argreturn = -1, b""
        try:
            camera = self._create_camera()
            try:
                self._sync_from_camera(camera)
                self._refresh_wavelengths_axis(expected_width=self.current_width)
                uri = (
                    f"andor-sdk2://camera/{self.serial_number_real}"
                    if self.serial_number_real != -1
                    else f"andor-sdk2://index/{self._coerce_int(self.camera_index, 0)}"
                )
                argreturn = self._coerce_int(self.camera_index, 0), uri.encode("utf-8")
            finally:
                camera.close()
        except Exception as exc:
            self.error(f"Could not initialize Andor camera via pylablib: {exc}")

        self._device_id_internal, self._uri = argreturn
        return argreturn

    def get_camera_friendly_name(self):
        return self.friendly_name

    def set_camera_friendly_name(self, value):
        self.friendly_name = str(value)

    def get_camera_serial_number(self) -> Union[str, int]:
        return self.serial_number_real

    def get_camera_model_name(self) -> str:
        return self.head_name

    def get_exposure_time(self) -> float:
        if self.camera:
            try:
                self.exposure_time_local = float(self.camera.get_exposure())
            except Exception:
                pass
        return self.exposure_time_local

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

    def set_trigger_delay(self, value: str):
        self.trigger_source_value = int(float(value))

    def get_trigger_delay(self) -> str:
        return float(self.trigger_source_value)

    def get_exposure_min(self):
        return 0.0

    def get_exposure_max(self):
        return 3600.0

    def set_gain(self, value: int):
        self.gain_value = int(value)
        if self.camera:
            self.camera.set_amp_mode(preamp=self.gain_value)

    def get_gain(self) -> int:
        return int(self.gain_value)

    def get_gain_min(self) -> int:
        return 0

    def get_gain_max(self) -> int:
        return int(max(self.n_gains_max, self.gain_value, 0))

    def get_width(self) -> int:
        return int(self.current_width)

    def set_width(self, value: int):
        self.current_width = max(1, int(value))

    def get_width_min(self):
        return 1

    def get_width_max(self):
        return int(self.current_width)

    def set_height(self, value: int):
        self.current_height = max(1, int(value))

    def get_height(self) -> int:
        return int(self.current_height)

    def get_height_min(self):
        return 1

    def get_height_max(self):
        return int(max(self.current_height, self.height_value))

    def get_offsetX(self) -> int:
        return int(self.offsetX_value)

    def set_offsetX(self, value: int):
        self.offsetX_value = int(value)

    def get_offsetY(self) -> int:
        return int(self.offsetY_value)

    def set_offsetY(self, value: int):
        self.offsetY_value = int(value)

    def set_format_pixel(self, value: str):
        return None

    def get_format_pixel(self) -> str:
        return "float32"

    def get_framerate(self):
        if not self.camera:
            return 0.0
        try:
            timings = self.camera.get_frame_timings()
            frame_period = float(getattr(timings, "frame_period", timings[1]))
            return 0.0 if frame_period <= 0 else 1.0 / frame_period
        except Exception:
            return 0.0

    def set_binning_horizontal(self, value: int):
        self.binning_horizontal_value = max(1, int(value))

    def get_binning_horizontal(self) -> int:
        return int(self.binning_horizontal_value)

    def set_binning_vertical(self, value: int):
        self.binning_vertical_value = max(1, int(value))

    def get_binning_vertical(self) -> int:
        return int(self.binning_vertical_value)

    def get_sensor_readout_mode(self) -> str:
        return str(self.current_read_mode)

    def turn_on_local(self) -> Union[int, str]:
        if self.camera is not None:
            self.set_state(DevState.ON)
            return 0

        try:
            self.camera = self._create_camera()
            self.camera.setup_shutter("open")
            self._sync_from_camera(self.camera)
            self._apply_parameters(self.parameters.get("Acquisition_Controls", {}))
            self._refresh_wavelengths_axis(expected_width=self.current_width)
            self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.camera = None
            self.set_state(DevState.FAULT)
            return f"Could not turn on camera via pylablib: {exc}"

    def turn_off_local(self) -> Union[int, str]:
        if self.grabbing:
            self.stop_grabbing_local()

        if self.camera is not None:
            try:
                self.camera.close()
            except Exception as exc:
                self.warn(f"Camera close reported: {exc}", True)
            finally:
                self.camera = None

        self.set_state(DevState.OFF)
        return 0

    def set_param_after_init_local(self) -> Union[int, str]:
        if not self.camera:
            return "Camera is not opened"
        return self._apply_parameters(self.parameters.get("Acquisition_Controls", {}))

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

    def _apply_trigger_mode(self, mode_value) -> None:
        self.trigger_mode_value = int(mode_value)
        trigger_mode = self.TRIGGER_MODE_MAP.get(self.trigger_mode_value, "ext")
        self.camera.set_trigger_mode(trigger_mode)

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

    def get_image(self):
        if self.last_image is not None:
            return
        if not self.camera:
            return

        try:
            frame = self.camera.snap()
            self.last_image = self._normalize_frame(frame)
        except Exception as exc:
            self.warn(f"Single-frame snap failed: {exc}")

    def wait(self, timeout=0):
        while self.abort is not True and self.camera is not None:
            try:
                self.camera.wait_for_frame(timeout=1.0, error_on_stopped=False)
                frame = self.camera.read_newest_image()
                if frame is None:
                    continue
                normalized = self._normalize_frame(frame)
                self.last_image = normalized
                self._consume_frame_for_orders(normalized)
            except Exception as exc:
                self.warn(f"Andor grabbing loop warning: {exc}")
                sleep(0.1)

    def get_controller_status_local(self) -> Union[int, str]:
        if self.camera is None:
            self.set_state(DevState.OFF)
            return 0
        if self.grabbing:
            self.set_state(DevState.RUNNING)
        else:
            self.set_state(DevState.ON)
        return 0

    def start_grabbing_local(self):
        if not self.camera:
            return "Camera is not opened"

        if self.grabbing_thread and self.grabbing_thread.is_alive():
            return 0

        self.abort = False
        self._apply_acquisition_mode_settings()
        self.camera.setup_acquisition(mode="sequence")
        self.camera.start_acquisition()
        self.grabbing_thread = Thread(target=self.wait, args=[self.timeoutt], daemon=True)
        self.grabbing_thread.start()
        self.set_state(DevState.RUNNING)
        return 0

    def stop_grabbing_local(self):
        self.abort = True
        if self.camera:
            try:
                self.camera.stop_acquisition()
            except Exception:
                pass
        if self.grabbing_thread and self.grabbing_thread.is_alive():
            self.grabbing_thread.join(timeout=1.0)
        self.set_state(DevState.ON if self.camera else DevState.OFF)
        return 0

    def grabbing_local(self):
        return bool(self.grabbing_thread and self.grabbing_thread.is_alive() and not self.abort)

    def set_trigger_mode(self, state):
        self.trigger_mode_value = int(state)
        if self.camera:
            self._apply_trigger_mode(state)

    def get_trigger_mode(self) -> int:
        return int(self.trigger_mode_value)

    def set_trigger_source(self, value):
        self.trigger_source_value = int(value)

    def get_trigger_source(self) -> int:
        return int(self.trigger_source_value)

    def set_trigger_type(self, value):
        self.trigger_type_value = int(value)

    def get_trigger_type(self) -> int:
        return int(self.trigger_type_value)

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        self.archive_state["ExposureTime"] = (self.get_exposure_time, "float32")
        self.archive_state["Temperature"] = (
            lambda: float(self.temperature_value),
            "float32",
        )

    def register_order_local(self, name, value):
        requested_frames = max(1, int(value[0]))
        self._refresh_wavelengths_axis(expected_width=self.current_width)
        self.orders[name] = FrameOrderState(
            order_length=requested_frames,
            order_done=False,
            order_timestamp=time(),
            ready_to_delete=False,
            order_array=np.array([self.wavelengths_axis_value], dtype=np.float32),
            frames_done=0,
        )
        return 0

    def give_order_local(self, name):
        if name in self.orders:
            order = self.orders[name]
            order.ready_to_delete = True
            return np.asarray(order.order_array, dtype=np.float32)

        if self.last_image is None:
            self.get_image()
        if self.last_image is None:
            return np.array([self.wavelengths_axis_value], dtype=np.float32)
        return np.vstack([self.wavelengths_axis_value, self.last_image]).astype(
            np.float32
        )

    @command
    def RefreshCalibration(self):
        self._refresh_wavelengths_axis(expected_width=self.current_width)

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
