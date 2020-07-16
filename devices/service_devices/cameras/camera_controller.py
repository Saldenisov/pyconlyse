import logging
from abc import abstractmethod
from os import path
from pathlib import Path
from typing import Any, Callable

from devices.devices import Service
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.errors.myexceptions import DeviceError
from utilities.myfunc import error_logger, info_msg

module_logger = logging.getLogger(__name__)


class CameraController(Service):
    ACTIVATE_CAMERA = CmdStruct(FuncActivateCameraInput, FuncActivateCameraOutput)
    GET_IMAGES = CmdStruct(FuncGetImagesInput, FuncGetImagesOutput)
    SET_IMAGE_PARAMETERS = CmdStruct(None, None)
    SET_SYNC_PARAMETERS = CmdStruct(None, None)
    SET_TRANSPORT_PARAMETERS = CmdStruct(None, None)
    SET_ALL_PARAMETERS = CmdStruct(None, None)
    STOP_ACQUISITION = CmdStruct(None, None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        pass

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return [*super().available_public_functions(), CameraController.ACTIVATE_CAMERA, CameraController.GET_IMAGES,
                CameraController.STOP_ACQUISITION]

    def description(self) -> Desription:
        """
        Description with important parameters
        :return: CameraDescription with parameters essential for understanding what this device is used for
        """
        try:
            parameters = self.get_settings('Parameters')
            return CameraDescription(cameras=self.cameras, info=parameters['info'], GUI_title=parameters['title'])
        except (KeyError, DeviceError) as e:
            return CameraError(self, f'Could not set description of controller in the database: {e}')

    def get_controller_state(self, func_input: FuncGetControllerStateInput) -> FuncGetControllerStateOutput:
        """
        State of controller is returned
        :return:  FuncOutput
        """
        comments = f'Controller is {self.device_status.active}. Power is {self.device_status.power}. ' \
                   f'Axes are {self._axes_status}'
        try:
            return FuncGetCameraControllerStateOutput(cameras=self.cameras, device_status=self.device_status,
                                                      comments=comments, func_success=True)
        except KeyError:
            return FuncGetCameraControllerStateOutput(cameras=self.cameras, device_status=self.device_status,
                                                      comments=comments, func_success=True)


class CameraError(BaseException):
    def __init__(self, controller: CameraController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')