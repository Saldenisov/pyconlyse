""""
saldenisov
created: 12/08/2020
"""

import requests

from devices.service_devices.pdu.pdu_controller import PDUController, PDUError
from utilities.datastructures.mes_independent.pdu_dataclass import *
from utilities.myfunc import error_logger, info_msg, join_smart_comments


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

    def _change_device_status(self, pdu_id: Union[int, str], flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_device_range(pdu_id)
        if res:
            res, comments = super()._check_status_flag(flag)
        if res:
            pdu: PDUNetio = self.pdus[pdu_id]
            change = False
            if pdu.status == 2 and force:
                change = True
            elif pdu.status == 2 and pdu.status != flag:
                res, comments = False, f'Cannot set device status to {flag}. Use force option.'
            else:
                change = True

            if change:
                pdu.status = flag
                res, comments = True, f'Device {pdu.friendly_name} status is changed to {flag}.'

        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()

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
                    comments = f'{com}. {comments}'
            else:
                results.append(False)
                comments = f'{com}. {comments}'
        return any(results), comments

    def _get_number_hardware_devices(self):
        return len(self.pdus)

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
        for pdu in self.pdus.values():
            pdu.friendly_name = pdu.name
        return True, ''

    def _set_mac_addresses(self):
        for pdu_id, pdu in self.pdus.items():
            res, com = self._get_json(pdu_id)
            if isinstance(res, requests.Response):
                if res.status_code == 200:
                    pdu.mac_address = res.json()['Agent']['MAC']

    def _set_pdu_state(self, func_input: FuncSetPDUStateInput) -> Tuple[bool, str]:
        pdu: PDUNetio = self.pdus[func_input.pdu_id]
        if func_input.pdu_output_id in pdu.outputs:
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
            return requests.get(addr, auth=authentication), ''
        else:
            return res, comments

    def _send_request(self, pdu_id: int, j_string: Dict[Union[int, str], Union[str, int]]) -> Tuple[Union[bool, requests.Response], str]:
        res, comments = self._check_device_range(device_id=pdu_id)
        if res:
            pdu: PDUNetio = self.pdus[pdu_id]
            addr = f'http://{pdu.ip_address}/netio.json'
            authentication = pdu.authentication
            return requests.post(addr, json=j_string, auth=authentication), ''
        else:
            return res, comments

    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        res, comment = super()._set_parameters_after_connect()
        results, comments_ = [res], comment
        a = self._set_friendly_names()
        results.append(a[0])
        if a[1]:
            comments_ = f'{comments_}. {a[1]}'
        return all(results), comments_

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
                    pdu.outputs = outputs
                else:
                    results.append(False)
                    comments = join_smart_comments(comments, com)

        return all(results), comments



