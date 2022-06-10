from tango import DbDevInfo, Database

db = Database()


names = {'1': ['manip/general', 'Numato1_GPIO', 'Numato1', '10.20.30.206', ('admin', 'admin'), 32,
         {'Pins': [(31, 'LED', 'DIR+_DM542_1st', '1'), (30, 'LED', 'ENA+_DM542_1st', '0'), (29, 'LED', 'DIR_A4988_4st', '1'), (28, 'LED', 'enable_A4988_4st', '0'), (27, 'LED', 'DIR_A4988_5th', '1'),
                   (26, 'LED', 'ennable_A4988_5th', '0'), (25, 'LED', 'Dir+_DM542_2nd', '1'), (24, 'LED', 'Ena+_DM542_2nd', '0'), (23, 'LED', 'Dir+_DM542_3rd', '1'), (22, 'LED', 'Ena+_DM542_3-rd', '0'),
                   (21, 'LED', 'MS3_A4988_all', '1'), (20, 'LED', 'MS2_A4988_all', '1'), (19, 'LED', 'MS1_A4988_all', '1'), (18, 'LED', 'DIR_A4988_1st', '1'), (17, 'LED', 'enable_A4988_1st', '0'),
                   (16, 'LED', 'DIR_A4988_2nd', '1'), (15, 'LED', 'enable_A4988_2nd', '0'), (14, 'LED', 'DIR_A4988_3rd', '1'), (13, 'LED', 'enable_A4988_3rd', '0')]
         }]
         }

def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[1]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_Numato_GPIO'
        dev_info.server = f'DS_Numato_GPIO/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': val[3], 'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'number_outputs': val[5],
                                          'authentication_name': val[4][0],
                                          'authentication_password': val[4][1],
                                          'parameters': str(val[6])})
        i += 1



if __name__ == '__main__':
    main()
