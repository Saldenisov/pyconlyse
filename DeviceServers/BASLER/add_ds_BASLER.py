from tango import DbDevInfo, Database

db = Database()


names = {22929018: ['manip/V0', 'Camera1_Pointing', 'Cam1_V0', '10.20.30.31'],
         22805482: ['manip/V0', 'Camera2_Pointing', 'Cam2_V0', '10.20.30.32'],
         22827199: ['manip/V0', 'Camera3_Pointing', 'Cam3_V0', '10.20.30.33']}


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
                                          'server_id': i})
        i += 1


if __name__ == '__main__':
    main()
