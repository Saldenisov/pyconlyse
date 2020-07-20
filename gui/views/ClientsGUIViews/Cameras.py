"""
Created on 16.07.2020

@author: saldenisov
"""
import copy
import logging
from _functools import partial

from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QErrorMessage

from communication.messaging.messages import MsgComExt, MsgComInt, MessageInt
from devices.devices import Device
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from gui.views.ui import Ui_CameraWidget
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.myfunc import info_msg, get_local_ip, error_logger

module_logger = logging.getLogger(__name__)


class StepMotorsView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: Desription, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.controller_status = CamerasCtrlStatusMultiCameras()

        self.name = f'CamerasClient:view: {service_parameters.device_id} {get_local_ip()}'
        self.logger = logging.getLogger("Cameras." + __name__)
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device: Device = self.model.superuser
        self.service_parameters: DeviceInfoExt = service_parameters

        self.ui = Ui_CameraWidget
        self.ui.setupUi(self, service_parameters)