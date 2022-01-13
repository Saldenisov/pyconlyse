from tango import DbDevInfo, Database
from collections import OrderedDict as od
db = Database()


names = {'LaserPointingV0_Cam1': ['manip/V0', 'LaserPointing-Cam1', 'Cam1',
                                  {'Camera': 'manip/V0/Cam1_V0',
                                   'MainLaserDiaphragm1': 'elyse/motorized_devices/de1',
                                   'Shutter1': 'manip/V0/s1',
                                   'CrimpingDiaphragm1': 'manip/V0/dv01',
                                   'CrimpingDiaphragm2': 'manip/V0/dv02',
                                   'ActuatorX1': 'elyse/motorized_devices/mm1_x',
                                   'ActuatorY1': 'elyse/motorized_devices/mm1_y',
                                   'ActuatorX2': 'elyse/motorized_devices/mm2_x',
                                   'ActuatorY2': 'elyse/motorized_devices/mm2_y'},
                                  od({'Laser size': ('MainLaserDiaphragm1'),
                                      'Shutters': ('Shutter1'),
                                      'Crimping Diaphragms': ('CrimpingDiaphragm1', 'CrimpingDiaphragm2'),
                                      'Actuators 1': ('ActuatorX1', 'ActuatorY1'),
                                      'Actuators 2': ('ActuatorX2', 'ActuatorY2')}
                                     ),
                                  {'starting_point': {'MainLaserDiaphragm': 9.2, 'Shutter1': -1,
                                                      'CrimpingDiaphragm': 20}}
                                  ],
         'LaserPointingV0_Cam2': ['manip/V0', 'LaserPointing-Cam2', 'Cam2',
                                  {'Camera': 'manip/V0/Cam2_V0',
                                   'MainLaserDiaphragm1': 'elyse/motorized_devices/de1',
                                   'MainLaserDiaphragm2': 'manip/V0/dv01',
                                   'Shutter1': 'manip/V0/s1',
                                   'Shutter2': 'manip/V0/s2',
                                   'CrimpingDiaphragm1': 'manip/V0/dv02',
                                   'CrimpingDiaphragm2': 'manip/V0/dv03',
                                   'ActuatorX3': 'manip/V0/mm3_x',
                                   'ActuatorY3': 'manip/V0/mm3_y',
                                   'ActuatorX4': 'manip/V0/mm4_x',
                                   'ActuatorY4': 'manip/V0/mm4_y',
                                   'TranslationStage1': ('manip/general/DS_OWIS_PS90', [2])},
                                  od({'Laser size': ('MainLaserDiaphragm1', 'MainLaserDiaphragm2'),
                                      'Shutters': ('Shutter1', 'Shutter2'),
                                      'Crimping Diaphragms': ('CrimpingDiaphragm1', 'CrimpingDiaphragm2'),
                                      'Actuators 1': ('ActuatorX3', 'ActuatorY3'),
                                      'Actuators 2': ('ActuatorX4', 'ActuatorY4'),
                                      'Translation stages': ('TranslationStage1')}),
                                  {'starting_point': {'MainLaserDiaphragm': 9.2, 'Shutter1': -1,
                                                      'CrimpingDiaphragm': 20}}
                                  ]
         }


def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[1]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_LaserPointing'
        dev_info.server = f'DS_LaserPointing/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1], 'server_id': i,
                                          'ds_dict': str(val[3]), 'groups': str(val[4]), 'rules': str(val[5])})
        i += 1


if __name__ == '__main__':
    main()
