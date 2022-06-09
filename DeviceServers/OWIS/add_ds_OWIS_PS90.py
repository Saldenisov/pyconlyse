from tango import DbDevInfo, Database

db = Database()

# namespace, friendly_name, name for tango, keep_on parameter, gear_ration,

delay_lines = {1: {'device_name': 'manip/VD2/DLs_VD2',
                   'friendly_name': 'Sample holder VD2',
                    'keep_on': False,
                    'gear_ratio': 1,
                    'pitch': 1,
                      'speed': 10,
                      'revolution': 200,
                      'limit_min': -40.0,
                      'limit_max': 260.0,
                      'real_pos': 30.0,
                      'wait_time': 5,
                      'preset_positions': [0, 12.9, 24.8, 38.7, 51.6, 83.0],
                      'relative_shift': 1.0}
                     ,
               2: {'device_name': 'manip/V0/DLl1_V0',
                     'friendly_name': 'Delay line for SC',
                     'keep_on': True,
                     'gear_ratio': 1,
                     'pitch': 5.0,
                     'speed': 65.0,
                     'revolution': 200.0,
                     'limit_min': -900.0,
                     'limit_max': 100.0,
                     'real_pos': -100.0,
                     'wait_time': 5,
                     'preset_positions': [0.0, 75.0, -100.0, -800.0],
                   'relative_shift': 1.0}
                     ,
               3: {'device_name': 'manip/V0/DLs_V0',
                     'friendly_name': 'Sample holder V0',
                      'keep_on': False,
                      'gear_ratio': 1.0,
                      'pitch': 1.0,
                      'speed': 8.0,
                      'revolution': 200.0,
                      'limit_min': -13.0,
                      'limit_max': 150.0,
                      'real_pos': 30.0,
                      'wait_time': 5,
                      'preset_positions': [155.0, 125.1, 101.8, 70.5, 46.8, 23.3, 0.0, 90.0],
                   'relative_shift': 1.0}
                     ,
               4: {'device_name': 'manip/V0/DLl2_V0',
                     'friendly_name': 'Delay line for OPA',
                      'keep_on': True,
                      'gear_ratio': 1.0,
                      'pitch': 5.0,
                      'speed': 65.0,
                      'revolution': 200,
                      'limit_min': -900.0,
                      'limit_max': 100.0,
                      'real_pos': -100.0,
                      'wait_time': 5,
                      'preset_positions': [0, 75.0,-100.0, -250.0, -500.0, -800.0],
                   'relative_shift': 1.0}
               }
names_param = {'1': ['manip/general/DS_OWIS_PS90',
                     {'baudrate': 9600,
                      'com_port': 3,
                      'interface': 0,
                      'control_unit_id': 1,
                      'friendly_name': 'DS_OWIS_PS90',
                      'serial_number': 15110070,
                      'delay_lines_parameters': str(delay_lines)}]
               }


def main():
    i = 1
    for dev_id, val in names_param.items():
        dev_info = DbDevInfo()
        dev_info.name = val[0]
        dev_info._class = 'DS_OWIS_PS90'
        dev_info.server = f'DS_OWIS_PS90/{i}'
        db.add_device(dev_info)
        param = val[1]
        param['device_id'] = dev_id
        param['server_id'] = i
        db.put_device_property(val[0], param)
        i += 1


if __name__ == '__main__':
    main()
