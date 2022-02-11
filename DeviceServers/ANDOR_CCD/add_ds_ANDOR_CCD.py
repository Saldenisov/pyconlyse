from tango import DbDevInfo, Database

db = Database()

names = {7428: ['manip/CR', 'ANDOR_CCD_V0', 'ANDOR_CCD1', 7428,
                {'Acquisition_Controls': {'AcquisitionMode': 3, 'TriggerMode': 1, 'FastExtTrigger': False,
                                          'ReadMode': 1, 'MultiTrack': (2, 128, 0), 'ExposureTime': 0.0001,
                                          'HSSpeed': 1, 'VSSpeed': 1, 'ADChannel': 1, 'PreAmpGain': 0,
                                          'BaselineClamp': True, 'Temperature': -80, 'CoolerON': True
                                              }},
                 {'width': 1024}, 'C:/dev/pyconlyse/DeviceServers/ANDOR_CCD/atmcd32d.dll'
                ]
         }



def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_ANDOR_CCD'
        dev_info.server = f'DS_ANDOR_CCD/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1], 'server_id': i,
                                          'serial_number': val[3], 'parameters': str(val[4]), 'width': val[5]['width'],
                                          'dll_path': val[6]})
        i += 1


if __name__ == '__main__':
    main()
