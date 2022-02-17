import sys
import simple_pid as spid
from pathlib import Path
from typing import Union, List
from collections import OrderedDict as od
from tango.server import Device, attribute, command, pipe, device_property
from time import sleep, monotonic
from threading import Thread
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from tango import DevState


try:
    from DeviceServers.General.DS_Control import DS_ControlPosition
except ModuleNotFoundError:
    from General.DS_Control import DS_ControlPostion


class DS_LaserPointing(DS_ControlPosition):
    RULES = {'set_param_after_init': [DevState.ON], 'start_grabbing': [DevState.ON],
             'stop_grabbing': [DevState.ON],
             **DS_ControlPosition.RULES}
    """
    Device Server (Tango) which controls laser pointing.
    """
    _version_ = '0.1'
    _model_ = 'LaserPointing Controller'
    polling = 500

    def init_device(self):
        self.sample_time = 1
        self.cgc = False
        self.deltas = [0, 0]
        self.pid_names = []
        self.pid_locked = False
        self.active_pid = ''
        self.current_pos = {'X': 0, 'Y': 0}
        self.previos_pos = {'X': 0, 'Y': 0}
        self.positions_before_pid = {}
        camera_name = self.ds_dict['Camera']
        self.devices[camera_name] = Device(camera_name)
        super().init_device()
        self.turn_on()

    def set_pid_thread(self, pid_name: str, actuator_name: str, group_points: str):
        pid_x = spid.PID(setpoint=0, output_limits=(-50, 50), auto_mode=True, sample_time=self.sample_time)
        pid_y = spid.PID(setpoint=0, output_limits=(-50, 50), auto_mode=True, sample_time=self.sample_time)
        actuators = self.groups[actuator_name]
        actuators_devices = od()
        for actuator in actuators:
            if self.ds_dict[actuator] not in self.devices:
                self.devices[self.ds_dict[actuator]] = Device(self.ds_dict[actuator])
            actuators_devices[actuator] = self.devices[self.ds_dict[actuator]]


        pid_group = Thread(target=self.group_pid_control, args=[[pid_x, pid_y], [actuators_devices.values()],
                                       group_points, pid_name])
        self.pid_names.append(pid_name)
        pid_group.start()

    def find_device(self):
        argreturn = self.server_id, self.device_id
        self._device_id_internal, self._uri = argreturn

    def get_controller_status_local(self) -> Union[int, str]:
        return super().get_controller_status_local()

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

    @command(dtype_in=str, dtype_out=int, doc_in='Command that start center of gravity control only for the '
                                                 'locking client, thus it requires to pass client_token.')
    def start_cgc(self, client_token=''):
        if client_token == self.locking_client_token and self.locked_client:
            self.cgc = True
            self.set_pid_thread('pid1', 'Actuator 1', 'group1')
            self.set_pid_thread('pid2', 'Actuator 2', 'group2')
            return 0
        else:
            return -1

    @command(dtype_in=str, dtype_out=int, doc_in='Command that stops center of gravity control only for the '
                                                 'locking client, thus it requires to pass client_token.')
    def stop_cgc(self, client_token=''):
        if client_token == self.locking_client_token and self.locked_client:
            self.cgc = False
            self.stop_pids()
            return 0
        else:
            return -1

    def group_pid_control(self, pids: List[spid.PID], controlling_devices: List[Device],
                          points_group: str, pid_name: str):
        self.controlling_cycle = 0
        last_pid_time = monotonic()
        while self.cgc:
            while self.active_pid == pid_name:
                if self.pid_locked:
                    i = 0
                    dt = monotonic() - last_pid_time
                    if not (dt >= self.sample_time):
                        sleep(self.sample_time - dt)

                    for pid, device in zip(pids, controlling_devices):
                        pid: spid.PID = pid
                        action = pid(self.deltas[i])
                        self.execute_action(action, device)
                        i += 1
                    sleep(0.05)
                    self.controlling_cycle += 1
                    self.pid_locked = False
                    last_pid_time = monotonic()
                else:
                    for point in points_group:
                        point_rules = self.controller_rules[point]
                        for device_friendly_name, value in point_rules.items():
                            device_name = self.ds_dict[device_friendly_name]
                            if device_name not in self.devices:
                                self.devices[device_name] = Device(device_name)
                            device = self.devices[device_name]
                            self.execute_action(value, device)
                        sleep(1)
                        camera_name = self.ds_dict['Camera']
                        camera = self.devices[camera_name]
                        cg = eval(camera.cg)
                        self.previos_pos = self.current_pos
                        self.current_pos = cg

                    delta_x = self.current_pos['X'] - self.previos_pos['X']
                    delta_y = self.current_pos['Y'] - self.previos_pos['Y']
                    self.deltas = [delta_x, delta_y]

                    if delta_x <= 2 and delta_y <= 2:
                        active_pid_idx = self.pid_names.index(self.active_pid)
                        new_active_pid_idx = 0
                        if active_pid_idx == 0:
                            new_active_pid_idx = 1
                        self.active_pid = self.pid_names[new_active_pid_idx]
                        self.pid_locked = False
                    else:
                        self.pid_locked = True


            sleep(0.05)

    def execute_action(self, action: float, device: Device, threaded=False):
        if threaded:
            ex_thread = Thread(target=self.execute_action, args=[action, device])
            ex_thread.start()
        else:
            device.move_axis_rel(action)

    def stop_pids(self):
        self.pid_names = []
        self.pid_locked = False
        self.active_pid = ''
        self.current_pos = [0, 0]
        self.previos_pos = [0, 0]

if __name__ == "__main__":
    DS_LaserPointing.run_server()
