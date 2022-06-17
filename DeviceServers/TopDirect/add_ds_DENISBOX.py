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

names = {'DM542_1': ['ELYSE/motorized_devices', 'TopDirect_Mirror_VD2', 'Mirror_VD2', [0, 90], [-10.0, 90.0],
                     {'parameters': {'enable_ds': 'manip/general/Numato1_GPIO',
                                     'dir_ds': 'manip/general/Numato1_GPIO',
                                     'pulse_ds': 'manip/V0/RPI3_GPIO_Controller',
                                     'enable_pin': 30,
                                     'dir_pin': 31,
                                     'pulse_pin': 9,
                                     'microstep': 128,
                                     'dt': '1',
                                     'delay_time': 2,
                                     'max_full_steps':  3930,
                                     'step_mm': 0.003198
                                     }},],
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
                                          'limit_max': val[4][1], 'real_pos': 0.0, 'parameters': str(val[5])})

        i += 1

if __name__ == '__main__':
    main()
