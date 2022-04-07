from tango import DbDevInfo, Database

db = Database()


names = {1: ['manip/V0', 'RPI4_GPIO_Controller', 'RPI_GPIO_V0', '129.175.100.171', 'rpi4_1',
                    {'Pins': [(4, 'LED', 'Laser_shutter'), (3, 'LED', 'Room_light')]}
                    ]}


def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_RPI_GPIO'
        dev_info.server = f'DS_RPI_GPIO/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': val[3], 'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'serial_number': val[4], 'parameters': str(val[5]),
                                          'number_pins': len(val[5]['Pins'])})
        i += 1


if __name__ == '__main__':
    main()
