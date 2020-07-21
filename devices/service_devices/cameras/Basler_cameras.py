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
