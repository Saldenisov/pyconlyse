from tango import DbDevInfo, Database

db = Database()

names = {7428: ['manip/CR', 'ANDOR_CCD_V0', 'ANDOR_CCD1', 7428,
                {'Acquisition_Controls': {'SetAcquisitionMode': 3, 'SetTriggerMode': 1, 'SetFastExtTrigger': False,
                                              'SetReadMode': 1, 'SetMultiTrack': (2, 128, 0), 'SetExposureTime': 0.0001,
                                              'SetHSSpeed': 1, 'SetVSSpeed': 1, 'SetADChannel': 1, 'SetPreAmpGain': 0,
                                              'SetBaselineClamp': True, 'SetTemperature': -80, 'CoolerON': True
                                              }}
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
                                          'serial_number': val[3], 'parameters': str(val[4])})
        i += 1


if __name__ == '__main__':
    main()
