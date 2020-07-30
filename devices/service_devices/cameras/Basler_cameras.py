"""
Controllers of Basler cameras are described here

created
"""
from dataclasses import asdict
from distutils.util import strtobool
from pypylon import pylon, genicam

from devices.service_devices.cameras.camera_controller import CameraController, CameraError
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.myfunc import error_logger, info_msg


class CameraCtrl_Basler(CameraController):
    """
    Works only for GiGE cameras of Basler, usb option is not available
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tl_factory = None

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        if self.device_status.power:
            if flag:
                res, comments = self._form_devices_list()
            else:
                res, comments = self._release_hardware()
            self.device_status.connected = flag
        else:
            res, comments = False, f'Power is off, connect to controller function cannot be called with flag {flag}'

        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        return super(CameraCtrl_Basler, self)._check_if_active()

    def _check_if_connected(self) -> Tuple[bool, str]:
        pass

    @property
    def cameras(self):
        return self.cameras_no_pylon

    @property
    def cameras_no_pylon(self):
        cameras = {}
        for camera_id, camera in self._cameras.items():
            cameras[camera_id] = camera.no_pylon()
        return cameras

    def _change_camera_status(self, camera_id: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_camera_flag(flag)
        if res:
            camera = self._cameras[camera_id]
            if camera.status != flag:
                info = ''
                if camera.status == 2 and force:
                    self._stop_acquisition(camera_id)
                    info = f'Camera id={camera_id}, name={camera.friendly_name} was stopped.'
                    camera.status = flag
                    res, comments = True, f'Camera id={camera_id}, name={camera.friendly_name} is set to {flag}.' + info
                elif camera.status == 2 and not force:
                    res, comments = False, f'Camera id={camera_id}, name={camera.friendly_name} is acquiring. ' \
                                           'Force Stop in order to change status.'
                elif flag in [0, 1]:
                    try:
                        if flag == 1:
                            camera.pylon_camera.Open()
                        else:
                            camera.pylon_camera.Close()
                        camera.status = flag
                        res, comments = True, f'Camera id={camera_id}, name={camera.friendly_name} is set to {flag}.' \
                                        + info
                    except pylon.GenericException as e:
                        comments = f'Tried to open connection, but failed: {e}'
                        error_logger(self, self._change_camera_status, comments)
                        return False, comments
            else:
                res, comments = True, f'Camera id={camera_id}, name={camera.friendly_name} is already set to {flag}'
        return res, comments

    def _form_devices_list(self) -> Tuple[bool, str]:
        # Init all camera
        try:
            # Get the transport layer factory.
            self.tl_factory = pylon.TlFactory.GetInstance()
            # Get all attached devices and exit application if no device is found.
            pylon_devices: Tuple[pylon.DeviceInfo] = self.tl_factory.EnumerateDevices()
            if len(pylon_devices) == 0:
                return False, "No cameras present."
            elif len(pylon_devices) != self._cameras_number:
                error_logger(self, self._form_devices_list, f'Not all cameras listed in DB are present.')

            # Create an array of instant cameras for the found devices and avoid exceeding a maximum number of devices.
            self.pylon_cameras: pylon.InstantCameraArray = pylon.InstantCameraArray(min(len(pylon_devices),
                                                                                        self._cameras_number))

            device_id_camera_id = self.device_id_to_id
            keep_camera = []

            for i, pylon_camera in enumerate(self.pylon_cameras):
                pylon_camera.Attach(self.tl_factory.CreateDevice(pylon_devices[i]))
                try:
                    device_id = int(pylon_camera.GetDeviceInfo().GetSerialNumber())
                except ValueError:
                    return False, f'Camera id {pylon_camera.GetDeviceInfo().GetSerialNumber()} ' \
                                  f'was not correctly converted to integer value.'

                if device_id in device_id_camera_id:
                    self._cameras[device_id_camera_id[device_id]].pylon_camera = pylon_camera
                    self._cameras[device_id_camera_id[device_id]].pylon_camera.Open()
                    self._cameras[device_id_camera_id[device_id]].status = 1

                    # Setting Parameters for the cameras
                    res, comments = self._set_parameters_camera(device_id_camera_id[device_id])
                    if res:
                        keep_camera.append(device_id)
                    else:
                        error_logger(self, self._form_devices_list, f'Parameters for camera with id {device_id} were '
                                                                    f'not set: {comments}. Skipping camera.')
                else:
                    info_msg(self, 'INFO', f'Camera with id: {device_id} is not known. Skipping its initialization.')

            # Deleting those cameras read from DB which were not found by controller.
            for device_id, camera_id in device_id_camera_id.items():
                if device_id not in keep_camera:
                    del self._cameras[camera_id]
            return True, ''
        except (genicam.GenericException, ValueError) as e:
            return False, f"An exception occurred. {e}"

    def _get_cameras_status(self) -> List[int]:
        a = {}
        device_id_camera_id = self.device_id_to_id
        for camera_id, pylon_camera in enumerate(self.pylon_cameras):
            device_id = int(pylon_camera.GetDeviceInfo().GetSerialNumber())
            if pylon_camera.IsOpen():
                a[device_id_camera_id[device_id]] = 1
            else:
                a[device_id_camera_id[device_id]] = 0
        b = list([value for _, value in a.items()])
        return b

    def _get_number_cameras(self):
        if not self.tl_factory:
            self.tl_factory = pylon.TlFactory.GetInstance()
        pylon_devices: Tuple[pylon.DeviceInfo] = self.tl_factory.EnumerateDevices()
        return len(pylon_devices)

    def _stop_acquisition(self, camera_id: int):
        pass

    def _set_private_parameters_db(self):
        self._set_transport_layer_db()
        self._set_analog_controls_db()
        self._set_aoi_controls_db()
        self._set_acquisition_controls_db()
        self._set_image_format_db()

    def _set_analog_controls_db(self):
        self._set_db_attribite(Analog_Controls, self._set_analog_controls_db)

    def _set_acquisition_controls_db(self):
        self._set_db_attribite(Acquisition_Controls, self._set_analog_controls_db)

    def _set_aoi_controls_db(self):
        self._set_db_attribite(AOI_Controls, self._set_analog_controls_db)

    def _set_image_format_db(self):
        self._set_db_attribite(Image_Format_Control, self._set_analog_controls_db)

    def _set_parameters_camera(self, camera_id: int) -> Tuple[bool, str]:
        device_id: int = self._cameras[camera_id].device_id
        camera = self._cameras[camera_id]
        pylon_camera: pylon.InstantCamera = camera.pylon_camera
        # Setting Friendly name
        try:
            try:
                friendly_name = eval(self.get_parameters['friendly_names'])[device_id]
            except (KeyError, ValueError, SyntaxError):
                friendly_name = str(device_id)

            pylon_camera.GetDeviceInfo().SetFriendlyName(friendly_name.format('utf-8'))
            camera.friendly_name = friendly_name

            parameters_groups = ['Transport_Layer',
                                 'Analog_Controls',
                                 'AOI_Controls',
                                 'Acquisition_Controls',
                                 'Image_Format_Control']
            for parameters_group_name in parameters_groups:
                if parameters_group_name not in camera.parameters:
                    return False, f'Parameters group "{parameters_group_name}" is absent in DB.'
                else:
                    try:
                        for param_name, param_value in asdict(camera.parameters[parameters_group_name]).items():
                            setattr(camera.pylon_camera, param_name, param_value)
                    except (genicam.GenericException, Exception) as e:
                        raise CameraError(self, text=f'Error appeared: {e} when setting parameter "{param_name}" for '
                                                     f'camera with id {device_id}')
            return True, ''

        except (genicam.GenericException, CameraError) as e:
            return False, f'Error appeared when camera id {device_id} was initializing: {e}.'

    def _set_transport_layer_db(self):
        self._set_db_attribite(Transport_Layer, self._set_analog_controls_db)

    def _set_db_attribite(self, dataclass, func):
        obligation_keys = set(dataclass.__annotations__.keys())
        attribute_name = dataclass.__name__
        try:
            analog_controls = self.get_settings(attribute_name)
            if set(analog_controls.keys()).intersection(obligation_keys) != obligation_keys:
                raise KeyError
            else:
                # Init Analog_Controls for all cameras
                for camera_key, camera in self._cameras.items():
                    camera.parameters[attribute_name] = dataclass()

            for analog_key, analog_value in analog_controls.items():
                if analog_key in obligation_keys:
                    try:
                        analog_value = eval(analog_value)
                    except (SyntaxError, NameError):
                        pass
                    if isinstance(analog_value, dict):
                        dict_opt = True
                    else:
                        dict_opt = False

                    for camera_key, camera in self._cameras.items():
                        try:
                            value = analog_value if not dict_opt else analog_value[camera.device_id]
                            t = dataclass.__annotations__[analog_key]
                            if t == bool and isinstance(value, str):
                                value = strtobool(value)
                            value = t(value)
                            setattr(camera.parameters[attribute_name], analog_key, value)
                        except KeyError:
                            raise KeyError(f'Not all cameras ids are passed to {attribute_name} attribute {analog_key}.')
                        except ValueError:
                            raise ValueError(f'Cannot convert {attribute_name} attribute {value} to correct type '
                                             f'{dataclass.__annotations__[analog_key]}.')

                else:
                    info_msg(self, 'INFO', f'Unknown parameter {analog_key} in {attribute_name} settings. Passing by.')

        except (KeyError, ValueError) as e:
            error_logger(self, func, e)
            raise CameraError(self, f'Check DB for {attribute_name}: {list(obligation_keys)}. {e}')

    def _release_hardware(self) -> Tuple[bool, str]:
        # TODO: make it work
        try:
            device_id_camera_id = self.device_id_to_id
            for camera_id, pylon_camera in enumerate(self.pylon_cameras):
                device_id = int(pylon_camera.GetDeviceInfo().GetSerialNumber())
                if pylon_camera.IsOpen():
                    pylon_camera.Close()
                    self._cameras[device_id_camera_id[device_id]].status = 0
                self._cameras[device_id_camera_id[device_id]].pylon_camera = None
                return True, ''
        except (genicam.GenericException, Exception) as e:
            error_logger(self, self._release_hardware, e)
            return False, f'Release_hardware function did not work: {e}.'


