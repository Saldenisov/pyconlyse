from tango import DbDevInfo, Database

db = Database()


"""
for DM542
//310 turns in delay line in the long 200mm one
// 128 - 1 (better 2)
// 16 - 40 (50)
//8 - 80 (90)
//4 - 160 (170)
//2 - 360 (400)
int microsteps = 128; // in one step
int delay_time = 2; // between TTL pulses in us
//max full microsteps is 62900 (128) for 200mm DL
//3930 for (16 microsteps) for 100mm DL
const long max_full_steps = 3930;
// 0.003198 in one microstep for 128microsteps
// 0.025584 in one microstep for 16microsteps
const float step_mm = 0.003198;
"""

names = {'DM542_1': ['ELYSE/motorized_devices', 'TopDirect_Mirror_VD2', 'Mirror_VD2', [0, 90], [-1000.0, 1000.0],
                     {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'pulse_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 30,
                                     'dir_pin': 31,
                                     'pulse_pin': 9,
                                     'microstep': 8,
                                     'dt': 80,
                                     'delay_time': 90,
                                     'max_full_steps':  3930,
                                     'step_mm': 1
                                     }},],
        'DM542_2': ['ELYSE/motorized_devices', 'TopDirect_line_1', 'something1', [0, 90], [-10.0, 90.0],
                     {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'pulse_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 24,
                                     'dir_pin': 25,
                                     'pulse_pin': 23,
                                     'microstep': 128,
                                     'dt': '1',
                                     'delay_time': 2,
                                     'max_full_steps':  3930,
                                     'step_mm': 0.003198
                                     }},],
        'DM542_3': ['ELYSE/motorized_devices', 'TopDirect_line_2', 'something2', [0, 90], [-10.0, 90.0],
                     {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'pulse_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 22,
                                     'dir_pin': 23,
                                     'pulse_pin': 22,
                                     'microstep': 128,
                                     'dt': '1',
                                     'delay_time': 2,
                                     'max_full_steps':  3930,
                                     'step_mm': 0.003198
                                     }},],
        'A4988_1': ['ELYSE/motorized_devices', 'TopDirect_flipper', 'flipper', [0, 90], [0, 1],
                    {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'step_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 22,
                                     'dir_pin': 18,
                                     'step_pin': 24,
                                     'microstep': 128,
                                     'dt': '1',
                                     'delay_time': 2,
                                     'max_full_steps': 90,
                                     'step_mm': 90
                                     }}, ],
        'A4988_2': ['ELYSE/motorized_devices', 'TopDirect_filter_1_VD2', 'filter_1_VD2', [0, 360], [0, 6],
                    {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'step_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 15,
                                     'dir_pin': 16,
                                     'step_pin': 24,
                                     'microstep': 128,
                                     'dt': '1',
                                     'delay_time': 2,
                                     'max_full_steps': 360,
                                     'step_mm': 360
                                     }}, ],
        'A4988_3': ['ELYSE/motorized_devices', 'TopDirect_filter_2_VD2', 'filter_2_VD2', [0, 360], [0, 6],
                    {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'step_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 15,
                                     'dir_pin': 16,
                                     'step_pin': 24,
                                     'microstep': 128,
                                     'dt': '1',
                                     'delay_time': 2,
                                     'max_full_steps': 360,
                                     'step_mm': 360
                                     }}, ],
         'A4988_4': ['ELYSE/motorized_devices', 'TopDirect_iris_VD2', 'iris_VD2', [0, 200], [0, 200],
                     {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'step_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 15,
                                     'dir_pin': 16,
                                     'step_pin': 24,
                                     'microstep': 128,
                                     'dt': '1',
                                     'delay_time': 2,
                                     'max_full_steps': 200,
                                     'step_mm': 1
                                     }}, ],
}


def main():
    i = 1
    a = []
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_DenisBox_Motor'
        dev_info.server = f'DS_DenisBox_Motor/{i}_{val[2]}'
        a.append(f'{i}_{val[2]}')
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1],
                                          'wait_time': 10, 'server_id': i, 'preset_pos': val[3], 'limit_min': val[4][0],
                                          'limit_max': val[4][1], 'real_pos': 0.0,
                                          'parameters': str(val[5]['parameters'])})

        i += 1

if __name__ == '__main__':
    main()