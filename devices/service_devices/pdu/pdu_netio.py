""""
saldenisov
created: 12/08/2020
"""

import requests

from devices.service_devices.pdu.pdu_controller import PDUController, PDUError
from utilities.datastructures.mes_independent.pdu_dataclass import *
from utilities.myfunc import error_logger, info_msg


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

    def _change_pdu_status(self, pdu_id: Union[int, str], flag: int, force=False) -> Tuple[bool, str]:
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
            res, com = self._send_request(pdu_id, {"Outputs": []})
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
        pass

    @property
    def pdus(self) -> Dict[Union[int, str], PDUNetio]:
        return super().pdus

    def _release_hardware(self) -> Tuple[bool, str]:
        for pdu in self.pdus.values():
            pdu.status = 0

    def _set_friendly_names(self):
        for pdu in self.pdus.values():
            pdu.friendly_name = pdu.name

    def _set_mac_addresses(self):
        for pdu_id, pdu in self.pdus.items():
            res, com =self._send_request(pdu_id, {"Outputs": []})
            if isinstance(res, requests.Response):
                if res.status_code == 200:
                    pdu.mac_address = res.json()['Agent']['MAC']

    def _send_request(self, pdu_id: int, j_string: dict) -> Tuple[Union[bool, requests.Response], str]:
        res, comments = self._check_device_range()
        if res:
            pdu: PDUNetio = self.pdus[pdu_id]
            return requests.post(f'http://{pdu.ip_address}/netio.json', json=j_string, auth=pdu.authentication), ''
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



