""""
saldenisov
created: 12/08/2020
"""

import requests
from devices.devices_dataclass import HardwareDeviceDict, FuncPowerInput, FuncActivateInput, FuncActivateDeviceInput
from devices.service_devices.pdu.pdu_controller import PDUController, PDUError
from devices.service_devices.pdu.pdu_dataclass import *
from utilities.myfunc import join_smart_comments


class PDUCtrl_NETIO(PDUController):

    def __init__(self, **kwargs):
        kwargs['pdu_dataclass'] = PDUNetio
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, PDUNetio] = HardwareDeviceDict()

        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('ip_address', 'ip_addresses', str),
                                                                      ('authentication', 'authentications', tuple)],
                                                          extra_func=[])
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        if not res:
            raise PDUError(self, comments)
        else:
            self._register_observation('PDU_outputs_state', self._set_all_pdu_outputs, 2)

    def _change_device_status_local(self, device: HardwareDevice, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = False, 'Did not work.'
        change = False
        if device.status == 2 and force:
            change = True
        elif device.status == 2 and device.status != flag:
            res, comments = False, f'Cannot set device status to {flag}. Use force option.'
        else:
            change = True

        if change:
            device.status = flag
            res, comments = True, f'PDU id={device.device_id_seq}, name={device.friendly_name} status is changed to ' \
                                  f'{flag}.'
        return res, comments

    def _check_if_connected(self) -> Tuple[bool, str]:
        results, comments = [], ''
        for pdu_id, pdu in self.pdus.items():
            res, com = self._get_json(pdu_id)
            if isinstance(res, requests.Response):
                if res.status_code == 200:
                    results.append(True)
                else:
                    results.append(False)
                    # TODO: make joining of comments more clear
                    comments = join_smart_comments(comments, com)
            else:
                results.append(False)
                comments = join_smart_comments(comments, com)
        return any(results), comments

    def _get_number_hardware_devices(self) -> int:
        return len(self.pdus)

    def _get_pdu_outputs(self, pdu_id: Union[int, str]) -> Tuple[bool, str]:
        results, comments = [], ''
        res, com = self._check_device_range(pdu_id)
        results.append(res)
        comments = join_smart_comments(comments, com)
        if res:
            res, com = self._get_json(pdu_id)
            if isinstance(res, requests.Response):
                if res.status_code == 200:
                    results.append(True)
                    pdu: PDUNetio = self.pdus[pdu_id]
                    outputs_l = res.json()['Outputs']
                    outputs = {}
                    for output in outputs_l:
                        outputs[output['ID']] = PDUNetioOutput(id=output['ID'], name=output['Name'],
                                                               state=output['State'], action=output['Action'],
                                                               delay=output['Delay'])
                    if pdu.outputs != outputs:
                        pdu.outputs = outputs
                else:
                    results.append(False)
                    comments = join_smart_comments(comments, com)
        return all(results), comments

    def _form_devices_list(self) -> Tuple[bool, str]:
        discard_id = []
        results, comments = [], ''
        for pdu in self.pdus.values():
            res, com = self._get_json(pdu.device_id)
            discard = False
            if isinstance(res, requests.Response):
                if res.status_code != 200:
                    discard = True
            else:
                discard = True
            if discard:
                comments = join_smart_comments(comments, com)
                discard_id.append(pdu.device_id)
        for pdu_id in discard_id:
            del self.pdus[pdu_id]
        if self.pdus:
            return True, ''
        else:
            return False, join_smart_comments('None of DB listed PDUs are available:', comments)

    @property
    def pdus(self) -> Dict[Union[int, str], PDUNetio]:
        return super().pdus

    def _release_hardware(self) -> Tuple[bool, str]:
        for pdu in self.pdus.values():
            pdu.status = 0
        return True, ''

    def _set_friendly_names(self):
        if self.ctrl_status.connected:
            for pdu in self.pdus.values():
                res, comments = self._get_json(pdu.device_id)
                if isinstance(res, requests.Response):
                    if res.status_code == 200:
                        pdu.friendly_name = res.json()['Agent']['DeviceName']
                    else:
                        pdu.friendly_name = pdu.name
                else:
                    pdu.friendly_name = pdu.name
            return True, ''
        else:
            for pdu in self.pdus.values():
                pdu.friendly_name = pdu.name
            return True, ''

    def _set_mac_addresses(self) -> Tuple[bool, str]:
        results, comments = [], ''
        for pdu_id, pdu in self.pdus.items():
            res, com = self._get_json(pdu_id)
            if isinstance(res, requests.Response):
                if res.status_code == 200:
                    pdu.mac_address = res.json()['Agent']['MAC']
                    results.append(True)
        return True, ''

    def _set_pdu_state(self, func_input: FuncSetPDUStateInput) -> Tuple[bool, str]:
        pdu: PDUNetio = self.pdus[func_input.pdu_id]
        if func_input.pdu_output_id in pdu.outputs:
            if isinstance(func_input.output, int):
                action = func_input.output
            elif isinstance(func_input.output, PDUNetioOutput):
                state_to_set: PDUNetioOutput = func_input.output
                action = 1 if state_to_set.state else 0
            j_string = {"Outputs": [{"ID": func_input.pdu_output_id,  "Action": action}]}
            res, comments = self._send_request(pdu.device_id, j_string)
            if isinstance(res, requests.Response):
                if res.status_code == 200:
                    res, comments = self._get_pdu_outputs(pdu.device_id)
                else:
                    res, comments = False, comments
            return res, comments
        else:
            return False, f'Output id {func_input.pdu_id} is not present in {pdu.outputs.keys()}.'

    def _get_json(self, pdu_id: int) -> Tuple[Union[bool, requests.Response], str]:
        res, comments = self._check_device_range(device_id=pdu_id)
        if res:
            pdu: PDUNetio = self.pdus[pdu_id]
            addr = f'http://{pdu.ip_address}/netio.json'
            authentication = pdu.authentication
            try:
                res, comments = requests.get(addr, auth=authentication), ''
            except requests.ConnectionError as e:
                res, comments = False, f'{e}'
        return res, comments

    def _send_request(self, pdu_id: int, j_string: Dict[Union[int, str], Union[str, int]]) -> Tuple[Union[bool, requests.Response], str]:
        res, comments = self._check_device_range(device_id=pdu_id)
        if res:
            pdu: PDUNetio = self.pdus[pdu_id]
            addr = f'http://{pdu.ip_address}/netio.json'
            authentication = pdu.authentication
            try:
                res, comments = requests.post(addr, json=j_string, auth=authentication), ''
            except (requests.ConnectionError, requests.RequestException) as e:
                res, comments = False, ''
        return res, comments

    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        res, com = super()._set_parameters_after_connect()
        results, comments = [res], com
        res, com = self._set_friendly_names()
        results.append(res)
        comments = join_smart_comments(comments, com)
        res, com = self._set_mac_addresses()
        results.append(res)
        comments = join_smart_comments(comments, com)
        return all(results), comments

