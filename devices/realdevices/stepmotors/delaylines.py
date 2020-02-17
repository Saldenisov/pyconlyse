import logging
from time import sleep
from typing import Dict, Union, Any, List, Tuple

from devices.realdevices.stepmotors.stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)

control = 'control'
observe = 'observe'
info = 'info'


class StpMtrCtrl_emulate(StpMtrController):
    # TODO  ranges, preset values must be set
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _activate_axis(self, axis: int, flag: int):
        return self._change_axis_status(axis, flag)

    def description(self):
        desc = {'GUI_title': """StpMtrCtrl_emulate service, 4 axes""",
                'axes_names': ['0/90 mirror', 'iris', 'filter wheel 1', 'filter wheel 2'],
                'axes_values': [0, 3],
                'ranges': [((0.0, 100.0), (0, 91)),
                           ((-100.0, 100.0), (0, 50)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360)),
                           ((0.0, 360.0), (0, 45, 90, 135, 180, 225, 270, 315, 360))],
                'info': "StpMtrCtrl_emulate controller, it emulates stepmotor controller with 4 axes"}
        return desc

    def GUI_bounds(self):
        return {'visual_components': [[('activate'), 'button'], [('move_pos', 'get_pos'), 'text_edit']]}

    def _change_axis_status(self, axis: int, flag: int, force=False) -> Tuple[bool, str]:
        return super()._change_axis_status(axis, flag, force)

    def _connect_controller(self, flag: bool) -> Tuple[bool, str]:
        return super()._connect_controller(flag)

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
            return True, comments
        else:
            return False, comments

    def _stop_axis(self, axis) -> Tuple[bool, str]:
        return self._change_axis_status(axis, 1, force=True)

    def _shutdown(self):
        return super()._shutdown()


