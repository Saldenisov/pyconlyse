from tango import DbDevInfo, Database

db = Database()


names = {'1': ['manip/general', 'Numato1_GPIO', 'Numato1', '10.20.30.204', ('admin', 'elyse'), 32],
         {'Pins': [(31, 'LED', 'DIR+_DM542_1st'), (30, 'LED', 'ENA+_DM542_1st'), (29, 'LED', 'DIR_A4988_4st'), (28, 'LED', 'enable_A4988_4st'), (27, 'LED', 'DIR_A4988_5th'),
                   (26, 'LED', 'ennable_A4988_5th'), (25, 'LED', 'Dir+_DM542_2nd'), (24, 'LED', 'Ena+_DM542_2nd'), (23, 'LED', 'Dir+_DM542_3rd'), (22, 'LED', 'Ena+_DM542_3-rd'),
                   (21, 'LED', 'MS3_A4988_all'), (20, 'LED', 'MS2_A4988_all'), (19, 'LED', 'MS1_A4988_all'), (18, 'LED', 'DIR_A4988_1st'), (17, 'LED', 'enable_A4988_1st'),
                   (16, 'LED', 'DIR_A4988_2nd'), (15, 'LED', 'enable_A4988_2nd'), (14, 'LED', 'DIR_A4988_3rd'), (13, 'LED', 'enable_A4988_3rd')]},
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
                                          'authentication_password': val[4][1]})
        i += 1



if __name__ == '__main__':
    main()
