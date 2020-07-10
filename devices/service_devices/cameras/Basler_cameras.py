"""
Controllers of Basler cameras are described here

created
"""
from devices.service_devices.cameras.camera_controller import CameraCtrl


class CameraCtrl_Basler(CameraCtrl):
    """
    Works only for GiGE cameras of Basler, usb option is not available
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
