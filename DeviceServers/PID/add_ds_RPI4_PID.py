from tango import DbDevInfo, Database

db = Database()


names = {1: ['manip/V0', 'RPI4_PID_Pt100', 'RPI4_PID', '129.175.100.171', 1, 20, 50]}



def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_RPI4_PID'
        dev_info.server = f'DS_RPI4_PID/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': val[3], 'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'serial_number': val[4], 'temp_polling': val[5],
                                          'pid_polling': val[6]})
        i += 1


if __name__ == '__main__':
    main()
