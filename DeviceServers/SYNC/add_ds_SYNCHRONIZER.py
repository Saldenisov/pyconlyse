from tango import DbDevInfo, Database

db = Database()


names = {1: ['ELYSE/clocks', 'Synchronizer1', 'SYNC_MAIN', 'Synchronizer1_main']}


def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_Synchronizer'
        dev_info.server = f'DS_Synchronizer/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1], 'server_id': i,
                                          'serial_number': val[3]})
        i += 1


if __name__ == '__main__':
    main()
