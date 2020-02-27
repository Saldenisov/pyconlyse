import logging
from time import sleep
from typing import Dict, Union, Any, List, Tuple

from devices.realdevices.stepmotors.stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)

control = 'control'
observe = 'observe'
info = 'info'


class StpMtrCtrl_emulate(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        return super()._connect(flag)

    def _change_axis_status(self, axis: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_axis_flag(flag)
        if res:
            if self._axes_status[axis] != 2 or force:
                self._axes_status[axis] = flag
                res, comments = True, ''
            else:
                res, comments = False, f'axis {axis} is running, its status cannot be changed'
        return res, comments

    def GUI_bounds(self):
        return {'visual_components': [[('activate'), 'button'], [('move_pos', 'get_pos'), 'text_edit']]}

    def _get_axes_status(self) -> List[int]:
        if self._axes_status:
            return self._axes_status
        else:
            return [0] * self._axes_number

    def _get_number_axes(self) -> int:
        return 4

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return [(0.0, 100.0), (-100.0, 100.0), (0.0, 360), (0.0, 360)]

    def _get_pos(self) -> List[Union[int, float]]:
        if self._pos:
            return self._pos
        else:
            return [0] * self._axes_number

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return [(0, 91),
                (0, 50),
                (0, 45, 90, 135, 180, 225, 270, 315, 360),
                (0, 45, 90, 135, 180, 225, 270, 315, 360)]

    def _move_axis_to(self, axis: int, pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis, 2)
        if res:
            if pos - self._pos[axis] > 0:
                dir = 1
            else:
                dir = -1
            steps = int(abs(pos - self._pos[axis]))
            for i in range(steps):
                if self._axes_status[axis] == 2:
                    self._pos[axis] = self._pos[axis] + dir
                    sleep(0.1)
                else:
                    comments = 'movement was interrupted'
                    break
            _, _ = self._change_axis_status(axis, 1, force=True)
            StpMtrController._write_to_file(str(self._pos), self._file_pos)
            res, comments = True, ''
        return res, comments
