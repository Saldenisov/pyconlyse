#!/usr/bin/env python


import os as _os

import sys
from pathlib import Path
from typing import List, Tuple, Union
from time import time

# Add the pyconlyse directory to Python path to enable DeviceServers imports
_PYCONLYSE_ROOT = Path(__file__).parent.parent.parent.parent  # Go up 4 levels to the root of pyconlyse
if str(_PYCONLYSE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYCONLYSE_ROOT))


import requests



from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, device_property

from DeviceServers.base.pdu import DS_PDU
from DeviceServers.power.netio.output_actions import output_actions, parse_snapshot



class DS_Netio_pdu(DS_PDU):
    """Device Server (Tango) which controls the NETIO pdu using JSON API."""

    _version_ = "0.2"
    _model_ = "NETIO PDU"
    polling = 500
    request_timeout_s = device_property(dtype=float, default_value=3.0)

    @attribute(dtype=str)
    def firmware_version(self):
        return self._netio_firmware

    @attribute(dtype=str)
    def hardware_model(self):
        return self._netio_model

    @attribute(dtype=str)
    def serial_number(self):
        return self._netio_serial

    @attribute(dtype=float)
    def native_snapshot_age_s(self):
        return max(0.0, time() - self._netio_read_at) if self._netio_read_at else -1.0

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
        self._netio_firmware = self._netio_model = self._netio_serial = ''
        self._netio_read_at = 0.0
        self._actions = []
        self._delays = []
        super().init_device()
        self.register_variables_for_archive()
        self.turn_on()
        print(f"NETIO_STARTUP_COMPLETE: device={self.get_name()} state={self.get_state()}", flush=True)

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
                result = self.__set_attributes_netio(res.json())
                if result == 0:
                    arg_return = 1, self._netio_serial
                else:
                    self.error(f"Invalid NETIO discovery reply: {result}")
        self._device_id_internal, self._uri = arg_return

    def get_channels_state_local(self) -> Union[int, str]:
        with self._get_lifecycle_lock():
            res = self._get_request()
            if isinstance(res, requests.Response):
                if res.status_code == 200:
                    return self.__set_attributes_netio(res.json())
            return f"Could not get channels states for {self.device_name}. Res {res}"

    def __set_attributes_netio(self, payload) -> Union[int, str]:
        try:
            snapshot = parse_snapshot(payload)
            if self._netio_serial and snapshot['serial'] != self._netio_serial:
                raise ValueError('NETIO identity changed; cached output map retained')
            self._names, self._states = snapshot['names'], snapshot['states']
            self._ids, self._actions, self._delays = snapshot['ids'], snapshot['actions'], snapshot['delays']
            self._netio_serial, self._netio_model = snapshot['serial'], snapshot['model']
            self._netio_firmware, self._netio_read_at = snapshot['firmware'], time()
            for id, state in zip(self._ids, self._states):
                data = self.form_archive_data(state, f"output_{id}", dt="uint8")
                self.write_to_archive(data)
            return 0
        except Exception as e:
            return e

    def _get_request(self) -> Union[requests.Response, bool]:
        try:
            res = requests.get(
                self._addr(),
                auth=self._authentication(),
                timeout=max(0.1, float(getattr(self, "request_timeout_s", 3.0))),
            )
        except requests.RequestException as e:
            self.error(f"{e}")
            res = False
        return res

    def set_channels_states_local(self, outputs: List[int]) -> Union[int, str]:
        """{ "Outputs": [{ "ID": 1,  "Action": 1 }]}"""
        with self._get_lifecycle_lock():
            outputs_list = output_actions(self._ids, outputs)
            if not outputs_list:
                return self.get_channels_state_local()
            res = self._send_request({"Outputs": outputs_list})
            if not isinstance(res, requests.Response):
                raise RuntimeError('NETIO write reply unavailable; outcome unknown; no automatic retry')
            res.raise_for_status()
            result = self.__set_attributes_netio(res.json())
            if result != 0:
                raise RuntimeError(f'NETIO write reply is invalid: {result}')
            actual = dict(zip(self._ids, self._states))
            mismatches = [item['ID'] for item in outputs_list
                          if item['Action'] in (0, 1) and actual.get(item['ID']) != item['Action']]
            if mismatches:
                raise RuntimeError(f'NETIO output state not confirmed for IDs {mismatches}; no automatic retry')
            return 0

    def _send_request(self, j_string) -> Union[requests.Response, bool]:
        try:
            res = requests.post(
                self._addr(),
                json=j_string,
                auth=self._authentication(),
                timeout=max(0.1, float(getattr(self, "request_timeout_s", 3.0))),
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
                res = self.__set_attributes_netio(res.json())
                if res == 0:
                    self._status_check_fault = min(self._status_check_fault, 0)
                    self.set_state(DevState.ON)
                    return 0
                error(self)
                return f"Could not get controller status of {self.device_name}: {res}."
            error(self)
            return f"Could not get controller status of {self.device_name}: {res}."

            return super().get_controller_status_local()
        error(self)
        return f"Could not get controller status of {self.device_name}: {res}."


if __name__ == "__main__":
    # ORBconfigFile handling removed - let omniORB use default configuration
    # or rely on OMNIORB_CONFIG environment variable
    DS_Netio_pdu.run_server()
