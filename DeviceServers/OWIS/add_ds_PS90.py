from tango import DbDevInfo, Database

def main():
    db = Database()

    names_param = {'1': ['manip/general/DS_OWIS_PS90',
                         {'baudrate': 9600,
                          'com_port': 4,
                          'interface': 0,
                          'control_unit_id': 1,
                          'friendly_name': 'DS_OWIS_PS90',
                          'serial_number': 15110070}]
                   }
    i = 1
    for dev_id, val in names_param.items():
        dev_info = DbDevInfo()
        dev_info.name = val[0]
        dev_info._class = 'DS_OWIS_PS90'
        dev_info.server = f'DS_OWIS_PS90/{i}'
        db.add_device(dev_info)
        param = val[1]
        param['device_id'] = dev_id
        param['server_id'] = i
        db.put_device_property(val[0], param)
        i += 1


if __name__ == '__main__':
    main()
