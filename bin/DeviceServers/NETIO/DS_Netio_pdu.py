#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import ctypes

from typing import Tuple, Union, Dict
from pathlib import Path
from time import sleep
import requests
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property


try:
    from bin.DeviceServers.DS_general import DS_PDU
except ModuleNotFoundError:
    from DS_general import DS_PDU


class DS_Netio_pdu(DS_PDU):
    """"
    Device Server (Tango) which controls the NETIO pdu using JSON API.
    """
    _version_ = '0.1'
    _model_ = 'NETIO PDU'


    @attribute(label="Outputs names", dtype=[str], display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Gives list of outputs names.", polling_period=250)
    def names(self):
        return self._names

    @attribute(label="Outputs ids", dtype=[str], display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Gives list of outputs ids.", polling_period=250)
    def ids(self):
        return self._ids

    @attribute(label="Outputs states", dtype=[int], display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Gives list of outputs states.", polling_period=250)
    def ids(self):
        return self._states

    @attribute(label="Outputs actions", dtype=[int], display_level=DispLevel.EXPERT, access=AttrWriteType.READ,
               doc="Gives list of outputs actions.", polling_period=250)
    def ids(self):
        return self._actions

    @attribute(label="Outputs delays", dtype=[int], display_level=DispLevel.EXPERT, access=AttrWriteType.READ,
               doc="Gives list of outputs delays.", polling_period=250)
    def ids(self):
        return self._delays

    def init_device(self):
        self._names = []
        self._ids = []
        self._states = []
        self._actions = []
        self._delays = []
        super().init_device()

    def _addr(self):
        return f'http://{self.ip_address}/netio.json'

    def _authentication(self):
        return self.authentication_name, self.authentication_password

    def find_device(self) -> Tuple[int, str]:
        arg_return = -1, ''
        self.info(f"Searching for NETIO PDU device {self.device_name()}", True)
        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                arg_return = 1, res.json()['Agent']['SerialNumber']
                outputs_list = res.json()['Outputs']
                self.__set_attributes_netio(outputs_list)
        print(arg_return)
        return arg_return

    def get_channels_state_local(self) -> Union[int, str]:
        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                outputs_list = res.json()['Outputs']
                return self.__set_attributes_netio(outputs_list)
        return f'Could not get channels states for {self.device_name()}. Res {res}'

    def __set_attributes_netio(self, outputs_list) -> Union[int, str]:
        try:
            names = []
            ids = []
            states = []
            actions = []
            delays = []

            for output in outputs_list:
                names.append(output['Name'])
                ids.append(output['ID'])
                states.append(output['State'])
                actions.append(output['Action'])
                delays.append(output['Delay'])

            self._names = names
            self._states = states
            self._ids = ids
            self._actions = actions
            self._delays = delays
            return 0
        except Exception as e:
            return e

    def _get_request(self) -> Union[requests.Response, bool]:
        try:
            res = requests.get(self._addr(), auth=self._authentication())
        except requests.ConnectionError as e:
            self.error(f'{e}')
            res = False
        return res

    def _send_request(self, j_string) -> Union[requests.Response, bool]:
        """
               { "Outputs": [{ "ID": 1,  "Action": 1 }]}
        """
        try:
            res = requests.post(self._addr(), json=j_string, auth=self._authentication())
        except (requests.ConnectionError, requests.RequestException) as e:
            res = False
        return res

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.info(f'Searching for device: {self.device_id}', True)
            self._device_id_internal, self._uri = self.find_device()

        if self._device_id_internal == -1:
            self.set_state(DevState.FAULT)
            return f'Could NOT turn on {self.device_name()}: Device could not be found.'
        else:
            self.set_state(DevState.ON)
            return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0


if __name__ == "__main__":
    DS_Netio_pdu.run_server()