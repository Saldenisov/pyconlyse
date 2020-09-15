import logging
from abc import abstractmethod
from functools import lru_cache
from devices.devices import Service
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.datastructures.mes_independent.general import *
from utilities.myfunc import error_logger, info_msg

module_logger = logging.getLogger(__name__)


class CameraController(Service):
    GET_IMAGES = CmdStruct(FuncGetImagesInput, FuncGetImagesOutput, FuncGetImagesPrepared)
    SET_IMAGE_PARAMETERS = CmdStruct(FuncSetImageParametersInput, FuncSetImageParametersOutput)
    SET_SYNC_PARAMETERS = CmdStruct(FuncSetSyncParametersInput, FuncSetImageParametersOutput)
    SET_TRANSPORT_PARAMETERS = CmdStruct(FuncSetTransportParametersInput, FuncSetTransportParametersOutput)
    START_TRACKING = CmdStruct(FuncStartTrackingInput, FuncStartTrackingOutput, FuncStartTrackingPrepared)
    STOP_ACQUISITION = CmdStruct(FuncStopAcquisitionInput, FuncStopAcquisitionOutput)

    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['camera_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, Camera] = HardwareDeviceDict()
        self._images_demanders: Dict[str, Dict[str, ImageDemand]] = {}

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return [*super().available_public_functions(), CameraController.GET_IMAGES,
                CameraController.SET_IMAGE_PARAMETERS, CameraController.SET_SYNC_PARAMETERS,
                CameraController.SET_TRANSPORT_PARAMETERS, CameraController.STOP_ACQUISITION]

    @property
    @abstractmethod
    def cameras(self):
        pass

    @property
    def cameras_essentials(self):
        return {camera_id: camera.short() for camera_id, camera in self._hardware_devices.items()}

    @property
    def _cameras_status(self) -> List[int]:
        return [camera.status for camera in self._hardware_devices.values()]

    @staticmethod
    def _check_status_flag(flag: int):
        flags = [0, 1, 2]  # 0 - closed, 1 - opened, 2 - acquiring
        if flag not in flags:
            return False, f'Wrong flag {flag} was passed. FLAGS={flags}.'
        else:
            return True, ''

    @property
    @lru_cache(maxsize=10)
    def device_id_to_id(self) -> Dict[int, int]:
        return_dict = {}
        for camera_id, camera in self._hardware_devices.items():
            return_dict[camera.device_id] = camera_id
        return return_dict

    @abstractmethod
    def _get_cameras_status(self) -> List[int]:
        pass

    def get_images(self, func_input: FuncGetImagesInput) -> FuncGetImagesPrepared:
        camera_id = func_input.camera_id
        res, comments = self._check_device(camera_id)
        if res:
            camera = self.cameras[camera_id]
            res, comments = self._prepare_camera_reading(camera_id)
        else:
            camera = None
        if res:
            image_demand = ImageDemand(camera_id=camera_id, demander_id=func_input.demander_device_id,
                                       every_n_sec=func_input.every_n_sec, return_images=func_input.return_images,
                                       post_treatment=func_input.post_treatment,
                                       treatment_param=func_input.treatment_param,
                                       history_post_treatment_n=func_input.history_post_treatment_n)
            self._register_image_demander(image_demand)
        return FuncGetImagesPrepared(comments=comments, func_success=True, ready=res, camera=camera)

    @abstractmethod
    def _grabbing(self, image_demander: ImageDemand):
        pass

    @abstractmethod
    def _prepare_camera_reading(self, camera_id: int) -> Tuple[bool, str]:
        return True, ''

    def _register_image_demander(self, image_demand: ImageDemand):
        camera_id = image_demand.camera_id
        demander_id = image_demand.demander_id

        def prepare_thread(camera_id, demander_id) -> Thread:
            return Thread(target=self._grabbing, args=(camera_id, demander_id))

        if demander_id not in self._images_demanders:
            thread = prepare_thread(camera_id, demander_id)
            image_demand.grabbing_thread = thread
            image_demand.grabbing_thread.start()
            self._images_demanders[demander_id] = {camera_id: image_demand}
        else:
            demands = self._images_demanders[demander_id]
            if camera_id not in demands:
                thread = prepare_thread(camera_id, demander_id)
                image_demand.grabbing_thread = thread
                image_demand.grabbing_thread.start()
                self._images_demanders[demander_id][camera_id] = image_demand
            else:
                demand: ImageDemand = self._images_demanders[demander_id][camera_id]
                image_demand.grabbing_thread = demand.grabbing_thread
                self._images_demanders[demander_id][camera_id] = image_demand

    def set_image_parameters(self, func_input: FuncSetImageParametersInput) -> FuncSetImageParametersOutput:
        camera_id = func_input.camera_id
        res, comments = self._check_device(camera_id)
        if res:
            camera = self.cameras[camera_id]
            res, comments = self._set_image_parameters_device(func_input)
        else:
            camera = None
        comments = f'Func "set_image_parameters" is accomplished with success: {res}. {comments}'
        return FuncSetImageParametersOutput(comments=comments, func_success=res, camera=camera)

    @abstractmethod
    def _set_image_parameters_device(self, func_input: FuncSetSyncParametersInput) -> Tuple[bool, str]:
        pass

    def set_sync_parameters(self, func_input: FuncSetSyncParametersInput) -> FuncSetSyncParametersOutput:
        camera_id = func_input.camera_id
        res, comments = self._check_device(camera_id)
        if res:
            camera = self.cameras[camera_id]
            res, comments = self._set_sync_parameters_device(func_input)
        else:
            camera = None
        comments = f'Func "set_sync_parameters" is accomplished with success: {res}. {comments}'
        return FuncSetSyncParametersOutput(comments=comments, func_success=res, camera=camera)

    @abstractmethod
    def _set_sync_parameters_device(self, func_input: FuncSetSyncParametersInput) -> Tuple[bool, str]:
        pass

    def set_transport_parameters(self, func_input: FuncSetTransportParametersInput) -> FuncSetTransportParametersOutput:
        camera_id = func_input.camera_id
        res, comments = self._check_device(camera_id)
        if res:
            camera = self.cameras[camera_id]
            res, comments = self._set_transport_parameters_device(func_input)
        else:
            camera = None
        comments = f'Func "set_transport_parameters" is accomplished with success: {res}. {comments}'
        return FuncSetTransportParametersOutput(comments=comments, func_success=res, camera=camera)

    @abstractmethod
    def _set_transport_parameters_device(self, func_input: FuncSetTransportParametersInput) -> Tuple[bool, str]:
        pass

    def start_tracking(self, func_input: FuncStartTrackingInput) -> FuncStartTrackingPrepared:
        camera_id = func_input.camera_id
        res, comments = self._check_device_range(camera_id)
        if res:
            camera = self.cameras[camera_id]
            res, comments = self._prepare_camera_reading(camera_id)
        else:
            camera = None
        if res:
            self._register_image_demander(camera_id, func_input.demander_device_id, func_input.n_images,
                                          func_input.every_n_sec)
        return FuncStartTrackingPrepared(comments=comments, func_success=True, ready=res, camera=camera)

    def stop_acquisition(self, func_input: FuncStopAcquisitionInput) -> FuncStopAcquisitionOutput:
        camera_id = func_input.camera_id
        res, comments = self._check_device(camera_id)
        if res:
            camera = self.cameras[camera_id]
            res, comments = self._stop_acquisition(camera_id)
        else:
            camera = None
        return FuncStopAcquisitionOutput(comments=comments, func_success=res, camera=camera)

    @abstractmethod
    def _stop_acquisition(self, camera_id: int) -> Tuple[bool, str]:
        pass


class CameraError(BaseException):
    def __init__(self, controller: CameraController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')