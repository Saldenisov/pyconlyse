#!/usr/bin/env python


import os as _os
import time as _time

_BOOT_T0 = _time.time()
_DEBUG_BOOT = str(_os.environ.get("DEBUG_BOOT", "")).strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
)

import sys
from pathlib import Path
from typing import List, Tuple, Union

# Parse --DEBUG early, before importing base classes, so env flags are visible
try:
    if "--DEBUG" in sys.argv:
        _os.environ["DEBUG_INIT_TIMING"] = "1"
        _os.environ["DEBUG_TIMING_THRESHOLD_MS"] = "1"
        _os.environ["DEBUG_FUNCTION_TIMING"] = "1"
        _os.environ["DEBUG_FUNCTION_MIN_MS"] = "1"
        _os.environ["DEBUG_BOOT"] = "1"
        # Also set the module flag immediately so BOOT prints are enabled in this process
        _DEBUG_BOOT = True
        sys.argv.remove("--DEBUG")
        try:
            print("DEBUG: timing flags enabled via --DEBUG")
        except Exception:
            pass
except Exception:
    pass

import requests

# Helper to print boot timing messages safely
_def_boot_msg = (
    lambda msg: (
        print(f"BOOT: {msg} T={( _time.time() - _BOOT_T0 ) * 1000.0:.1f} ms")
        if _DEBUG_BOOT
        else None
    )
)

_def_boot_msg("after DS_Netio_pdu basic imports")

app_folder = Path(__file__).resolve().parents[3]  # Go to pyconlyse root directory
sys.path.append(str(app_folder))

_def_boot_msg("before tango import")
from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute
_def_boot_msg("after tango import")

try:
    from DeviceServers.base.pdu import DS_PDU
except ModuleNotFoundError:
    from DeviceServers.base.pdu import DS_PDU
_def_boot_msg("after DS_PDU import")

# Global handle for faulthandler output file
_FAULTHANDLER_FILE = None


class DS_Netio_pdu(DS_PDU):
    """Device Server (Tango) which controls the NETIO pdu using JSON API."""

    _version_ = "0.1"
    _model_ = "NETIO PDU"
    polling = 500

    @attribute(
        label="Outputs actions",
        dtype=[
            int,
        ],
        max_dim_x=10,
        display_level=DispLevel.EXPERT,
        access=AttrWriteType.READ,
        doc="Gives list of outputs actions.",
        polling_period=polling,
    )
    def actions(self):
        return self._actions

    @attribute(
        label="Outputs delays",
        dtype=[
            int,
        ],
        max_dim_x=10,
        display_level=DispLevel.EXPERT,
        access=AttrWriteType.READ,
        doc="Gives list of outputs delays.",
        polling_period=polling,
    )
    def delays(self):
        return self._delays

    def init_device(self):
        # Cancel any pending startup traceback dumps now that init has started
        try:
            import faulthandler as _fhmod
            _fhmod.cancel_dump_traceback_later()
            global _FAULTHANDLER_FILE
            try:
                if _FAULTHANDLER_FILE:
                    _FAULTHANDLER_FILE.close()
            except Exception:
                pass
        except Exception:
            pass
        self._actions = []
        self._delays = []
        super().init_device()
        self.register_variables_for_archive()
        self.turn_on()

    def _addr(self):
        return f"http://{self.ip_address}/netio.json"

    def _authentication(self):
        return self.authentication_name, self.authentication_password

    def find_device(self) -> Tuple[int, str]:
        arg_return = -1, ""
        self.info(f"Searching for NETIO PDU device {self.device_name}", True)
        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                arg_return = 1, res.json()["Agent"]["SerialNumber"]
                outputs_list = res.json()["Outputs"]
                self.__set_attributes_netio(outputs_list)
        self._device_id_internal, self._uri = arg_return

    def get_channels_state_local(self) -> Union[int, str]:
        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                outputs_list = res.json()["Outputs"]
                return self.__set_attributes_netio(outputs_list)
        return f"Could not get channels states for {self.device_name}. Res {res}"

    def __set_attributes_netio(self, outputs_list) -> Union[int, str]:
        try:
            names = []
            ids = []
            states = []
            actions = []
            delays = []

            for output in outputs_list:
                names.append(output["Name"])
                ids.append(output["ID"])
                states.append(output["State"])
                actions.append(output["Action"])
                delays.append(output["Delay"])

            self._names = names
            self._states = states
            self._ids = ids
            self._actions = actions
            self._delays = delays
            for id, state in zip(ids, states):
                data = self.form_archive_data(state, f"output_{id}", dt="uint8")
                self.write_to_archive(data)
            return 0
        except Exception as e:
            return e

    def _get_request(self) -> Union[requests.Response, bool]:
        try:
            res = requests.get(self._addr(), auth=self._authentication())
        except requests.ConnectionError as e:
            self.error(f"{e}")
            res = False
        return res

    def set_channels_states_local(self, outputs: List[int]) -> Union[int, str]:
        """{ "Outputs": [{ "ID": 1,  "Action": 1 }]}"""
        json_dict = {}
        outputs_list = list(
            [
                {"ID": int(id), "Action": int(action)}
                for id, action in zip(self._ids, outputs)
            ]
        )
        json_dict["Outputs"] = list(outputs_list)
        res = self._send_request(json_dict)
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                outputs_list = res.json()["Outputs"]
                return self.__set_attributes_netio(outputs_list)
            return res
        return "Unknown error during setting channels"

    def _send_request(self, j_string) -> Union[requests.Response, bool]:
        try:
            res = requests.post(
                self._addr(), json=j_string, auth=self._authentication()
            )
        except (requests.ConnectionError, requests.RequestException) as e:
            self.error(f"{e}")
            res = False
        return res

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.info(f"Searching for device: {self.device_id}", True)
            self.find_device()
        if self._device_id_internal == -1:
            self.set_state(DevState.FAULT)
            return f"Could NOT turn on {self.device_name}: Device could not be found."
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

    def register_variables_for_archive(self):
        from functools import partial

        super().register_variables_for_archive()
        extra = {}
        extra["output1"] = (partial(self.get_channel_state, 0), "int8")
        extra["output2"] = (partial(self.get_channel_state, 1), "int8")
        extra["output3"] = (partial(self.get_channel_state, 2), "int8")
        extra["output4"] = (partial(self.get_channel_state, 3), "int8")
        self.archive_state.update(extra)

    def get_channel_state(self, channel):
        return self._states[channel]

    def get_controller_status_local(self) -> Union[int, str]:
        def error(self):
            self._status_check_fault += 1
            if self._status_check_fault > 10:
                self.set_state(DevState.FAULT)

        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                res = self.__set_attributes_netio(res.json()["Outputs"])
                if res == 0:
                    self._status_check_fault = min(self._status_check_fault, 0)
                    return 0
                return f"Could not get controller status of {self.device_name}: {res}."
            error(self)
            return f"Could not get controller status of {self.device_name}: {res}."

            return super().get_controller_status_local()
        error(self)
        return f"Could not get controller status of {self.device_name}: {res}."


if __name__ == "__main__":
    # If boot debugging is on, schedule periodic stack dumps to help locate startup delays
    if _DEBUG_BOOT:
        try:
            import faulthandler as _fh
            trace_path = Path(__file__).with_suffix(".startup.trace")
            _FAULTHANDLER_FILE = open(trace_path, "w", encoding="utf-8", errors="replace")
            # Dump every 5 seconds until canceled in init_device()
            _fh.dump_traceback_later(5, repeat=True, file=_FAULTHANDLER_FILE)
        except Exception:
            pass
        try:
            print(
                f"BOOT: before run_server T={(_time.time() - _BOOT_T0) * 1000.0:.1f} ms"
            )
        except Exception:
            pass
    DS_Netio_pdu.run_server()
