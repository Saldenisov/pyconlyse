import logging
from time import sleep
from typing import List, Union, Tuple, Dict, Set

from devices.service_devices.stepmotors.stpmtr_dataclass import EmulateAxisStpMtr, absolute
from devices.devices_dataclass import HardwareDeviceDict, HardwareDevice
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)

control = 'control'
observe = 'observe'
info = 'info'


class StpMtrCtrl_emulate(StpMtrController):

    def __init__(self, **kwargs):
        kwargs['stpmtr_dataclass'] = EmulateAxisStpMtr
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, EmulateAxisStpMtr] = HardwareDeviceDict()

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        return super()._connect(flag)

    def _change_device_status_local(self, device: HardwareDevice, flag: int, force=False) -> Tuple[bool, str]:
        return True, ''

    def _form_devices_list(self) -> Tuple[bool, str]:
        return True, ''

    def _get_number_hardware_devices(self) -> int:
        return 4

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()

    def _get_position_axis(self, device_id: Union[int, str]) -> Tuple[bool, str]:
        return True, ''

    def _set_move_parameters_axes(self, must_have_param: Dict[int, Set[str]] = None):
        pass

    def _set_pos_axis(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        pass

    def _check_if_connected(self) -> Tuple[bool, str]:
        return super()._check_if_connected()

    def GUI_bounds(self):
        return {'visual_components': [[('activate'), 'button'], [('move_pos', 'get_pos'), 'text_edit']]}

    def _get_axes_names(self):
        return self._get_axes_names_db()

    def _get_axes_status(self) -> List[int]:
        return self._axes_status

    def _get_number_axes(self) -> int:
        return len(self.axes_stpmtr)

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._axes_limits

    def _get_positions(self) -> List[Union[int, float]]:
        return self._axes_positions

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._axes_preset_values

    def _move_axis_to(self, axis_id: int, go_pos: Union[float, int], how=absolute) -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis_id, 2)
        if res:
            if go_pos - self.axes_stpmtr[axis_id].position > 0:
                dir = 1
            else:
                dir = -1
            steps = int(abs(go_pos - self.axes_stpmtr[axis_id].position))
            interrupted = False
            for i in range(steps):
                if self.axes_stpmtr[axis_id].status == 2:
                    self.axes_stpmtr[axis_id].position = self.axes_stpmtr[axis_id].position + dir
                    sleep(0.1)
                else:
                    res = False
                    comments = f'Movement of Axis with id={axis_id} was interrupted'
                    interrupted = True
                    break
            _, _ = self._change_axis_status(axis_id, 1, force=True)
            StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)
            if not interrupted:
                res, comments = True, f'Movement of Axis with id={axis_id}, name={self.axes_stpmtr[axis_id].name} was finished.'
        return res, comments

    def _set_pos(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        self.axes_stpmtr[axis_id].position = pos
        return True, ''

    def _release_hardware(self) -> Tuple[bool, str]:
        super(StpMtrCtrl_emulate, self)._release_hardware()