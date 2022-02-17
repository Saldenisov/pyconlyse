#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import requests

from typing import Tuple, Union,  List
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute


try:
    from DeviceServers.General.DS_PDU import DS_PDU
except ModuleNotFoundError:
    from General.DS_PDU import DS_PDU


class DS_Numato_GPIO(DS_PDU):
    """
    Device Server (Tango) which controls the NUMATO pdu using JSON API.
    """
    _version_ = '0.1'
    _model_ = 'NUMATO_GPIO'
    polling = 500


    def init_device(self):
        self._actions = []
        super().init_device()
        self.turn_on()

    def _addr(self):
        return f'http://{self.ip_address}/numato.json'

    def _authentication(self):
        return self.authentication_name, self.authentication_password

    def find_device(self) -> Tuple[int, str]:
        arg_return = -1, ''
        self.info(f"Searching for NUMATO_GPIO device {self.device_name}", True)
        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                arg_return = 1, res.json()['Agent']['SerialNumber']
                outputs_list = res.json()['Outputs']
                self.__set_attributes_numato(outputs_list)
        self._device_id_internal, self._uri = arg_return

    def get_channels_state_local(self) -> Union[int, str]:
        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                outputs_list = res.json()['Outputs']
                return self.__set_attributes_numato(outputs_list)
        return f'Could not get channels states for {self.device_name}. Res {res}'

    def __set_attributes_numato(self, outputs_list) -> Union[int, str]:
        try:
            names = []
            ids = []
            states = []
            actions = []

            for output in outputs_list:
                names.append(output['Name'])
                ids.append(output['ID'])
                states.append(output['State'])
                actions.append(output['Action'])

            self._names = names
            self._states = states
            self._ids = ids
            self._actions = actions
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

    def set_channels_states_local(self, outputs: List[int]) -> Union[int, str]:
        """
               { "Outputs": [{ "ID": 1,  "Action": 1 }]}
        """
        json_dict = {}
        outputs_list = list([{'ID': int(id), 'Action': int(action)} for id, action in zip(self._ids, outputs)])
        json_dict["Outputs"] = list(outputs_list)
        res = self._send_request(json_dict)
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                outputs_list = res.json()['Outputs']
                return self.__set_attributes_netio(outputs_list)
            else:
                return res
        else:
            return 'Unknown error during setting channels'

    def _send_request(self, j_string) -> Union[requests.Response, bool]:
        try:
            res = requests.post(self._addr(), json=j_string, auth=self._authentication())
        except (requests.ConnectionError, requests.RequestException) as e:
            res = False
        finally:
            return res

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.info(f'Searching for device: {self.device_id}', True)
            self.find_device()
        if self._device_id_internal == -1:
            self.set_state(DevState.FAULT)
            return f'Could NOT turn on {self.device_name}: Device could not be found.'
        else:
            self.set_state(DevState.ON)
            return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

    def get_controller_status_local(self) -> Union[int, str]:
        def error(self):
            self._status_check_fault += 1
            if self._status_check_fault > 10:
                self.set_state(DevState.FAULT)

        res = self._get_request()
        if isinstance(res, requests.Response):
            if res.status_code == 200:
                res = self.__set_attributes_netio(res.json()['Outputs'])
                if res == 0:
                    if self._status_check_fault > 0:
                        self._status_check_fault = 0
                    return 0
                else:
                    return f'Could not get controller status of {self.device_name}: {res}.'
            else:
                error(self)
                return f'Could not get controller status of {self.device_name}: {res}.'

            return super().get_controller_status_local()
        else:
            error(self)
            return f'Could not get controller status of {self.device_name}: {res}.'


if __name__ == "__main__":
    DS_Numato_GPIO.run_server()