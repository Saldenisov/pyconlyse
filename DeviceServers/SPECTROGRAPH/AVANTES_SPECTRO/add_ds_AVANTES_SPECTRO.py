from tango import DbDevInfo, Database

db = Database()

names = {'avspectro_gamma1': ['manip/CR', 'AVANTES_SPECTRO_GAMMA', 'AVANTES_SPECTRO1', 'avspectro_gamma1',
                {'Acquisition_Controls': {'TriggerMode': 2, 'TriggerSource': 0, 'TriggerType': 0,
                                          'IntegrationTime': 0.1, 'IntegrationDelay': 0, 'BGLevel': 7000},
                 'Connection': -1},
                 {'freq': 10,
                  'arduino_sync': '10.20.30.47', 'signal_detector': 'manip/cr/avantes_ccd1',
                  'reference_detector': 'manip/cr/avantes_ccd2'},
                ]
         }

def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_AVANTES_SPECTRO'
        dev_info.server = f'DS_AVANTES_SPECTRO/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1], 'server_id': i,
                                          'serial_number': val[3], 'parameters': str(val[4]),
                                          'arduino_sync': str(val[5]['arduino_sync']),
                                          'signal_detector': val[5]['signal_detector'],
                                          'reference_detector': val[5]['reference_detector']})
        i += 1


if __name__ == '__main__':
    main()
