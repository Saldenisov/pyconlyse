import sys
import simple_pid as spid
from pathlib import Path
from typing import Union, List
from collections import OrderedDict as od
from tango.server import attribute, command, pipe, device_property
from taurus import Device
from time import sleep, monotonic
from threading import Thread
from scipy.optimize import minimize, basinhopping, dual_annealing

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from tango import DevState


try:
    from DeviceServers.General.DS_Control import DS_ControlPosition
except ModuleNotFoundError:
    from General.DS_Control import DS_ControlPostion

global global_result
global glob_res_n

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
        self.optimization_names = []
        self.opt_locked = False
        self.active_opt = ''
        self.current_pos = {'X': 0, 'Y': 0}
        self.previos_pos = {'X': 0, 'Y': 0}
        self.positions_before_pid = {}
        super().init_device()
        camera_name = self.ds_dict['Camera']
        self.devices[camera_name] = Device(camera_name)
        self.turn_on()
        self.locking_client_token = 'test'
        self.locked_client = True
        self.start_cgc('test')

    def set_optimization_thread(self, opt_name: str, actuator_name: str, group_points: str, bounds):
        actuators = self.groups[actuator_name]
        actuators_devices = od()
        for actuator in actuators:
            if self.ds_dict[actuator] not in self.devices:
                self.devices[self.ds_dict[actuator]] = Device(self.ds_dict[actuator])
            actuators_devices[actuator] = self.devices[self.ds_dict[actuator]]

        optimization_group = Thread(target=self.minimization, args=[list(actuators_devices.values()),
                                                                    self.pid_groups[group_points], opt_name])
        setattr(self, f'{opt_name}_bounds', bounds)
        self.optimization_names.append(opt_name)
        optimization_group.start()

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
        # if client_token == self.locking_client_token and self.locked_client:
        if True:
            self.cgc = True
            self.set_optimization_thread('opt1', 'Actuators 1', 'group1', [(-40, 40), (-40, 40)])
            self.set_optimization_thread('opt2', 'Actuators 2', 'group2', [(-40, 40), (-40, 40)])
            self.active_opt = self.optimization_names[0]
            return 0
        else:
            return -1

    @command(dtype_in=str, dtype_out=int, doc_in='Command that stops center of gravity control only for the '
                                                 'locking client, thus it requires to pass client_token.')
    def stop_cgc(self, client_token=''):
        # if client_token == self.locking_client_token and self.locked_client:
        if True:
            self.cgc = False
            self.stop_opts()
            return 0
        else:
            return -1

    def minimization(self, controlling_devices: List[Device], points_group: str, opt_name: str):
        self.controlling_cycle = 0
        self.glob_res_n = 0
        self.global_result = 0

        def min_func(x):
            print(f'Trying {opt_name} with {x}')
            if self.active_opt == opt_name:
                for device, pos in zip(controlling_devices, x):
                    self.execute_action(pos, device)

                for point in points_group:
                    point_rules = self.controller_rules[point]
                    for device_friendly_name, value in point_rules.items():
                        device_name = self.ds_dict[device_friendly_name]
                        if device_name not in self.devices:
                            self.devices[device_name] = Device(device_name)
                        device = self.devices[device_name]
                        self.execute_action(value, device, threaded=True)
                    sleep(1.5)
                    camera_name = self.ds_dict['Camera']
                    camera = self.devices[camera_name]
                    cg = eval(camera.cg)
                    self.previos_pos = self.current_pos
                    self.current_pos = cg

                if self.previos_pos['X'] == 1024 and self.current_pos['X'] == 1024:
                    delta_x = 1024
                else:
                    delta_x = self.previos_pos['X'] - self.current_pos['X']

                if self.previos_pos['Y'] == 1024 and self.current_pos['Y'] == 1024:
                    delta_y = 1024
                else:
                    delta_y = self.previos_pos['Y'] - self.current_pos['Y']

                self.deltas = [delta_x, delta_y]

                if (abs(delta_x) <= 2 and abs(delta_y) <= 2) or self.glob_res_n >= 5:
                    active_opt_idx = self.optimization_names.index(self.active_opt)
                    new_active_opt_idx = 0
                    if active_opt_idx == 0:
                        new_active_opt_idx = 1
                    self.active_opt = self.optimization_names[new_active_opt_idx]
                    res = 0
                    self.glob_res_n = 0
                    x_pos, y_pos = x
                    bounds = getattr(self, f'{opt_name}_bounds')

                    x_min = x_pos - abs(bounds[0][0] / 1.5)
                    x_max = x_pos + abs(bounds[0][1] / 1.5)
                    y_min = y_pos - abs(bounds[1][0] / 1.5)
                    y_max = y_pos + abs(bounds[1][1] / 1.5)
                    setattr(self, f'{opt_name}_bounds', [(x_min, x_max), (y_min, y_max)])
                else:
                    res = (delta_x**2 + delta_y**2)**.5
            else:
                res = 0
            print(f'Deltas: {self.deltas}...Res: {res}')

            if res != 0:
                ratio = abs(self.global_result) / abs(res)
            else:
                ratio = 1

            if (ratio >= 0.9 and ratio <= 1.1) and res < 1448:
                self.glob_res_n += 1
                print(f'Glob res_n: {self.glob_res_n}')
            else:
                self.glob_res_n = 0

            self.global_result = res

            return res


        while self.cgc:
            if self.active_opt == opt_name:
                bounds = getattr(self, f'{opt_name}_bounds')
                print(f'{opt_name} bounds: {bounds} ')
                minimize(fun=min_func, x0=[0, 0], bounds=bounds)
                # basinhopping(func=min_func, x0=[0, 0], niter=100, T=1.0, stepsize=5, interval=2,
                #              disp=True, target_accept_rate=0.5, stepwise_factor=0.9)
                # dual_annealing(func=min_func, x0=[0, 0], maxiter=200, no_local_search=True,
                #                bounds=bounds, maxfun=10)

                # minimize(fun=min_func, x0=[0, 0], args=([controlling_devices, self, opt_name]), method='TNC',
                #          bounds=[(-100, 100)] * 2, jac='2-point',
                #          options={'disp': True, 'finite_diff_rel_step': 0.1, 'xtol': 0.1, 'accuracy': 0.1, 'eps': 0.1})
            sleep(0.1)

    def execute_action(self, action: float, device: Device, relative=False, threaded=False):
        if threaded:
            ex_thread = Thread(target=self.execute_action, args=[action, device])
            ex_thread.start()
        else:
            if relative:
                device.move_axis_rel(action)
            else:
                device.move_axis_abs(action)

    def stop_opts(self):
        self.optimization_names = []
        self.opt_locked = False
        self.active_opt = ''
        self.current_pos = [0, 0]
        self.previos_pos = [0, 0]

if __name__ == "__main__":
    DS_LaserPointing.run_server()
