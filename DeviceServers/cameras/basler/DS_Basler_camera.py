#!/usr/bin/python3 -u
import os
import sys
import time
from pathlib import Path

try:
    import cv2
except ImportError:  # Optional: only used for center-of-gravity calculation.
    cv2 = None

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from collections import OrderedDict
from threading import Event, Thread, current_thread
from typing import Union

import numpy as np

from DeviceServers.control.laser_pointing.beam_metrics import beam_visibility

try:
    from pypylon import genicam, pylon
except ImportError:  # Allow the Tango server to report a recoverable SDK error.
    genicam = None
    pylon = None
from tango import AttrWriteType, DevState

# -----------------------------
from tango.server import attribute, device_property

from DeviceServers.base.camera import DS_CAMERA_CCD


class DS_Basler_camera(DS_CAMERA_CCD):
    """Basler
    This controls the connection to Basler Cameras. One can also see many of
    the properties form the camera as well as the image observed by it.
    Moreover, if the camera is configured for triggered image acquisition,
    you can trigger image captures at particular points in time (in timeoutt).

    There are two types of grab strategies: one by one (the images are
    processed in the order of their arrival) or latest only (The images are processed
    in the order of their arrival but only the last received image is kept in
    the output queue.This strategy can be useful when the acquired images are
    only displayed on the screen. If the processor has been busy for a while
    and images could not be displayed automatically the latest image is
    displayed when processing time is available again.).

    Sensor readout mode: normal (the readout time for each row of pixels
    remains unchanged), fast (the readout time for each row of pixels is
                              reduced, compared to normal readout. )
    """

    polling_main = 5000
    polling_infinite = 100000
    timeoutt = 5000
    cg_threshold = device_property(dtype=int, default_value=50)
    ip_address = device_property(dtype=str)

    # Publish the GenICam node ranges on the corresponding writable Tango
    # attributes. Taurus input widgets use this metadata to reject invalid
    # values before a write reaches the camera SDK.
    WRITABLE_RANGE_NODES = {
        "width": ("Width", int),
        "height": ("Height", int),
        "offsetX": ("OffsetX", int),
        "offsetY": ("OffsetY", int),
        "exposure_time": ("ExposureTimeAbs", float),
        "gain": ("GainRaw", int),
    }

    def _publish_writable_attribute_ranges(self):
        if self.camera is None or not self.camera.IsOpen():
            return

        try:
            device_attributes = self.get_device_attr()
        except Exception:
            # Unit-test stubs and partially constructed server instances do not
            # necessarily expose Tango's MultiAttribute object.
            return

        for attribute_name, (node_name, value_type) in (
            self.WRITABLE_RANGE_NODES.items()
        ):
            try:
                node = getattr(self.camera, node_name)
                writable_attribute = device_attributes.get_w_attr_by_name(
                    attribute_name
                )
                writable_attribute.set_min_value(value_type(node.Min))
                writable_attribute.set_max_value(value_type(node.Max))
            except Exception as error:
                self.warn(
                    f"Could not publish {attribute_name} camera limits: {error}"
                )

    def get_camera_friendly_name(self):
        return self.camera.DeviceUserID.GetValue()

    def set_camera_friendly_name(self, value):
        self.friendly_name = str(value)
        self.camera.DeviceUserID.SetValue(str(value))

    def get_camera_serial_number(self) -> Union[str, int]:
        return self.device.GetSerialNumber()

    def get_camera_model_name(self) -> str:
        return self.camera.GetDeviceInfo().GetModelName()

    def get_exposure_time(self) -> float:
        return self.camera.ExposureTimeAbs()

    def set_exposure_time(self, value: float):
        self.camera.ExposureTimeAbs.SetValue(value)

    def set_trigger_delay(self, value: str):
        self.camera.TriggerDelayAbs.SetValue(value)

    def get_trigger_delay(self) -> str:
        return self.camera.TriggerDelayAbs()

    def get_exposure_min(self):
        return self.camera.ExposureTimeAbs.Min

    def get_exposure_max(self):
        return self.camera.ExposureTimeAbs.Max

    def set_gain(self, value: int):
        self.camera.GainRaw.SetValue(value)

    def get_gain(self) -> int:
        return self.camera.GainRaw()

    def get_gain_min(self) -> int:
        return self.camera.GainRaw.Min

    def get_gain_max(self) -> int:
        return self.camera.GainRaw.Max

    def get_width(self) -> int:
        return self.camera.Width()

    def set_width(self, value: int):
        was_grabbing = False
        if self.grabbing:
            was_grabbing = True
            self.stop_grabbing()
        self.camera.Width.SetValue(value)
        self._publish_writable_attribute_ranges()
        if was_grabbing:
            self.start_grabbing()

    def get_width_min(self):
        return self.camera.Width.Min

    def get_width_max(self):
        return self.camera.Width.Max

    def set_height(self, value: int):
        was_grabbing = False
        if self.grabbing:
            was_grabbing = True
            self.stop_grabbing()
        self.camera.Height.SetValue(value)
        self._publish_writable_attribute_ranges()
        if was_grabbing:
            self.start_grabbing()

    def get_height(self) -> int:
        return self.camera.Height()

    def get_height_min(self):
        return self.camera.Height.Min

    def get_height_max(self):
        return self.camera.Height.Max

    def get_offsetX(self) -> int:
        return self.camera.OffsetX()

    def set_offsetX(self, value: int):
        self.camera.OffsetX.SetValue(value)
        self._publish_writable_attribute_ranges()

    def get_offsetY(self) -> int:
        return self.camera.OffsetY()

    def set_offsetY(self, value: int):
        self.camera.OffsetY.SetValue(value)
        self._publish_writable_attribute_ranges()

    def set_format_pixel(self, value: str):
        was_grabbing = False
        if self.grabbing:
            was_grabbing = True
            self.stop_grabbing()
        self.camera.PixelFormat = value
        if was_grabbing:
            self.start_grabbing()

    def get_format_pixel(self) -> str:
        return self.camera.PixelFormat()

    def get_framerate(self):
        return self.camera.ResultingFrameRateAbs()

    def set_binning_horizontal(self, value: int):
        self.camera.BinningHorizontal = value

    def get_binning_horizontal(self) -> int:
        return self.camera.BinningHorizontal()

    def set_binning_vertical(self, value: int):
        self.camera.BinningVertical = value

    def get_binning_vertical(self) -> int:
        return self.camera.BinningVertical()

    def get_sensor_readout_mode(self) -> str:
        return self.camera.SensorReadoutMode.GetValue()

    def init_device(self):
        self.pixel_format = None
        self.camera = None
        self.converter = None
        self.device = None
        self.grabbing_thread = None
        self._grabbing_stop_event = None
        self.CG_valid = False
        self.CG_area = 0.0
        self.beam_visibility_state = "unavailable"
        self.beam_visibility_detail = "No camera frame has been analysed yet."
        self.ambient_light_detected = False
        self.beam_background_value = 0.0
        self.beam_contrast_value = 0.0
        self.beam_foreground_fraction_value = 0.0
        self._last_trigger_timeout_warning = 0.0
        super().init_device()
        self.register_variables_for_archive()

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b""
        if state_ok:
            if pylon is None:
                self.error("Basler SDK unavailable: install pypylon on this host.")
                self._device_id_internal, self._uri = argreturn
                return argreturn
            self.device = self._get_camera_device()
            if self.device is not None:
                try:
                    instance = pylon.TlFactory.GetInstance()
                    self.camera = pylon.InstantCamera(
                        instance.CreateDevice(self.device)
                    )
                    argreturn = (
                        1,
                        str(self.camera.GetDeviceInfo().GetSerialNumber()).encode(
                            "utf-8"
                        ),
                    )
                except Exception as e:
                    self.error(f"Could not open camera. {e}")
            else:
                self.error("Could not find camera.")
        self._device_id_internal, self._uri = argreturn
        return argreturn

    def turn_on_local(self) -> Union[int, str]:
        if pylon is None:
            return "Basler SDK unavailable: install pypylon on this host."
        if self.camera is None:
            return "Could not turn on camera, because it does not exist."
        if not self.camera.IsOpen():
            self.camera.Open()
        if self.converter is None:
            self.converter = pylon.ImageFormatConverter()
        self._publish_writable_attribute_ranges()
        self.set_state(DevState.ON)
        self.get_camera_friendly_name()
        self.info(f"{self.device_name} was Opened.", True)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        if self.camera and self.camera.IsOpen():
            if self.grabbing:
                self.stop_grabbing()
            self.camera.Close()
            self.set_state(DevState.OFF)
            self.info(f"{self.device_name} was Closed.", True)
            return 0
        self.set_state(DevState.OFF)
        return 0

    def set_param_after_init_local(self) -> Union[int, str]:
        functions = [
            self.set_transport_layer,
            self.set_analog_controls,
            self.set_aio_controls,
            self.set_acquisition_controls,
            self.set_image_format,
        ]
        results = []
        for func in functions:
            results.append(func())
        self._publish_writable_attribute_ranges()
        results_s = ""
        for res in results:
            if res != 0:
                results_s = results_s + res
        return results_s if results_s else 0

    def set_acquisition_controls(self):
        exposure_time = self.parameters["Acquisition_Controls"]["ExposureTimeAbs"]
        trigger_mode = self.parameters["Acquisition_Controls"]["TriggerMode"]
        trigger_delay = self.parameters["Acquisition_Controls"]["TriggerDelayAbs"]
        frame_rate = self.parameters["Acquisition_Controls"]["AcquisitionFrameRateAbs"]
        trigger_source = self.parameters["Acquisition_Controls"]["TriggerSource"]
        formed_parameters_dict = {
            "TriggerSource": trigger_source,
            "TriggerMode": trigger_mode,
            "TriggerDelayAbs": trigger_delay,
            "ExposureTimeAbs": exposure_time,
            "AcquisitionFrameRateAbs": frame_rate,
            "AcquisitionFrameRateEnable": True,
        }
        if trigger_mode == "Trigger Software":
            self.trigger_software = True
        return self._set_parameters(formed_parameters_dict)

    def set_transport_layer(self) -> Union[int, str]:
        packet_size = self.parameters["Transport_layer"]["Packet_size"]
        inter_packet_delay = self.parameters["Transport_layer"]["Inter-Packet_Delay"]
        formed_parameters_dict = {
            "GevSCPSPacketSize": packet_size,
            "GevSCPD": inter_packet_delay,
        }
        return self._set_parameters(formed_parameters_dict)

    def set_analog_controls(self):
        gain_mode = self.parameters["Analog_Controls"]["GainAuto"]
        gain = self.parameters["Analog_Controls"]["GainRaw"]
        blacklevel = self.parameters["Analog_Controls"]["BlackLevelRaw"]
        balance_ratio = self.parameters["Analog_Controls"]["BalanceRatioRaw"]
        formed_parameters_dict_analog_controls = {
            "GainAuto": gain_mode,
            "GainRaw": gain,
            "BlackLevelRaw": blacklevel,
            "BalanceRatioRaw": balance_ratio,
        }
        return self._set_parameters(formed_parameters_dict_analog_controls)

    def set_aio_controls(self):
        width = self.parameters["AOI_Controls"]["Width"]
        height = self.parameters["AOI_Controls"]["Height"]
        offset_x = self.parameters["AOI_Controls"]["OffsetX"]
        offset_y = self.parameters["AOI_Controls"]["OffsetY"]
        formed_parameters_dict_AOI = OrderedDict()
        formed_parameters_dict_AOI["Width"] = width
        formed_parameters_dict_AOI["Height"] = height
        formed_parameters_dict_AOI["OffsetX"] = offset_x
        formed_parameters_dict_AOI["OffsetY"] = offset_y
        return self._set_parameters(formed_parameters_dict_AOI)

    def set_image_format(self):
        pixel_format = self.parameters["Image_Format_Control"]["PixelFormat"]
        formed_parameters_dict_image_format = {"PixelFormat": pixel_format}
        # to change, what if someone wants color converter
        self.converter.OutputPixelFormat = pylon.PixelType_RGB8packed
        # self.converter.OutputPixelFormat = pylon.PixelType_Mono8
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        return self._set_parameters(formed_parameters_dict_image_format)

    def _set_parameters(self, formed_parameters_dict):
        if self.camera.IsOpen():
            restart_grabbing = self.grabbing
            if self.grabbing:
                self.stop_grabbing()
            try:
                for param_name, param_value in formed_parameters_dict.items():
                    setattr(self.camera, param_name, param_value)
                if restart_grabbing:
                    self.start_grabbing()
                return 0
            except Exception as e:
                if restart_grabbing and not self.grabbing:
                    self.start_grabbing()
                return f'Error appeared: {e} when setting parameter "{param_name}" for camera {self.device_name}.'
        else:
            return (
                f"Basler_Camera {self.device_name} connected states {self.camera.IsOpen()} "
                f"Camera grabbing status is {self.grabbing}."
            )

    def _get_camera_device(self):
        if pylon is None:
            return None
        for device in pylon.TlFactory.GetInstance().EnumerateDevices():
            serial_number = device.GetSerialNumber()
            if serial_number == self.serial_number:
                return device
        return None

    def get_image(self):
        # Attribute reads are passive.  Several preview clients poll ``image``;
        # letting a read call start_grabbing makes an explicit StopGrabbing
        # impossible to hold while any such client remains open.
        return self.last_image

    def calc_cg(self, image):
        """Track a distinct beam without accepting broad room illumination."""
        cX, cY = 1024, 1024
        self.CG_valid = False
        self.CG_area = 0.0
        if cv2 is None:
            self.warn("OpenCV unavailable; center-of-gravity calculation skipped.")
            self.CG_position = {"X": cX, "Y": cY}
            return
        try:
            diagnosis = beam_visibility(image, self.cg_threshold)
            self.beam_visibility_state = str(diagnosis["status"])
            self.beam_visibility_detail = str(diagnosis["message"])
            self.ambient_light_detected = bool(diagnosis["ambient_light_high"])
            self.beam_background_value = float(diagnosis["background_level"])
            self.beam_contrast_value = float(diagnosis["contrast"])
            self.beam_foreground_fraction_value = float(
                diagnosis["foreground_fraction"]
            )
            self.CG_area = float(diagnosis["area"])
            centroid = diagnosis["centroid"]
            if diagnosis["beam_visible"] and centroid is not None:
                cX, cY = (int(round(value)) for value in centroid)
                self.CG_valid = True
        except Exception as error:
            self.beam_visibility_state = "unavailable"
            self.beam_visibility_detail = f"Beam visibility analysis failed: {error}"
            self.ambient_light_detected = False
            self.warn(self.beam_visibility_detail)

        self.CG_position = {"X": cX, "Y": cY}
        data = self.form_archive_data(
            np.array([self.CG_position["X"], self.CG_position["Y"]]).reshape((1, 2)),
            "cg_position",
            dt="uint16",
        )
        self.write_to_archive(data)

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def _awaiting_external_trigger(self) -> bool:
        """Return whether acquisition is intentionally waiting for a line trigger."""
        try:
            return (
                self.camera.TriggerMode.GetValue() == "On"
                and self.camera.TriggerSource.GetValue() != "Software"
            )
        except Exception:
            return False

    def _log_trigger_timeout(self, timeout: int):
        """Warn at a bounded rate while an externally triggered camera is idle."""
        now = time.monotonic()
        if now - self._last_trigger_timeout_warning >= 60:
            source = self.camera.TriggerSource.GetValue()
            self.warn(
                f"No frame received for {timeout} ms; awaiting external trigger "
                f"on {source}. Acquisition remains active.",
                True,
            )
            self._last_trigger_timeout_warning = now

    def wait(self, timeout, stop_event=None):
        # One event belongs to one acquisition worker.  Reusing a single
        # boolean/event across stop -> start lets the old worker wake up after
        # the new acquisition starts and contend for the same camera stream.
        stop_event = stop_event or Event()
        i = 0
        max_errors = 10
        error_count = 0

        while not stop_event.is_set() and self.grabbing and error_count < max_errors:
            # Check if camera is still available
            if (
                not self.camera
                or not self.camera.IsOpen()
                or not self.camera.IsGrabbing()
            ):
                self.info(
                    "Camera no longer available or not grabbing, stopping wait loop"
                )
                break

            i += 1
            self.info(f"Grabbing: {i}", False)
            grab_result = None
            try:
                grab_result = self.camera.RetrieveResult(
                    timeout, pylon.TimeoutHandling_Return
                )
                # StopGrabbing intentionally interrupts RetrieveResult.  That
                # invalid result is a clean shutdown, not a failed grab.
                if (
                    stop_event.is_set()
                    or not self.camera
                    or not self.camera.IsGrabbing()
                ):
                    break
                if grab_result is not None and grab_result.IsValid() and grab_result.GrabSucceeded():
                    image = np.array(
                        self.converter.Convert(grab_result).GetArray(), copy=True
                    )
                    self.calc_cg(image)
                    # data = self.form_archive_data(image, f'image', dt='uint8')
                    # self.write_to_archive(data)
                    # Convert 3D array to 2D for Tango to transfer it
                    image2D = image.transpose(2, 0, 1).reshape(-1, image.shape[1])
                    self.info("Image is received...")
                    self.last_image = image2D
                    error_count = 0  # Reset error count on success
                elif self._awaiting_external_trigger():
                    self._log_trigger_timeout(timeout)
                else:
                    raise pylon.GenericException("Grab failed")
            except (pylon.GenericException, pylon.TimeoutException) as e:
                error_count += 1
                self.error(f"Grabbing error {error_count}/{max_errors}: {e!s}")
                if error_count >= max_errors:
                    self.error("Too many grabbing errors, stopping grabbing thread")
                    break
                # Small delay before retrying
                time.sleep(0.1)
            finally:
                if grab_result is not None and grab_result.IsValid():
                    grab_result.Release()

        # Clean exit
        if (
            not stop_event.is_set()
            and getattr(self, "_grabbing_stop_event", None) is stop_event
            and self.camera
            and self.camera.IsGrabbing()
        ):
            self.stop_grabbing_local()
        if getattr(self, "grabbing_thread", None) is current_thread():
            self.grabbing_thread = None
        self.info("Wait thread exiting")

    def get_controller_status_local(self) -> Union[int, str]:
        if self.camera is None:
            return "Basler camera is not initialized"
        r = 0
        if self.camera.IsOpen():
            self.set_status(DevState.ON)
        else:
            a = os.system("ping -c 1 -n 1 -w 1 " + str(self.ip_address))
            if a == 0:
                self.set_status(DevState.OFF)
            else:
                self.set_status(DevState.FAULT)
                r = f"{self.ip_address} is not reachable."
        return r

    def start_grabbing_local(self):
        if not self.camera or not self.camera.IsOpen():
            return "Camera not available or not open"
        if self.camera.IsGrabbing():
            return 0

        previous_thread = getattr(self, "grabbing_thread", None)
        if (
            previous_thread is not None
            and getattr(previous_thread, "is_alive", lambda: False)()
        ):
            return "Previous grabbing thread is still exiting"

        try:
            stop_event = Event()
            self._grabbing_stop_event = stop_event
            if self.latestimage:
                self.info("Grabbing LatestImageOnly", True)
                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                # Start grabbing thread only if camera is grabbing
                if self.camera.IsGrabbing():
                    self.grabbing_thread = Thread(
                        target=self.wait, args=[self.timeoutt, stop_event]
                    )
                    self.grabbing_thread.daemon = True  # Make thread daemon
                    self.grabbing_thread.start()
            else:
                self.info("Grabbing OneByOne", True)
                self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
                # Start grabbing thread only if camera is grabbing
                if self.camera.IsGrabbing():
                    self.grabbing_thread = Thread(
                        target=self.wait, args=[self.timeoutt, stop_event]
                    )
                    self.grabbing_thread.daemon = True  # Make thread daemon
                    self.grabbing_thread.start()
            return 0
        except Exception as e:
            self.error(f"Error starting grabbing: {e!s}")
            return str(e)

    def stop_grabbing_local(self):
        try:
            stop_event = getattr(self, "_grabbing_stop_event", None)
            if stop_event is not None:
                stop_event.set()
            if self.camera and self.camera.IsGrabbing():
                self.camera.StopGrabbing()
            worker = getattr(self, "grabbing_thread", None)
            if worker is not None and worker is not current_thread():
                join = getattr(worker, "join", None)
                if join is not None:
                    # StopGrabbing normally wakes RetrieveResult immediately.
                    # A short join prevents a following start from overlapping
                    # the old acquisition worker without blocking Tango for the
                    # full external-trigger timeout.
                    join(timeout=1.0)
                if not getattr(worker, "is_alive", lambda: False)():
                    self.grabbing_thread = None
            return 0
        except Exception as e:
            return str(e)

    def grabbing_local(self):
        if self.camera:
            return self.camera.IsGrabbing()
        return False

    def get_trigger_mode(self) -> int:
        return 1 if self.camera.TriggerMode.GetValue() == "On" else 0

    def set_trigger_mode(self, value: int):
        state = "On" if value else "Off"
        self.info(f"Enabling hardware trigger: {state}", True)
        restart = False
        if self.grabbing:
            self.stop_grabbing()
            restart = True
        try:
            self.camera.TriggerMode = state
        except Exception as e:
            self.error(e)
        if restart:
            self.start_grabbing()

    @attribute(
        label="Center of gravity threshold", dtype=int, access=AttrWriteType.READ_WRITE
    )
    def center_gravity_threshold(self):
        return self.cg_threshold

    def write_center_gravity_threshold(self, value):
        self.cg_threshold = value

    @attribute(label="Center of gravity is valid", dtype=bool, access=AttrWriteType.READ)
    def cg_valid(self):
        return self.CG_valid

    @attribute(label="Tracked contour area", dtype=float, access=AttrWriteType.READ)
    def cg_area(self):
        return self.CG_area

    @attribute(label="Beam visibility status", dtype=str, access=AttrWriteType.READ)
    def beam_visibility_status(self):
        return self.beam_visibility_state

    @attribute(label="Beam visibility message", dtype=str, access=AttrWriteType.READ)
    def beam_visibility_message(self):
        return self.beam_visibility_detail

    @attribute(label="Ambient light is too high", dtype=bool, access=AttrWriteType.READ)
    def ambient_light_high(self):
        return self.ambient_light_detected

    @attribute(label="Camera background level", dtype=float, access=AttrWriteType.READ)
    def beam_background(self):
        return self.beam_background_value

    @attribute(label="Beam contrast above background", dtype=float, access=AttrWriteType.READ)
    def beam_contrast(self):
        return self.beam_contrast_value

    @attribute(label="Fraction of image above beam threshold", dtype=float, access=AttrWriteType.READ)
    def beam_foreground_fraction(self):
        return self.beam_foreground_fraction_value


if __name__ == "__main__":
    DS_Basler_camera.run_server()
