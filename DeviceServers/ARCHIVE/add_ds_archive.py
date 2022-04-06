from tango import DbDevInfo, Database

db = Database()


names = {1: ['manip/general', 'Archiving_Experimental', 'Archive', "E:\\data\\h5", 1, 2**30]}



def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_c'
        dev_info.server = f'DS_Archive/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'serial_number': val[4], 'folder_location': val[3],
                                          'maximum_size': val[5]})
        i += 1


if __name__ == '__main__':
    main()
