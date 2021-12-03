from tango import DbDevInfo, Database

db = Database()


names = {22929018: ['manip/V0', 'Camera1_Pointing', 'Cam1_V0', '10.20.30.31', 22929018,
                    {'Tranposort_layer': {'Packet_size': 1500, 'Inter-Packet_Delay': 1000},
                     'Analog_Controls': {'GainAuto': 'Off', 'GainRaw': 0, 'BlackLevelRaw': -30, 'BalanceRatioRaw': 64},
                     'AOI_Controls': {'Width': 370, 'Height': 370, 'OffsetX': 600, 'OffsetY': 300},
                     'Acquisition_Controls': {'TriggerSource': 'Line1', 'TriggerMode': 'On', 'TriggerDelayAbs': 350000,
                                              'ExposureTimeAbs': 15000, 'AcquisitionFrameRateAbs': 5,
                                              'AcquisitionFrameRateEnable': True},
                     'Image_Format_Control': {'PixelFormat': 'Mono8'}}
                    ],
         22805482: ['manip/V0', 'Camera2_Pointing', 'Cam2_V0', '10.20.30.32', 22805482,
                    {'Tranposort_layer': {'Packet_size': 1500, 'Inter-Packet_Delay': 1000},
                     'Analog_Controls': {'GainAuto': 'Off', 'GainRaw': 0, 'BlackLevelRaw': -30, 'BalanceRatioRaw': 64},
                     'AOI_Controls': {'Width': 370, 'Height': 370, 'OffsetX': 600, 'OffsetY': 300},
                     'Acquisition_Controls': {'TriggerSource': 'Line1', 'TriggerMode': 'On', 'TriggerDelayAbs': 350000,
                                              'ExposureTimeAbs': 15000, 'AcquisitionFrameRateAbs': 5,
                                              'AcquisitionFrameRateEnable': True},
                     'Image_Format_Control': {'PixelFormat': 'Mono8'}}
                    ],
         22827199: ['manip/V0', 'Camera3_Pointing', 'Cam3_V0', '10.20.30.33', 22827199,
                    {'Tranposort_layer': {'Packet_size': 1500, 'Inter-Packet_Delay': 1000},
                     'Analog_Controls': {'GainAuto': 'Off', 'GainRaw': 0, 'BlackLevelRaw': -30, 'BalanceRatioRaw': 64},
                     'AOI_Controls': {'Width': 370, 'Height': 370, 'OffsetX': 600, 'OffsetY': 300},
                     'Acquisition_Controls': {'TriggerSource': 'Line1', 'TriggerMode': 'On', 'TriggerDelayAbs': 350000,
                                              'ExposureTimeAbs': 15000, 'AcquisitionFrameRateAbs': 5,
                                              'AcquisitionFrameRateEnable': True},
                     'Image_Format_Control': {'PixelFormat': 'Mono8'}}
                    ]}



def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[1]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_Basler_camera'
        dev_info.server = f'DS_Basler_camera/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': val[3], 'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'serial_number': val[4], 'parameters': str(val[5])})
        i += 1


if __name__ == '__main__':
    main()
