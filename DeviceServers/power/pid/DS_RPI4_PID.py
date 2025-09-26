#!/usr/bin/python3 -u
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Union

from DeviceServers.General.DS_PID import DS_PID

# -----------------------------


class DS_RPI4_PID(DS_PID):
    _version_ = "0.1"
    _model_ = "RPI4 PID MAX31865"

    def find_device(self):
        pass

    def get_controller_status_local(self) -> Union[int, str]:
        pass

    def turn_on_local(self) -> Union[int, str]:
        pass

    def turn_off_local(self) -> Union[int, str]:
        pass

    def read_temperature_local(self):
        pass

    def pid_action_local(self):
        pass


if __name__ == "__main__":
    DS_RPI4_PID.run_server()


