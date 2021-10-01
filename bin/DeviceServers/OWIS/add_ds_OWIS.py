from tango import DbDevInfo, Database

db = Database()

# namespace, friendly_name, name for tango, keep_on parameter, gear_ration,
names_param = {'1': ['manip/VD2/DLs_VD2',
                     {'friendly_name': 'Sample holder VD2',
                      'internal_id': 3,
                      'mother_device': 'manip/general/DS_OWIS_PS90',
                      'keep_on': True,
                      'gear_ratio': 1,
                      'pitch': 1,
                      'speed': 12,
                      'revolution': 200,
                      'limit_min': -40.0,
                      'limit_max': 160.0,
                      'real_pos': 30.0,
                      'wait_time': 5,
                      'preset_positions': [0, 12.9, 24.8, 38.7, 51.6, 80]}
                     ],
               '2': ['manip/V0/DLl1_V0',
                    {'friendly_name': 'Delay line for SC',
                     'internal_id': 2,
                     'mother_device': 'manip/general/DS_OWIS_PS90',
                     'keep_on': True,
                     'gear_ratio': 1,
                     'pitch': 5.0,
                     'speed': 12,
                     'revolution': 200,
                     'limit_min': -900.0,
                     'limit_max': 100,
                     'real_pos': -100.0,
                     'wait_time': 5,
                     'preset_positions': [0, 75, -800]}
                     ],
               '3': ['manip/V0/DLs_V0',
                     {'friendly_name': 'Sample holder V0',
                      'internal_id': 3,
                      'mother_device': 'manip/general/DS_OWIS_PS90',
                      'keep_on': False,
                      'gear_ratio': 1,
                      'pitch': 1.0,
                      'speed': 8,
                      'revolution': 200,
                      'limit_min': -13.0,
                      'limit_max': 150,
                      'real_pos': 30.0,
                      'wait_time': 5,
                      'preset_positions': [155.0, 125.1, 101.8, 70.5, 46.8, 23.3, 0.0, 90.0]}
                     ],
               '4': ['manip/V0/DLl2_V0',
                     {'friendly_name': 'Delay line for OPA',
                      'internal_id': 4,
                      'mother_device': 'manip/general/DS_OWIS_PS90',
                      'keep_on': True,
                      'gear_ratio': 1,
                      'pitch': 5.0,
                      'speed': 12,
                      'revolution': 200,
                      'limit_min': -900.0,
                      'limit_max': 100,
                      'real_pos': -100.0,
                      'wait_time': 5,
                      'preset_positions': [0, 75, -800]}
                     ],
               }

i = 1
for dev_id, val in names_param.items():
    dev_info = DbDevInfo()
    dev_info.name = val[0]
    dev_info._class = 'DS_Owis_delay_line'
    dev_info.server = f'DS_Owis_delay_line/{i}'
    db.add_device(dev_info)
    param = val[1]
    param['device_id'] = dev_id
    param['server_id'] = i
    db.put_device_property(val[0], param)
    i += 1
