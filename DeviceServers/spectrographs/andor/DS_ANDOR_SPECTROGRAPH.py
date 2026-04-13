#!/usr/bin/python3 -u
import sys
from pathlib import Path
from typing import Union

import numpy as np
from tango import AttrWriteType, DevState
from tango.server import attribute, command, device_property

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from DeviceServers.andor.pylablib_backend import get_andor_module
from DeviceServers.base.general import DS_General


class DS_ANDOR_SPECTROGRAPH(DS_General):
    RULES = {**DS_General.RULES}

    _version_ = "0.1"
    _model_ = "ANDOR Shamrock/Kymera (pylablib)"

    dll_path = device_property(dtype=str, default_value="")
    shamrock_dll_path = device_property(dtype=str, default_value="")
    spectrograph_index = device_property(dtype=int, default_value=0)
    pixel_number = device_property(dtype=int, default_value=1064)
    pixel_width_um = device_property(dtype=float, default_value=13.5)
    linked_camera_ds = device_property(dtype=str, default_value="")
    start_on_init = device_property(dtype=int, default_value=1)

    def init_device(self):
        self.spectrograph = None
        self.serial_number_value = ""
        self.current_wavelength_nm = 0.0
        self.current_grating = 1
        self.gratings_number_value = 0
        self.input_side_slit_um_value = 0.0
        self.output_side_slit_um_value = 0.0
        self.input_direct_slit_um_value = 0.0
        self.output_direct_slit_um_value = 0.0
        self.calibration_axis_nm = np.array([], dtype=np.float32)
        self.lines_per_mm_value = 0.0
        self.blaze_wavelength_nm_value = 0.0
        super().init_device()
        self.register_variables_for_archive()
        if bool(int(self.start_on_init or 0)):
            try:
                self.turn_on()
            except Exception as exc:
                self.warn(f"Auto-start spectrograph failed: {exc}", True)

    @attribute(label="serial number", dtype=str, access=AttrWriteType.READ)
    def serial_number(self):
        return str(self.serial_number_value)

    @attribute(
        label="center wavelength nm",
        dtype=float,
        access=AttrWriteType.READ_WRITE,
    )
    def wavelength_nm(self):
        return float(self.current_wavelength_nm)

    def write_wavelength_nm(self, value: float):
        self.set_wavelength_nm(value)

    @attribute(label="grating", dtype=int, access=AttrWriteType.READ_WRITE)
    def grating(self):
        return int(self.current_grating)

    def write_grating(self, value: int):
        self.set_grating_index(value)

    @attribute(label="gratings number", dtype=int, access=AttrWriteType.READ)
    def gratings_number(self):
        return int(self.gratings_number_value)

    @attribute(label="pixel number", dtype=int, access=AttrWriteType.READ_WRITE)
    def pixel_number_attr(self):
        return int(self.pixel_number)

    def write_pixel_number_attr(self, value: int):
        self.pixel_number = int(value)
        self.refresh_calibration_axis()

    @attribute(label="pixel width um", dtype=float, access=AttrWriteType.READ_WRITE)
    def pixel_width_um_attr(self):
        return float(self.pixel_width_um)

    def write_pixel_width_um_attr(self, value: float):
        self.pixel_width_um = float(value)
        self.refresh_calibration_axis()

    @attribute(
        label="input side slit um",
        dtype=float,
        access=AttrWriteType.READ_WRITE,
    )
    def input_side_slit_um(self):
        return float(self.input_side_slit_um_value)

    def write_input_side_slit_um(self, value: float):
        self._set_slit_width("input_side", value)

    @attribute(
        label="output side slit um",
        dtype=float,
        access=AttrWriteType.READ_WRITE,
    )
    def output_side_slit_um(self):
        return float(self.output_side_slit_um_value)

    def write_output_side_slit_um(self, value: float):
        self._set_slit_width("output_side", value)

    @attribute(
        label="input direct slit um",
        dtype=float,
        access=AttrWriteType.READ_WRITE,
    )
    def input_direct_slit_um(self):
        return float(self.input_direct_slit_um_value)

    def write_input_direct_slit_um(self, value: float):
        self._set_slit_width("input_direct", value)

    @attribute(
        label="output direct slit um",
        dtype=float,
        access=AttrWriteType.READ_WRITE,
    )
    def output_direct_slit_um(self):
        return float(self.output_direct_slit_um_value)

    def write_output_direct_slit_um(self, value: float):
        self._set_slit_width("output_direct", value)

    @attribute(
        label="calibration axis",
        dtype=(float,),
        max_dim_x=4096,
        access=AttrWriteType.READ,
    )
    def calibration(self):
        self.refresh_calibration_axis()
        return np.asarray(self.calibration_axis_nm, dtype=np.float32)

    @attribute(label="lines per mm", dtype=float, access=AttrWriteType.READ)
    def lines_per_mm(self):
        return float(self.lines_per_mm_value)

    @attribute(label="blaze wavelength nm", dtype=float, access=AttrWriteType.READ)
    def blaze_wavelength_nm(self):
        return float(self.blaze_wavelength_nm_value)

    def _create_spectrograph(self):
        Andor = get_andor_module(
            sdk_path=self.dll_path,
            shamrock_path=self.shamrock_dll_path,
        )
        return Andor.ShamrockSpectrograph(idx=int(self.spectrograph_index or 0))

    def _setup_calibration_geometry(self):
        if self.spectrograph is None:
            return

        try:
            self.spectrograph.set_number_pixels(int(self.pixel_number))
        except Exception:
            pass

        try:
            self.spectrograph.set_pixel_width(float(self.pixel_width_um) * 1e-6)
        except Exception:
            pass

    def _sync_from_spectrograph(self, spectrograph) -> None:
        self._setup_calibration_geometry()
        try:
            self.serial_number_value = str(spectrograph.get_device_info())
        except Exception:
            self.serial_number_value = f"index-{self.spectrograph_index}"

        try:
            self.current_wavelength_nm = float(spectrograph.get_wavelength()) * 1e9
        except Exception:
            pass

        try:
            self.current_grating = int(spectrograph.get_grating())
        except Exception:
            pass

        try:
            self.gratings_number_value = int(spectrograph.get_gratings_number())
        except Exception:
            pass

        self._read_slit_widths(spectrograph)
        self._read_grating_info(spectrograph)
        self.refresh_calibration_axis()

    def _read_grating_info(self, spectrograph) -> None:
        try:
            info = spectrograph.get_grating_info(self.current_grating)
        except Exception:
            return

        try:
            self.lines_per_mm_value = float(getattr(info, "lines", info[0]))
        except Exception:
            pass
        try:
            blaze_raw = getattr(info, "blaze_wavelength", info[1])
            self.blaze_wavelength_nm_value = float(blaze_raw) * 1e9
        except Exception:
            pass

    def _read_slit_widths(self, spectrograph=None) -> None:
        spec = spectrograph or self.spectrograph
        if spec is None:
            return

        slit_map = {
            "input_side": "input_side_slit_um_value",
            "output_side": "output_side_slit_um_value",
            "input_direct": "input_direct_slit_um_value",
            "output_direct": "output_direct_slit_um_value",
        }
        for slit_name, attr_name in slit_map.items():
            try:
                value_um = float(spec.get_slit_width(slit_name)) * 1e6
                setattr(self, attr_name, value_um)
            except Exception:
                continue

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        self.archive_state["WavelengthNm"] = (
            lambda: float(self.current_wavelength_nm),
            "float32",
        )
        self.archive_state["Grating"] = (lambda: int(self.current_grating), "uint8")

    def find_device(self):
        self.info(f"Searching for Andor spectrograph {self.device_name}", True)
        arg_return = -1, b""
        try:
            spectrograph = self._create_spectrograph()
            try:
                self.spectrograph = spectrograph
                self._setup_calibration_geometry()
                self._sync_from_spectrograph(spectrograph)
                uri = (
                    f"andor-shamrock://index/{self.spectrograph_index}"
                ).encode("utf-8")
                arg_return = int(self.spectrograph_index or 0), uri
            finally:
                try:
                    spectrograph.close()
                except Exception:
                    pass
                self.spectrograph = None
        except Exception as exc:
            self.error(f"Could not initialize spectrograph via pylablib: {exc}")

        self._device_id_internal, self._uri = arg_return

    def get_controller_status_local(self) -> Union[int, str]:
        if self.spectrograph is None:
            self.set_state(DevState.OFF)
        else:
            self.set_state(DevState.ON)
        return 0

    def turn_on_local(self) -> Union[int, str]:
        if self.spectrograph is not None:
            self.set_state(DevState.ON)
            return 0

        try:
            self.spectrograph = self._create_spectrograph()
            self._setup_calibration_geometry()
            self._sync_from_spectrograph(self.spectrograph)
            self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.spectrograph = None
            self.set_state(DevState.FAULT)
            return f"Could not turn on spectrograph via pylablib: {exc}"

    def turn_off_local(self) -> Union[int, str]:
        if self.spectrograph is not None:
            try:
                self.spectrograph.close()
            except Exception as exc:
                self.warn(f"Spectrograph close reported: {exc}", True)
            finally:
                self.spectrograph = None
        self.set_state(DevState.OFF)
        return 0

    def refresh_calibration_axis(self):
        if self.spectrograph is None:
            return
        try:
            self._setup_calibration_geometry()
            calibration = np.asarray(self.spectrograph.get_calibration(), dtype=np.float32)
            self.calibration_axis_nm = calibration * 1e9
        except Exception as exc:
            self.warn(f"Calibration update failed: {exc}")

    def set_wavelength_nm(self, value: float):
        self.current_wavelength_nm = float(value)
        if self.spectrograph:
            self.spectrograph.set_wavelength(float(value) * 1e-9)
            self.current_wavelength_nm = float(self.spectrograph.get_wavelength()) * 1e9
            self.refresh_calibration_axis()

    def set_grating_index(self, value: int):
        self.current_grating = int(value)
        if self.spectrograph:
            self.spectrograph.set_grating(int(value))
            self.current_grating = int(self.spectrograph.get_grating())
            self._read_grating_info(self.spectrograph)
            self.refresh_calibration_axis()

    def _set_slit_width(self, slit_name: str, value_um: float):
        attr_name = f"{slit_name}_slit_um_value"
        setattr(self, attr_name, float(value_um))
        if self.spectrograph:
            self.spectrograph.set_slit_width(slit_name, float(value_um) * 1e-6)
            self._read_slit_widths()

    @command
    def RefreshCalibration(self):
        self.refresh_calibration_axis()

    @command
    def GoToZeroOrder(self):
        if not self.spectrograph:
            raise RuntimeError("Spectrograph is not opened")
        self.spectrograph.goto_zero_order()
        self.refresh_calibration_axis()


if __name__ == "__main__":
    DS_ANDOR_SPECTROGRAPH.run_server()
