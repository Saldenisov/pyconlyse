from abc import abstractmethod

from tango import DispLevel, DevState
from tango.server import command, device_property
from typing import Union, List

from DeviceServers.General.DS_general import DS_General


class DS_PDU(DS_General):
    """
    bla-bla
    """
    RULES = {'set_channels_states': [DevState.ON, DevState.STANDBY],
             'get_channels_states': [DevState.ON, DevState.STANDBY], **DS_General.RULES
             }
    ip_address = device_property(dtype=str)
    authentication_name = device_property(dtype=str)
    authentication_password = device_property(dtype=str)
    number_outputs = device_property(dtype=str)

    def init_device(self):
        super().init_device()
        self._device_id_internal = -1
        self._outputs = {}
        self._device_id_internal, self._uri = self.find_device()
        if self._device_id_internal >= 0:
            self.info(f"Device {self.device_name()} was found.", True)
            self.set_state(DevState.OFF)
        else:
            self.info(f"Device {self.device_name()} was NOT found.", True)
            self.set_state(DevState.FAULT)

    # @command(doc_in="Reads PDU channels state.", polling_period=500, dtype_out=)
    # def get_channels_states(self):
    #     self.debug_stream(f'Getting PDU channels states of {self.device_name()}.')
    #     state_ok = self.check_func_allowance(self.get_channels_state())
    #     if state_ok == 1:
    #         res = self.get_channels_state_local()
    #         if res != 0:
    #             self.error(f'{res}')
    #     return self._outputs

    @abstractmethod
    def get_channels_state_local(self) -> Union[int, str]:
        pass

    @command(dtype_in=[int], doc_in='Function that changes state of outputs of the PDU.',
             display_level=DispLevel.OPERATOR)
    def set_channels_states(self, outputs: List[int]):
        self.info(f"Setting output channels of device {self.device_name()} to {outputs}.")
        state_ok = self.check_func_allowance(self.set_channels_states)
        if state_ok == 1:
            res = self.set_channels_states_local(outputs)
            if res != 0:
                self.error(f'Setting output channels of device {self.device_name()} was NOT '
                           f'accomplished with success: {res}')

    @abstractmethod
    def set_channels_states_local(self, outputs: List[int]) -> Union[int, str]:
        pass

