from tango import DbDevInfo, Database

db = Database()


names = {'24A42C38E097': ['manip/V0', 'PDU_VO', 'V0', '10.20.30.40', ('radiolyse', 'Elys3!lcp'), 4],
         '24A42C38E09F': ['manip/VD2', 'PDU_VD2', 'VD2','10.20.30.41', ('radiolyse', 'Elys3!lcp'), 4],
         '24A42C38E0B7': ['manip/SD1', 'PDU_SD1', 'SD1', '10.20.30.42', ('radiolyse', 'Elys3!lcp'), 4],
         '24A42C38E0AB': ['manip/SD2', 'PDU_SD2', 'SD2', '10.20.30.43', ('radiolyse', 'Elys3!lcp'), 4],
         '24A42C38E0A7': ['manip/ELYSE', 'PDU_ELYSE', 'ELYSE', '10.20.30.44', ('elyse', 'elyse'), 4]}


def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[1]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_Netio_pdu'
        dev_info.server = f'DS_Netio_pdu/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': val[3], 'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'number_outputs': val[5],
                                          'authentication_name': val[4][0],
                                          'authentication_password': val[4][1]})
        i += 1


if __name__ == '__main__':
    main()
