from tango import DbDevInfo, Database

db = Database()


names = {'1': ['manip/general', 'Numato1_GPIO', 'Numato1', '10.20.30.206', ('admin', 'admin'), 32,
         {'Pins': [(31, 'LED', 'DIR+_DM542_1st', 1), (30, 'LED', 'ENA+_DM542_1st', 0), (29, 'LED', 'DIR_A4988_4st', 1),
                   (28, 'LED', 'enable_A4988_4st', 0), (27, 'LED', 'DIR_A4988_5th', 1),
                   (26, 'LED', 'ennable_A4988_5th', 0), (25, 'LED', 'Dir+_DM542_2nd', 1),
                   (24, 'LED', 'Ena+_DM542_2nd', 0), (23, 'LED', 'Dir+_DM542_3rd', 1),
                   (22, 'LED', 'Ena+_DM542_3-rd', 0), (21, 'LED', 'MS3_A4988_all', 1),
                   (20, 'LED', 'MS2_A4988_all', 1), (19, 'LED', 'MS1_A4988_all', 1),
                   (18, 'LED', 'DIR_A4988_1st', 1), (17, 'LED', 'enable_A4988_1st', 0),
                   (16, 'LED', 'DIR_A4988_2nd', 1), (15, 'LED', 'enable_A4988_2nd', 0),
                   (14, 'LED', 'DIR_A4988_3rd', 1), (13, 'LED', 'enable_A4988_3rd', 0)]
         }, 'DS_Numato_GPIO'],
'2': ['manip/general', 'Numato2_RELAY', 'Numato2', '10.20.30.207', ('admin', 'admin'), 16,
         {'Pins': [(0, 'LED', 'power1_12V', 0), (1, 'LED', 'power2_12V', 0), (2, 'LED', 'power3_12V', 0),
                   (3, 'LED', 'power4_12V', 0), (4, 'LED', 'power5_12V', 0), (5, 'LED', 'power6_12V', 0),
                   (6, 'LED', 'power7_12V', 0), (7, 'LED', 'power8_12V', 0), (8, 'LED', 'power9_12V', 0),
                   (9, 'LED', 'power10_24V', 0), (10, 'LED', 'power11_24V', 0), (11, 'LED', 'power12_24V', 0),
                   (12, 'LED', 'power13_36V', 0)]
         }, 'DS_Numato_Relay']
         }

def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[1]}'
        dev_info.name = dev_name
        dev_info._class = val[7]
        dev_info.server = f'{val[7]}/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': val[3], 'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'number_outputs': val[5],
                                          'authentication_name': val[4][0],
                                          'authentication_password': val[4][1],
                                          'parameters': str(val[6])})
        i += 1



if __name__ == '__main__':
    main()
