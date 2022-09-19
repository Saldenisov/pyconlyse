from abc import abstractmethod
import zlib
import numpy as np
from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, List, Dict, Any
from data_classes import *
from DeviceServers.General.DS_general import DS_General, GeneralOrderInfo
from utilities.myfunc import ping
from dataclasses import dataclass
from enum import Enum
from data_classes import *



class DS_Experiment(DS_General):
    """
    Gives control to pulse and 3P epxeriment
    """
    RULES = {
             **DS_General.RULES}

    _version_ = '0.1'
    _model_ = 'Experiment ds'
    polling = 500

    authentication_name = device_property(dtype=str, default_value='admin')
    authentication_password = device_property(dtype=str, default_value='admin')
    parameters = device_property(dtype=str, default_value={})

    def init_device(self):
        super().init_device()
        self.turn_on()

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def find_device(self):
        arg_return = -1, ''
        self.info(f"Searching for Experiment device {self.device_name}", True)
        self._device_id_internal, self._uri = self.device_id, self.friendly_name.encode('utf-8')

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

    @command(dtype_in=str, dtype_out=str, doc_in="Receives str of Dict{'email': value, 'password_hash': value}",
             doc_out="Dict{'name': value, 'surname': value, success: bool}")
    def login(self, input: str):
        pass

    @attribute(label="List of Available detections", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Gives {'ANDOR_CCD': 'manip/cr/andor_ccd1'}")
    def available_detection(self):
        return str(self.parameters['available_detection'])

    @attribute(label="List of cells holders with positions", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ,
               doc="Gives {'5mm': [0, 12.9, 25.8, 38.7, 51.6, 64.5, 80], '10mm': [18, 80]...}")
    def available_cell_holders(self):
        return str(self.parameters['available_cell_holders'])

    @attribute(label="List of Detection settings", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Gives {'BG': 50000, 'pulse_difference': 10}")
    def detection_settings(self):
        return str(self.parameters['detection_settings'])

    @attribute(label="Exp Type", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="class ExpType(Enum): PP = 1  # Pump-probe PPP1 = 2  # Simple 3P experiment STREAK = 3 PPP2 = 4  # Complex 3P experiment")
    def exp_type(self):
        return str(ExpType(self.id))

    @attribute(label="List of translation stages", dtype=str, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ,
               doc="Gives 'samples': 'manip/general/ds_owis_ps90/2','SC_delay': 'manip/general/ds_owis_ps90/1'}")
    def translation_stages(self):
        return str(self.parameters['translation_stages'])

    @command(dtype_in=str, dtype_out=str, doc_in="Receives str ProjectDescription}",
             doc_out="Sends str of List[projects names] available")
    def create_project(self, value):
        self.write_project_info(value)
        return self.projects_available()

    @command(dtype_in=str, dtype_out=str, doc_in="Receives str of Dict{'project_name': str,  'password': str}",
             doc_out="Sends str of Dict{'project_name': str}")
    def delete_project(self, value):
        pass

    @command(dtype_in=str, dtype_out=str, doc_in="Receives str ProjectDescription}",
             doc_out="Sends str of List[projects names] available")
    def update_project(self, value):
        self.write_project_info(value)
        return self.projects_available()

    @command(dtype_in=str, dtype_out=str, doc_in="compressed with zlib str of Measurement",
             doc_out="list of measurement in the project")
    def write_data_project(self, data_arrived: str):
        data: Measurement = eval(data_arrived)

        return self.measurements_available(data.project_name)

    def write_project_info(self, info: ProjectDescription):
        pass

    def projects_available(self) -> List[str]:
        pass

    def measurements_available(self, project_name: str) -> List[str]:
        pass

if __name__ == "__main__":
    DS_Experiment.run_server()
