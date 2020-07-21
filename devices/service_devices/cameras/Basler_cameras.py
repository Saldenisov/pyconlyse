"""
Controllers of Basler cameras are described here

created
"""
from typing import Tuple, List
from distutils.util import strtobool
from devices.service_devices.cameras.camera_controller import CameraController, CameraError
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.myfunc import error_logger, info_msg


class CameraCtrl_Basler(CameraController):
    """
    Works only for GiGE cameras of Basler, usb option is not available
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _get_cameras_status(self) -> List[int]:
        pass

    def _get_number_cameras(self):
        pass

    def _stop_acquisition(self, camera_id: int):
        pass

    def _check_if_active(self) -> Tuple[bool, str]:
        pass

    def _check_if_connected(self) -> Tuple[bool, str]:
        pass

    def _set_private_parameters_db(self):
        self._set_transport_layer_db()
        self._set_analog_controls_db()
        self._set_aoi_controls_db()
        self._set_acquisition_controls_db()
        self._set_image_format_db()

    def _set_analog_controls_db(self):
        obligation_keys = set(Analog_Controls.__annotations__.keys())
        try:
            analog_controls = self.get_settings('Analog_Controls')
            if set(analog_controls.keys()).intersection(obligation_keys) != obligation_keys:
                raise KeyError
            else:
                # Init Analog_Controls for all cameras
                for camera_key, camera in self.cameras.items():
                    camera.parameters['Analog_Controls'] = Analog_Controls()

            for analog_key, analog_value in analog_controls.items():
                if analog_key in obligation_keys:
                    try:
                        analog_value = eval(analog_value)
                    except SyntaxError:
                        pass
                    if isinstance(analog_value, dict):
                        dict_opt = True
                    else:
                        dict_opt = False

                    for camera_key, camera in self.cameras.items():
                        try:
                            value = analog_value if not dict_opt else analog_value[camera.device_id]
                            t = Analog_Controls.__annotations__[analog_key]
                            if t == bool and isinstance(value, str):
                                value = strtobool(value)
                            value = t(value)
                            setattr(camera.parameters['Analog_Controls'], analog_key, value)
                        except KeyError:
                            raise KeyError(f'Not all cameras ids are passed to Analog_controls attribute {analog_key}.')
                        except ValueError:
                            raise ValueError(f'Cannot convert Analog_controls attribute {value} to correct type '
                                             f'{Analog_Controls.__annotations__[analog_key]}.')

                else:
                    info_msg(self, 'INFO', f'Unknown parameter {analog_key} in Analog_Controls settings. Passing by.')

        except (KeyError, ValueError) as e:
            error_logger(self, self._set_analog_controls_db, e)
            raise CameraError(self, f'Check DB for Analog_Controls: {list(obligation_keys)}. {e}')

    def _set_acquisition_controls_db(self):
        pass

    def _set_aoi_controls_db(self):
        pass

    def _set_image_format_db(self):
        pass

    def _set_transport_layer_db(self):
        pass
