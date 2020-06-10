import logging
from time import sleep
from typing import List, Union, Tuple

from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from datastructures.mes_independent.stpmtr_dataclass import relative, absolute

module_logger = logging.getLogger(__name__)

control = 'control'
observe = 'observe'
info = 'info'


class StpMtrCtrl_emulate(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        return super()._connect(flag)

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_axis_flag(flag)
        if res:
            if self.axes[axis_id].status != 2 or force:
                self.axes[axis_id].status = flag
                res, comments = True, ''
            else:
                res, comments = False, f'Axis id={axis_id}, name={self.axes[axis_id].name} is running, ' \
                                       f'its status cannot be changed. First stop it.'
        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()

    def _check_if_connected(self) -> Tuple[bool, str]:
        return super()._check_if_connected()

    def GUI_bounds(self):
        return {'visual_components': [[('activate'), 'button'], [('move_pos', 'get_pos'), 'text_edit']]}

    def _get_axes_names(self):
        return self._get_axes_names_db()

    def _get_axes_status(self) -> List[int]:
        return self._axes_status

    def _get_number_axes(self) -> int:
        return len(self.axes)

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._axes_limits

    def _get_positions(self) -> List[Union[int, float]]:
        return self._axes_positions

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._axes_preset_values

    def _move_axis_to(self, axis_id: int, pos: Union[float, int], how=absolute) -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis_id, 2)
        if res:
            if pos - self.axes[axis_id].position > 0:
                dir = 1
            else:
                dir = -1
            steps = int(abs(pos - self.axes[axis_id].position))
            interrupted = False
            for i in range(steps):
                if self.axes[axis_id].status == 2:
                    self.axes[axis_id].position = self.axes[axis_id].position + dir
                    sleep(0.1)
                else:
                    res = False
                    comments = f'Movement of Axis with id={axis_id} was interrupted'
                    interrupted = True
                    break
            _, _ = self._change_axis_status(axis_id, 1, force=True)
            StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)
            if not interrupted:
                res, comments = True, f'Movement of Axis with id={axis_id}, name={self.axes[axis_id].name} was finished.'
        return res, comments

    def _set_controller_positions(self, positions: List[Union[int, float]]) -> Tuple[bool, str]:
        return super()._set_controller_positions(positions)

    def _release_hardware(self) -> Tuple[bool, str]:
        super(StpMtrCtrl_emulate, self)._release_hardware()
    