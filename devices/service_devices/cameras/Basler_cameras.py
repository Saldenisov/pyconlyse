"""
Controllers of Basler cameras are described here

created
"""
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

    def _form_devices_list(self) -> Tuple[bool, str]:
        # Init all camera
        try:
            # Get the transport layer factory.
            tlFactory = pylon.TlFactory.GetInstance()

            # Get all attached devices and exit application if no device is found.
            pylon_devices: Tuple[pylon.DeviceInfo] = tlFactory.EnumerateDevices()
            if len(pylon_devices) == 0:
                return False, "No cameras present."

            # Create an array of instant cameras for the found devices and avoid exceeding a maximum number of devices.
            pylon_cameras: pylon.InstantCameraArray = pylon.InstantCameraArray(min(len(pylon_devices), self._cameras_number))

            device_id_camera_id = self.device_id_to_id
            for i, pylon_camera in enumerate(pylon_cameras):
                pylon_camera.Attach(tlFactory.CreateDevice(pylon_devices[i]))
                pylon_camera.Open()
                device_id = int(pylon_camera.GetDeviceInfo().GetSerialNumber())
                self.cameras[device_id_camera_id[device_id]].pylon_camera = pylon_camera

            return True, ''
        except (genicam.GenericException, ValueError) as e:
            return False, f"An exception occurred. {e}"

    def _get_cameras_status(self) -> List[int]:
        pass

    def _get_number_cameras(self):
        pass

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
                for camera_key, camera in self.cameras.items():
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

                    for camera_key, camera in self.cameras.items():
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
        pass

