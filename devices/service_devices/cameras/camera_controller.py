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
    STOP_ACQUISITION = CmdStruct(FuncStopAcquisitionInput, FuncStopAcquisitionOutput)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cameras: Dict[int, Camera] = dict()

        res, comments = self._set_parameters()  # Set parameters from database first and after connection is done update
                                                # from hardware controller if possible
        if not res:
            raise CameraError(self, comments)

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        res, comments = self._check_if_active()
        if res ^ flag:  # res XOR Flag
            if flag:
                res, comments = self._connect(flag)  # guarantees that parameters could be read from controller
                if res:  # parameters should be set from hardware controller if possible
                    res, comments = self._set_parameters()  # This must be realized for all controllers
                    if res:
                        self.device_status.active = True
            else:
                res, comments = self._connect(False)
                if res:
                    self.device_status.active = flag
        info = f'{self.id}:{self.name} active state is {self.device_status.active}. {comments}'
        info_msg(self, 'INFO', info)
        return FuncActivateOutput(comments=info, device_status=self.device_status, func_success=res)

    def activate_camera(self, func_input: FuncActivateCameraInput) -> FuncActivateCameraOutput:
        camera_id = func_input.camera_id
        flag = func_input.flag
        res, comments = self._check_axis_range(camera_id)
        if res:
            res, comments = self._check_controller_activity()
        if res:
            res, comments = self._change_axis_status(camera_id, flag)
        essentials = self.cameras_essentials
        status = []
        for key, camera in essentials.items():
            status.append(essentials[key].status)
        info = f'Cameras status: {status}. {comments}'
        info_msg(self, 'INFO', info)
        return FuncActivateCameraOutput(cameras=self.cameras_essentials, comments=info, func_success=res)

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return [*super().available_public_functions(), CameraController.ACTIVATE_CAMERA, CameraController.GET_IMAGES,
                CameraController.STOP_ACQUISITION]

    @property
    def cameras_essentials(self):
        essentials = {}
        for camera_id, camera in self.cameras.items():
            essentials[camera_id] = camera.short()
        return essentials

    @property
    def _cameras_status(self) -> List[int]:
        return [camera.status for camera in self.cameras.values()]

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

    @abstractmethod
    def _get_cameras_status(self) -> List[int]:
        pass

    def _get_cameras_status_db(self) -> List[int]:
        return [0] * self._cameras_number

    def get_controller_state(self, func_input: FuncGetControllerStateInput) -> FuncGetControllerStateOutput:
        """
        State of controller is returned
        :return:  FuncOutput
        """
        comments = f'Controller is {self.device_status.active}. Power is {self.device_status.power}. ' \
                   f'Cameras are {self._cameras_status}'
        try:
            return FuncGetCameraControllerStateOutput(cameras=self.cameras, device_status=self.device_status,
                                                      comments=comments, func_success=True)
        except KeyError:
            return FuncGetCameraControllerStateOutput(cameras=self.cameras, device_status=self.device_status,
                                                      comments=comments, func_success=True)

    def _get_cameras_ids_db(self):
        try:
            ids: List[int] = []
            ids_s: List[str] = self.get_parameters['cameras_ids'].replace(" ", "").split(';')
            for exp in ids_s:
                val = eval(exp)
                if not isinstance(val, int):
                    raise TypeError()
                ids.append(val)
            if len(ids) != self._cameras_number:
                raise CameraError(self, f'Number of cameras_ids {len(ids)} is not equal to '
                                        f'cameras_number {self._cameras_number}.')
            return ids
        except KeyError:
            try:
                cameras_number = int(self.get_parameters['cameras_number'])
                return list([camera_id for camera_id in range(1, cameras_number + 1)])
            except (KeyError, ValueError):
                raise CameraError(self, text="Cameras ids could not be set, cameras_ids or cameras_number fields is absent "
                                             "in the database.")
        except (TypeError, SyntaxError):
            raise CameraError(self, text="Check cameras_ids field in database, must be integer.")

    def _get_cameras_names_db(self):
        try:
            names: List[int] = []
            names_s: List[str] = self.get_parameters['cameras_names'].replace(" ", "").split(';')
            for exp in names_s:
                val = exp
                if not isinstance(val, str):
                    raise TypeError()
                names.append(val)
            if len(names) != self._cameras_number:
                raise CameraError(self, f'Number of cameras_names {len(names)} is not equal to '
                                        f'cameras_number {self._cameras_number}.')
            return names
        except KeyError:
            raise CameraError(self, text="Cameras names could not be set, cameras_names field is absent in the database.")
        except (TypeError, SyntaxError):
            raise CameraError(self, text="Check cameras_names field in database.")

    @abstractmethod
    def _get_number_cameras(self):
        pass

    def _get_number_cameras_db(self):
        try:
            return int(self.get_parameters['cameras_number'])
        except KeyError:
            raise CameraError(self, text="Cameras_number could not be set, cameras_number field is absent "
                                              "in the database")
        except (ValueError, SyntaxError):
            raise CameraError(self, text="Check cameras number in database, must be cameras_number = number")

    def _set_number_cameras(self):
        if self.device_status.connected:
            self._cameras_number = self._get_number_cameras()
        else:
            self._cameras_number = self._get_number_cameras_db()

    def _set_names_cameras(self):
        if not self.device_status.connected:
            names = self._get_cameras_names_db()
            for id, name in zip(self.cameras.keys(), names):
                self.cameras[id].name = name
                self.cameras[id].friendly_name = name

    def _set_ids_cameras(self):
        if not self.device_status.connected:
            ids = self._get_cameras_ids_db()
            i = 1
            for id_a in ids:
                self.cameras[i] = Camera(device_id=id_a)
                i += 1

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        try:
            self._set_number_cameras()
            self._set_ids_cameras()  # Ids must be set first
            self._set_names_cameras()
            self._set_private_parameters_db()
            self._set_status_cameras()
            res = []
            if extra_func:
                comments = ''
                for func in extra_func:
                    r, com = func()
                    res.append(r)
                    comments = comments + com

            if self.device_status.connected:
                self._parameters_set_hardware = True
            if all(res):
                return True, ''
            else:
                raise CameraError(self, comments)
        except CameraError as e:
            error_logger(self, self._set_parameters, e)
            return False, str(e)

    @abstractmethod
    def _set_private_parameters_db(self):
        pass


    def _set_status_cameras(self):
        if self.device_status.connected:
            statuses = self._get_cameras_status()
        else:
            statuses = self._get_cameras_status_db()

        for id, status in zip(self.cameras.keys(), statuses):
            self.cameras[id].status = status

    @abstractmethod
    def _stop_acquisition(self, camera_id: int):
        pass


class CameraError(BaseException):
    def __init__(self, controller: CameraController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')