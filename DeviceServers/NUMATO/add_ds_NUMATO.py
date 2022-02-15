from tango import DbDevInfo, Database

db = Database()


names = {'1': ['manip/general', 'Numato1_GPIO', 'Numato1', '10.20.30.204', ('admin', 'Elys3!icp'), 32]}


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
