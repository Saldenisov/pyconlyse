from tango import DbDevInfo, Database

db = Database()

names = {'75833353934351B05090': ['ELYSE/motorized_devices', 'TopDirect_Lense', 'Lense260', [-10, -5, -2, 0, 2, 5, 10], [-20.0, 20.0],
                                  115200, 0.1],
         '55838333832351518082': ['manip/V0', 'TopDirect_SC', 'DL_SC1', [-2, -1, -.5, 0, 0.5, 1, 2, 3], [-5.0, 5.0],
                                  115200, 0.1],
}


def main():
    i = 1
    a = []
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_TopDirect_Motor'
        dev_info.server = f'DS_TopDirect_Motor/{i}_{val[2]}'
        a.append(f'{i}_{val[2]}')
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1],
                                          'wait_time': 10, 'server_id': i, 'preset_pos': val[3], 'limit_min': val[4][0],
                                          'limit_max': val[4][1], 'real_pos': 0.0, 'baudrate': val[5],
                                          'timeout': val[6]})

        i += 1

if __name__ == '__main__':
    main()
